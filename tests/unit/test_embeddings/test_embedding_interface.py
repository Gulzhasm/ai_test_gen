"""Tests for embedding interface components."""
import numpy as np
import pytest

from core.services.embeddings.embedding_interface import (
    EmbeddingResult,
    SimilarityMatch,
    cosine_similarity
)


class TestCosineSimlarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self):
        """Identical vectors should have similarity of 1.0."""
        vec = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity of 0.0."""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity of -1.0."""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([-1.0, 0.0])
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_similar_vectors(self):
        """Similar vectors should have high similarity."""
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([1.1, 2.1, 3.1])
        similarity = cosine_similarity(vec1, vec2)
        assert similarity > 0.99

    def test_zero_vector_handling(self):
        """Zero vectors should return 0.0 similarity."""
        vec1 = np.array([0.0, 0.0])
        vec2 = np.array([1.0, 2.0])
        assert cosine_similarity(vec1, vec2) == 0.0

    def test_high_dimensional_vectors(self):
        """Should work with high-dimensional vectors (like 1536)."""
        vec1 = np.random.rand(1536)
        vec2 = np.random.rand(1536)
        similarity = cosine_similarity(vec1, vec2)
        assert -1.0 <= similarity <= 1.0


class TestEmbeddingResult:
    """Tests for EmbeddingResult dataclass."""

    def test_to_dict(self):
        """Should serialize to dictionary correctly."""
        result = EmbeddingResult(
            text="test text",
            vector=np.array([1.0, 2.0, 3.0]),
            model="test-model",
            dimensions=3,
            usage={"tokens": 5}
        )

        data = result.to_dict()

        assert data["text"] == "test text"
        assert data["vector"] == [1.0, 2.0, 3.0]
        assert data["model"] == "test-model"
        assert data["dimensions"] == 3
        assert data["usage"] == {"tokens": 5}

    def test_from_dict(self):
        """Should deserialize from dictionary correctly."""
        data = {
            "text": "test text",
            "vector": [1.0, 2.0, 3.0],
            "model": "test-model",
            "dimensions": 3,
            "usage": {"tokens": 5}
        }

        result = EmbeddingResult.from_dict(data)

        assert result.text == "test text"
        assert np.array_equal(result.vector, np.array([1.0, 2.0, 3.0]))
        assert result.model == "test-model"
        assert result.dimensions == 3
        assert result.usage == {"tokens": 5}

    def test_roundtrip_serialization(self):
        """Should survive roundtrip serialization."""
        original = EmbeddingResult(
            text="roundtrip test",
            vector=np.array([0.5, -0.5, 0.25]),
            model="test-model",
            dimensions=3
        )

        restored = EmbeddingResult.from_dict(original.to_dict())

        assert restored.text == original.text
        assert np.allclose(restored.vector, original.vector)
        assert restored.model == original.model
        assert restored.dimensions == original.dimensions


class TestSimilarityMatch:
    """Tests for SimilarityMatch dataclass."""

    def test_creation(self):
        """Should create with all fields."""
        match = SimilarityMatch(
            pattern_id="action_bring_to_front",
            pattern_text="bring to front",
            category="action",
            similarity_score=0.92,
            metadata={"subcategory": "z_order"}
        )

        assert match.pattern_id == "action_bring_to_front"
        assert match.pattern_text == "bring to front"
        assert match.category == "action"
        assert match.similarity_score == 0.92
        assert match.metadata["subcategory"] == "z_order"

    def test_to_dict(self):
        """Should serialize to dictionary."""
        match = SimilarityMatch(
            pattern_id="test",
            pattern_text="test pattern",
            category="action",
            similarity_score=0.85
        )

        data = match.to_dict()

        assert data["pattern_id"] == "test"
        assert data["pattern_text"] == "test pattern"
        assert data["category"] == "action"
        assert data["similarity_score"] == 0.85
