"""Tests for LLM providers."""
import pytest
from core.services.llm import OllamaProvider, create_llm_provider


def test_ollama_provider_initialization():
    """Test OllamaProvider initialization."""
    provider = OllamaProvider(
        endpoint="http://localhost:11434",
        model="llama3.2:3b",
        timeout=30
    )
    
    assert provider.endpoint == "http://localhost:11434"
    assert provider.model == "llama3.2:3b"
    assert provider.timeout == 30


def test_create_llm_provider_ollama():
    """Test factory creates Ollama provider."""
    provider = create_llm_provider(
        provider_type="ollama",
        endpoint="http://localhost:11434",
        model="llama3.2:3b"
    )
    
    assert provider is not None
    assert isinstance(provider, OllamaProvider)


def test_create_llm_provider_unsupported():
    """Test factory returns None for unsupported provider."""
    provider = create_llm_provider(
        provider_type="unsupported"
    )
    
    assert provider is None


@pytest.mark.skip(reason="Requires Ollama running")
def test_ollama_provider_rewrite():
    """Test OllamaProvider.rewrite_text() (requires Ollama running)."""
    provider = OllamaProvider()
    
    if not provider.is_available():
        pytest.skip("Ollama not available")
    
    prompt = "Rewrite this text to be more natural: The tool can be activated."
    result = provider.rewrite_text(prompt, temperature=0.3, max_tokens=100)
    
    assert result is not None
    assert len(result) > 0


@pytest.mark.skip(reason="Requires Ollama running")
def test_ollama_provider_is_available():
    """Test OllamaProvider.is_available() (requires Ollama running)."""
    provider = OllamaProvider()
    
    # This will return True/False depending on whether Ollama is running
    is_available = provider.is_available()
    
    assert isinstance(is_available, bool)
