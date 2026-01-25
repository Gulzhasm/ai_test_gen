"""
File-based persistent cache implementation.

Stores cache entries as JSON files for persistence across sessions.
"""
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from .cache_interface import ICache, CacheStats


class FileCache(ICache[Any]):
    """File-based persistent cache."""

    INDEX_FILE = "index.json"

    def __init__(
        self,
        cache_dir: str = ".cache",
        default_ttl: Optional[timedelta] = None,
        max_size: int = 10000
    ):
        """Initialize file cache.

        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live (None = 7 days)
            max_size: Maximum number of entries
        """
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl or timedelta(days=7)
        self._max_size = max_size
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._index = self._load_index()

    def _get_index_path(self) -> Path:
        """Get path to index file."""
        return self._cache_dir / self.INDEX_FILE

    def _load_index(self) -> Dict[str, Dict]:
        """Load index from file.

        Returns:
            Index dictionary
        """
        index_path = self._get_index_path()
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_index(self) -> None:
        """Save index to file."""
        index_path = self._get_index_path()
        try:
            with open(index_path, 'w') as f:
                json.dump(self._index, f, indent=2)
        except IOError:
            pass  # Silently fail on write errors

    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        # Use hash of key for filename to handle special characters
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:32]
        return self._cache_dir / f"{key_hash}.json"

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
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

            # Read value from file
            file_path = self._get_file_path(key)
            if not file_path.exists():
                self._delete_entry(key)
                self._misses += 1
                return None

            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    self._hits += 1

                    # Update hit count in index
                    self._index[key]["hit_count"] = (
                        self._index[key].get("hit_count", 0) + 1
                    )
                    self._save_index()

                    return data["value"]
            except (json.JSONDecodeError, IOError, KeyError):
                self._delete_entry(key)
                self._misses += 1
                return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> None:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live (uses default if not provided)
        """
        with self._lock:
            # Evict if at capacity
            while len(self._index) >= self._max_size:
                self._evict_oldest()

            # Calculate expiration
            actual_ttl = ttl or self._default_ttl
            expires_at = datetime.now() + actual_ttl

            # Write value to file
            file_path = self._get_file_path(key)
            try:
                data = {
                    "key": key,
                    "value": value,
                    "created_at": datetime.now().isoformat(),
                    "expires_at": expires_at.isoformat()
                }
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2, default=str)

                # Update index
                self._index[key] = {
                    "file": str(file_path.name),
                    "created_at": datetime.now().isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "hit_count": 0
                }
                self._save_index()

            except (IOError, TypeError) as e:
                # Failed to serialize or write
                print(f"Cache write error for key {key}: {e}")

    def delete(self, key: str) -> bool:
        """Remove entry from cache.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted
        """
        with self._lock:
            return self._delete_entry(key)

    def _delete_entry(self, key: str) -> bool:
        """Internal delete without lock.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted
        """
        if key not in self._index:
            return False

        # Delete file
        file_path = self._get_file_path(key)
        try:
            if file_path.exists():
                file_path.unlink()
        except IOError:
            pass

        # Remove from index
        del self._index[key]
        self._save_index()

        return True

    def _evict_oldest(self) -> None:
        """Evict oldest entry."""
        if not self._index:
            return

        # Find oldest entry by created_at
        oldest_key = min(
            self._index.keys(),
            key=lambda k: self._index[k].get("created_at", "")
        )
        self._delete_entry(oldest_key)
        self._evictions += 1

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            # Delete all cache files
            for key in list(self._index.keys()):
                file_path = self._get_file_path(key)
                try:
                    if file_path.exists():
                        file_path.unlink()
                except IOError:
                    pass

            # Clear index
            self._index.clear()
            self._save_index()

            # Reset stats
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def contains(self, key: str) -> bool:
        """Check if key exists and is valid.

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        with self._lock:
            if key not in self._index:
                return False

            entry_meta = self._index[key]
            expires_at = datetime.fromisoformat(entry_meta["expires_at"])

            if datetime.now() > expires_at:
                self._delete_entry(key)
                return False

            return True

    @property
    def stats(self) -> CacheStats:
        """Return cache statistics.

        Returns:
            CacheStats instance
        """
        with self._lock:
            return CacheStats(
                size=len(self._index),
                max_size=self._max_size,
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions
            )

    def keys(self) -> List[str]:
        """Get all valid cache keys.

        Returns:
            List of keys (non-expired only)
        """
        with self._lock:
            valid_keys = []
            expired_keys = []

            for key, meta in self._index.items():
                expires_at = datetime.fromisoformat(meta["expires_at"])
                if datetime.now() > expires_at:
                    expired_keys.append(key)
                else:
                    valid_keys.append(key)

            # Clean up expired entries
            for key in expired_keys:
                self._delete_entry(key)

            return valid_keys

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired = []
            for key, meta in self._index.items():
                expires_at = datetime.fromisoformat(meta["expires_at"])
                if datetime.now() > expires_at:
                    expired.append(key)

            for key in expired:
                self._delete_entry(key)

            return len(expired)

    def get_disk_usage(self) -> int:
        """Get total disk usage of cache.

        Returns:
            Disk usage in bytes
        """
        total = 0
        for file in self._cache_dir.iterdir():
            if file.is_file():
                total += file.stat().st_size
        return total
