"""
Embedding provider interface for semantic AC parsing.

Defines abstract interface for embedding providers (OpenAI, sentence-transformers, etc.)
to enable semantic similarity matching in AC parsing.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    text: str
    vector: np.ndarray
    model: str
    dimensions: int
    usage: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (vector as list for serialization)."""
        return {
            "text": self.text,
            "vector": self.vector.tolist(),
            "model": self.model,
            "dimensions": self.dimensions,
            "usage": self.usage
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingResult":
        """Create from dictionary."""
        return cls(
            text=data["text"],
            vector=np.array(data["vector"]),
            model=data["model"],
            dimensions=data["dimensions"],
            usage=data.get("usage")
        )


@dataclass
class SimilarityMatch:
    """Result of similarity search."""
    pattern_id: str
    pattern_text: str
    category: str  # "action", "outcome", "boundary", "condition"
    similarity_score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_text": self.pattern_text,
            "category": self.category,
            "similarity_score": self.similarity_score,
            "metadata": self.metadata
        }


class IEmbeddingProvider(ABC):
    """Interface for embedding providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (e.g., 'openai', 'sentence-transformers')."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model being used (e.g., 'text-embedding-3-small')."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding vector dimensions."""

    @abstractmethod
    def embed(self, text: str) -> EmbeddingResult | None:
        """Generate embedding for single text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResult with vector or None on failure
        """

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of EmbeddingResults (may be shorter than input on failures)
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and reachable.

        Returns:
            True if provider can be used
        """


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Cosine similarity score (0-1, higher = more similar)
    """
    # Handle zero vectors
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(vec1, vec2) / (norm1 * norm2))
