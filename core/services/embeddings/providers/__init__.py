"""
Embedding providers package.

Available providers:
- OpenAIEmbeddingProvider: Uses OpenAI text-embedding-3-small/large
"""
from .openai_embeddings import OpenAIEmbeddingProvider
from .provider_factory import create_embedding_provider

__all__ = [
    "OpenAIEmbeddingProvider",
    "create_embedding_provider",
]
