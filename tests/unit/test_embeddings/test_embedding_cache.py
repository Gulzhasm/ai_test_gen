"""Tests for embedding cache."""
import tempfile
import numpy as np
import pytest
from datetime import timedelta

from core.services.embeddings.embedding_cache import EmbeddingCache
from core.services.embeddings.embedding_interface import EmbeddingResult


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create a cache with temporary directory."""
        return EmbeddingCache(cache_dir=str(tmp_path), max_entries=100)

    @pytest.fixture
    def sample_result(self):
        """Create a sample embedding result."""
        return EmbeddingResult(
            text="test text",
            vector=np.array([0.1, 0.2, 0.3, 0.4, 0.5]),
            model="test-model",
            dimensions=5,
            usage={"tokens": 3}
        )

    def test_set_and_get(self, cache, sample_result):
        """Should store and retrieve embeddings."""
        cache.set(sample_result)

        retrieved = cache.get("test text", "test-model")

        assert retrieved is not None
        assert retrieved.text == sample_result.text
        assert np.allclose(retrieved.vector, sample_result.vector)
        assert retrieved.model == sample_result.model

    def test_get_missing_key(self, cache):
        """Should return None for missing keys."""
        result = cache.get("nonexistent", "model")
        assert result is None

    def test_different_models_different_keys(self, cache, sample_result):
        """Same text with different model should be different cache entries."""
        # Store with model A
        cache.set(sample_result)

        # Try to get with model B
        result = cache.get("test text", "different-model")
        assert result is None

        # Get with correct model
        result = cache.get("test text", "test-model")
        assert result is not None

    def test_cache_hit_increments_stats(self, cache, sample_result):
        """Cache hits should increment hit counter."""
        cache.set(sample_result)

        initial_hits = cache.stats["hits"]
        cache.get("test text", "test-model")
        assert cache.stats["hits"] == initial_hits + 1

    def test_cache_miss_increments_stats(self, cache):
        """Cache misses should increment miss counter."""
        initial_misses = cache.stats["misses"]
        cache.get("nonexistent", "model")
        assert cache.stats["misses"] == initial_misses + 1

    def test_clear_removes_all_entries(self, cache, sample_result):
        """Clear should remove all entries."""
        cache.set(sample_result)
        assert cache.stats["size"] > 0

        cache.clear()

        assert cache.stats["size"] == 0
        assert cache.get("test text", "test-model") is None

    def test_max_entries_eviction(self, tmp_path):
        """Should evict oldest entries when at capacity."""
        cache = EmbeddingCache(cache_dir=str(tmp_path), max_entries=3)

        # Add 4 entries (exceeds max of 3)
        for i in range(4):
            result = EmbeddingResult(
                text=f"text_{i}",
                vector=np.array([float(i)]),
                model="model",
                dimensions=1
            )
            cache.set(result)

        # First entry should be evicted
        assert cache.get("text_0", "model") is None

        # Later entries should still exist
        assert cache.get("text_3", "model") is not None

    def test_batch_operations(self, cache):
        """Should support batch get and set."""
        results = [
            EmbeddingResult(
                text=f"text_{i}",
                vector=np.array([float(i)]),
                model="model",
                dimensions=1
            )
            for i in range(3)
        ]

        cache.set_batch(results)

        retrieved = cache.get_batch(["text_0", "text_1", "text_2"], "model")

        assert len(retrieved) == 3
        assert all(v is not None for v in retrieved.values())
