"""
Embedding pattern index for pre-computed pattern embeddings.

Loads patterns from JSON and pre-computes embeddings for fast similarity search.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .embedding_interface import IEmbeddingProvider
from .embedding_cache import EmbeddingCache


@dataclass
class PatternEntry:
    """Single pattern with pre-computed embedding."""
    pattern_id: str
    canonical: str
    category: str
    subcategory: Optional[str]
    synonyms: List[str]
    embedding: np.ndarray
    synonym_embeddings: List[np.ndarray] = field(default_factory=list)
    regex_fallback: Optional[str] = None

    def get_all_embeddings(self) -> List[np.ndarray]:
        """Get canonical + all synonym embeddings."""
        return [self.embedding] + self.synonym_embeddings


class EmbeddingPatternIndex:
    """Pre-computed pattern embeddings for fast similarity search.

    Loads patterns from JSON file and pre-computes embeddings for:
    - Canonical pattern text
    - All synonyms (for matching variations)

    Usage:
        provider = create_embedding_provider()
        index = EmbeddingPatternIndex(provider)
        index.load_patterns()

        patterns = index.get_patterns_by_category("action")
    """

    def __init__(
        self,
        provider: IEmbeddingProvider,
        cache: Optional[EmbeddingCache] = None,
        patterns_file: str = "patterns/ac_patterns.json"
    ):
        """Initialize pattern index.

        Args:
            provider: Embedding provider for computing vectors
            cache: Optional cache for persistence
            patterns_file: Path to patterns JSON file
        """
        self._provider = provider
        self._cache = cache or EmbeddingCache()
        self._patterns_file = patterns_file
        self._patterns: Dict[str, PatternEntry] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if patterns have been loaded."""
        return self._loaded

    @property
    def pattern_count(self) -> int:
        """Number of loaded patterns."""
        return len(self._patterns)

    def load_patterns(self) -> None:
        """Load patterns from JSON and compute embeddings.

        Raises:
            FileNotFoundError: If patterns file doesn't exist
        """
        patterns_path = Path(self._patterns_file)
        if not patterns_path.exists():
            raise FileNotFoundError(f"Patterns file not found: {self._patterns_file}")

        with open(patterns_path) as f:
            data = json.load(f)

        # Collect all texts to embed (canonical + synonyms)
        all_texts = []
        text_mapping = {}  # text -> (pattern_id, is_canonical)

        for pattern in data["patterns"]:
            pattern_id = pattern["id"]
            canonical = pattern["canonical"]

            # Add canonical
            all_texts.append(canonical)
            text_mapping[canonical] = (pattern_id, True)

            # Add synonyms
            for synonym in pattern.get("synonyms", []):
                all_texts.append(synonym)
                text_mapping[synonym] = (pattern_id, False)

        # Batch embed all texts
        embeddings = self._embed_all(all_texts)

        # Build pattern entries
        for pattern in data["patterns"]:
            pattern_id = pattern["id"]
            canonical = pattern["canonical"]

            # Get canonical embedding
            canonical_embedding = embeddings.get(canonical)
            if canonical_embedding is None:
                print(f"Warning: Failed to embed pattern {pattern_id}")
                continue

            # Get synonym embeddings
            synonym_embeddings = []
            for synonym in pattern.get("synonyms", []):
                syn_emb = embeddings.get(synonym)
                if syn_emb is not None:
                    synonym_embeddings.append(syn_emb)

            # Create pattern entry
            entry = PatternEntry(
                pattern_id=pattern_id,
                canonical=canonical,
                category=pattern["category"],
                subcategory=pattern.get("subcategory"),
                synonyms=pattern.get("synonyms", []),
                embedding=canonical_embedding,
                synonym_embeddings=synonym_embeddings,
                regex_fallback=pattern.get("regex_fallback")
            )

            self._patterns[pattern_id] = entry

            # Update category index
            category = pattern["category"]
            if category not in self._category_index:
                self._category_index[category] = []
            self._category_index[category].append(pattern_id)

        self._loaded = True
        print(f"Loaded {len(self._patterns)} patterns with embeddings")

    def _embed_all(self, texts: List[str]) -> Dict[str, np.ndarray]:
        """Embed all texts, using cache where possible.

        Args:
            texts: List of texts to embed

        Returns:
            Dict mapping text to embedding vector
        """
        results = {}
        texts_to_compute = []

        # Check cache first
        for text in texts:
            cached = self._cache.get(text, self._provider.model_name)
            if cached:
                results[text] = cached.vector
            else:
                texts_to_compute.append(text)

        # Batch compute remaining
        if texts_to_compute:
            print(f"Computing embeddings for {len(texts_to_compute)} texts...")
            computed = self._provider.embed_batch(texts_to_compute)
            for result in computed:
                results[result.text] = result.vector
                self._cache.set(result)

        return results

    def get_patterns_by_category(self, category: str) -> List[PatternEntry]:
        """Get all patterns in a category.

        Args:
            category: Category name (action, outcome, boundary)

        Returns:
            List of PatternEntry objects
        """
        pattern_ids = self._category_index.get(category, [])
        return [self._patterns[pid] for pid in pattern_ids if pid in self._patterns]

    def get_all_patterns(self) -> List[PatternEntry]:
        """Get all loaded patterns."""
        return list(self._patterns.values())

    def get_pattern_by_id(self, pattern_id: str) -> Optional[PatternEntry]:
        """Get pattern by ID.

        Args:
            pattern_id: Pattern identifier

        Returns:
            PatternEntry or None if not found
        """
        return self._patterns.get(pattern_id)

    def get_category_embeddings(self, category: str) -> np.ndarray:
        """Get all embeddings for a category as numpy array.

        Useful for vectorized similarity computation.

        Args:
            category: Category name

        Returns:
            2D numpy array of shape (n_patterns, embedding_dim)
        """
        patterns = self.get_patterns_by_category(category)
        if not patterns:
            return np.array([])

        return np.array([p.embedding for p in patterns])

    def get_categories(self) -> List[str]:
        """Get list of all categories."""
        return list(self._category_index.keys())

    def search_by_text(self, text: str) -> Optional[PatternEntry]:
        """Find pattern by exact text match (canonical or synonym).

        Args:
            text: Text to search for

        Returns:
            PatternEntry if exact match found, None otherwise
        """
        text_lower = text.lower().strip()
        for pattern in self._patterns.values():
            if pattern.canonical.lower() == text_lower:
                return pattern
            for synonym in pattern.synonyms:
                if synonym.lower() == text_lower:
                    return pattern
        return None
