"""
LLM Provider Factory
Creates LLM providers based on configuration.
"""
import os

from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider
from .ollama import OllamaProvider
from .openai_provider import OpenAIProvider


def create_llm_provider(
    provider_type: str = "ollama",
    endpoint: str = "http://localhost:11434",
    model: str | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    api_key: str | None = None
) -> OllamaProvider | OpenAIProvider | AnthropicProvider | GeminiProvider | None:
    """Create LLM provider based on configuration.

    Args:
        provider_type: Type of provider ('ollama', 'openai', 'anthropic', or 'gemini')
        endpoint: API endpoint (used for Ollama)
        model: Model name (defaults based on provider)
        timeout: Request timeout in seconds
        max_retries: Maximum retries on failure
        api_key: API key (used for OpenAI/Anthropic/Gemini, defaults to env var)

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
    elif provider == "anthropic" or provider == "claude":
        return AnthropicProvider(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            model=model or "claude-opus-5-5",
            timeout=timeout,
            max_retries=max_retries
        )
    elif provider == "gemini" or provider == "google":
        return GeminiProvider(
            api_key=api_key or os.getenv("GEMINI_API_KEY"),
            model=model or "gemini-2.5-flash",
            timeout=timeout,
            max_retries=max_retries
        )
    else:
        print(f"Unsupported LLM provider type: {provider_type}")
        print("Supported providers: 'ollama', 'openai', 'anthropic', 'gemini'")
        return None
