"""
Embeddings module for semantic AC parsing.

Provides embedding-based semantic similarity matching to improve
acceptance criteria parsing beyond regex patterns.

Usage:
    from core.services.embeddings import (
        create_embedding_provider,
        EmbeddingCache,
        EmbeddingPatternIndex,
        SemanticMatcher
    )

    # Create provider
    provider = create_embedding_provider()

    # Generate embedding
    if provider and provider.is_available():
        result = provider.embed("User can bring object to front")
        print(f"Vector dimensions: {result.dimensions}")

    # Load pattern index
    cache = EmbeddingCache()
    index = EmbeddingPatternIndex(provider, cache)
    index.load_patterns()

    # Find similar patterns
    matcher = SemanticMatcher(provider, index, cache)
    matches = matcher.find_similar("move above other objects", category="action")
    print(f"Best match: {matches[0].pattern_text}")  # "bring to front"
"""
from .embedding_interface import (
    IEmbeddingProvider,
    EmbeddingResult,
    SimilarityMatch,
    cosine_similarity,
)
from .embedding_cache import EmbeddingCache
from .pattern_index import EmbeddingPatternIndex, PatternEntry
from .semantic_matcher import SemanticMatcher
from .providers import (
    OpenAIEmbeddingProvider,
    create_embedding_provider,
)

__all__ = [
    # Interfaces
    "IEmbeddingProvider",
    "EmbeddingResult",
    "SimilarityMatch",
    "cosine_similarity",
    # Cache
    "EmbeddingCache",
    # Pattern Index
    "EmbeddingPatternIndex",
    "PatternEntry",
    # Matcher
    "SemanticMatcher",
    # Providers
    "OpenAIEmbeddingProvider",
    "create_embedding_provider",
]
