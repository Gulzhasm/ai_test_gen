"""
Embedding provider factory.

Creates embedding providers based on configuration.
"""
import os
from typing import Optional

from ..embedding_interface import IEmbeddingProvider
from .openai_embeddings import OpenAIEmbeddingProvider


def create_embedding_provider(
    provider_type: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[IEmbeddingProvider]:
    """Create embedding provider based on configuration.

    Args:
        provider_type: Provider type ("openai" or None for auto-detect)
        model: Model name (defaults based on provider)
        api_key: API key (for OpenAI)

    Returns:
        Configured embedding provider or None if unavailable

    Examples:
        # Auto-detect from environment
        provider = create_embedding_provider()

        # Explicit OpenAI
        provider = create_embedding_provider("openai", "text-embedding-3-small")

        # With custom API key
        provider = create_embedding_provider("openai", api_key="sk-...")
    """
    # Auto-detect provider from environment if not specified
    if provider_type is None:
        provider_type = os.getenv("EMBEDDING_PROVIDER", "openai")

    provider = provider_type.lower().strip()

    if provider == "openai":
        # Get model from env if not specified
        if model is None:
            model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        return OpenAIEmbeddingProvider(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            model=model
        )

    # Unknown provider
    print(f"Unknown embedding provider: {provider_type}")
    return None


def get_available_providers() -> dict:
    """Get information about available providers.

    Returns:
        Dict with provider availability status
    """
    providers = {}

    # Check OpenAI
    openai_provider = create_embedding_provider("openai")
    providers["openai"] = {
        "available": openai_provider.is_available() if openai_provider else False,
        "model": openai_provider.model_name if openai_provider else None,
        "dimensions": openai_provider.dimensions if openai_provider else None
    }

    return providers
