"""
LLM Provider Factory
Creates LLM providers based on configuration.
"""
import os
from typing import Optional, Union
from .ollama import OllamaProvider
from .openai_provider import OpenAIProvider


def create_llm_provider(
    provider_type: str = "ollama",
    endpoint: str = "http://localhost:11434",
    model: Optional[str] = None,
    timeout: int = 30,
    max_retries: int = 2,
    api_key: Optional[str] = None
) -> Optional[Union[OllamaProvider, OpenAIProvider]]:
    """Create LLM provider based on configuration.

    Args:
        provider_type: Type of provider ('ollama' or 'openai')
        endpoint: API endpoint (used for Ollama)
        model: Model name (defaults based on provider)
        timeout: Request timeout in seconds
        max_retries: Maximum retries on failure
        api_key: API key (used for OpenAI, defaults to env var)

    Returns:
        LLM provider instance or None if unsupported type
    """
    provider = provider_type.lower()

    if provider == "ollama":
        return OllamaProvider(
            endpoint=endpoint,
            model=model or "llama3.2:3b",
            timeout=timeout,
            max_retries=max_retries
        )
    elif provider == "openai":
        return OpenAIProvider(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            model=model or "gpt-4o-mini",
            timeout=timeout,
            max_retries=max_retries
        )
    else:
        print(f"Unsupported LLM provider type: {provider_type}")
        print("Supported providers: 'ollama', 'openai'")
        return None
