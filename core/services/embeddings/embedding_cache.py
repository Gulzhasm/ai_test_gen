"""
Embedding cache for persistent storage of computed embeddings.

Uses file-based storage similar to FileCache pattern but optimized
for embedding vectors with longer TTL (embeddings are expensive to compute).
"""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from .embedding_interface import EmbeddingResult


class EmbeddingCache:
    """File-based persistent cache for embeddings.

    Embeddings are expensive to compute, so cache with longer TTL (30 days default).
    Stores vectors as JSON-serializable lists.
    """

    INDEX_FILE = "embedding_index.json"

    def __init__(
        self,
        cache_dir: str = ".cache/embeddings",
        default_ttl: timedelta | None = None,
        max_entries: int = 50000
    ):
        """Initialize embedding cache.

        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live (30 days default for embeddings)
            max_entries: Maximum number of entries
        """
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl or timedelta(days=30)
        self._max_entries = max_entries
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
        self._index = self._load_index()

    def _get_index_path(self) -> Path:
        """Get path to index file."""
        return self._cache_dir / self.INDEX_FILE

    def _load_index(self) -> dict[str, dict]:
        """Load index from file."""
        index_path = self._get_index_path()
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save_index(self) -> None:
        """Save index to file."""
        index_path = self._get_index_path()
        try:
            with open(index_path, 'w') as f:
                json.dump(self._index, f, indent=2)
        except OSError:
            pass

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key from text and model.

        Args:
            text: Input text
            model: Model name

        Returns:
            Cache key string
        """
        combined = f"{model}:{text}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key."""
        return self._cache_dir / f"{key[:32]}.json"

    def get(self, text: str, model: str) -> EmbeddingResult | None:
        """Retrieve cached embedding.

        Args:
            text: Original text
            model: Model name used for embedding

        Returns:
            Cached EmbeddingResult or None if not found/expired
        """
        key = self._get_cache_key(text, model)

        with self._lock:
            if key not in self._index:
                self._misses += 1
                return None

            entry_meta = self._index[key]

            # Check expiration
            expires_at = datetime.fromisoformat(entry_meta["expires_at"])
            if datetime.now() > expires_at:
                self._delete_entry(key)
                self._misses += 1
                return None

            # Read from file
            file_path = self._get_file_path(key)
            if not file_path.exists():
                self._delete_entry(key)
                self._misses += 1
                return None

            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    self._hits += 1

                    # Update hit count
                    self._index[key]["hit_count"] = (
                        self._index[key].get("hit_count", 0) + 1
                    )
                    self._save_index()

                    return EmbeddingResult.from_dict(data["embedding"])

            except (OSError, json.JSONDecodeError, KeyError):
                self._delete_entry(key)
                self._misses += 1
                return None

    def set(
        self,
        result: EmbeddingResult,
        ttl: timedelta | None = None
    ) -> None:
        """Store embedding in cache.

        Args:
            result: EmbeddingResult to cache
            ttl: Time-to-live (uses default if not provided)
        """
        key = self._get_cache_key(result.text, result.model)

        with self._lock:
            # Evict if at capacity
            while len(self._index) >= self._max_entries:
                self._evict_oldest()

            # Calculate expiration
            actual_ttl = ttl or self._default_ttl
            expires_at = datetime.now() + actual_ttl

            # Write to file
            file_path = self._get_file_path(key)
            try:
                data = {
                    "embedding": result.to_dict(),
                    "created_at": datetime.now().isoformat(),
                    "expires_at": expires_at.isoformat()
                }
                with open(file_path, 'w') as f:
                    json.dump(data, f)

                # Update index
                self._index[key] = {
                    "text_preview": result.text[:50],
                    "model": result.model,
                    "dimensions": result.dimensions,
                    "created_at": datetime.now().isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "hit_count": 0
                }
                self._save_index()

            except (OSError, TypeError) as e:
                print(f"Embedding cache write error: {e}")

    def get_batch(
        self,
        texts: list[str],
        model: str
    ) -> dict[str, EmbeddingResult | None]:
        """Get multiple embeddings from cache.

        Args:
            texts: List of texts to look up
            model: Model name

        Returns:
            Dict mapping text to EmbeddingResult (None if not cached)
        """
        results = {}
        for text in texts:
            results[text] = self.get(text, model)
        return results

    def set_batch(
        self,
        results: list[EmbeddingResult],
        ttl: timedelta | None = None
    ) -> None:
        """Store multiple embeddings in cache.

        Args:
            results: List of EmbeddingResults to cache
            ttl: Time-to-live
        """
        for result in results:
            self.set(result, ttl)

    def _delete_entry(self, key: str) -> bool:
        """Delete entry without lock."""
        if key not in self._index:
            return False

        file_path = self._get_file_path(key)
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

        del self._index[key]
        self._save_index()
        return True

    def _evict_oldest(self) -> None:
        """Evict oldest entry."""
        if not self._index:
            return

        oldest_key = min(
            self._index.keys(),
            key=lambda k: self._index[k].get("created_at", "")
        )
        self._delete_entry(oldest_key)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            for key in list(self._index.keys()):
                file_path = self._get_file_path(key)
                try:
                    if file_path.exists():
                        file_path.unlink()
                except OSError:
                    pass

            self._index.clear()
            self._save_index()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "size": len(self._index),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }
