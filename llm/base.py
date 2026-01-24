"""
LLM Provider Base Interface
Protocol/interface for LLM providers.
"""
from typing import Protocol, Optional


class LLMProvider(Protocol):
    """Interface for LLM providers."""
    
    def rewrite_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Rewrite text based on prompt.
        
        Args:
            prompt: The prompt containing context and text to rewrite
            temperature: Temperature for generation (0.0-1.0, lower = more deterministic)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Rewritten text or None if generation fails
        """
        ...
    
    def is_available(self) -> bool:
        """Check if the LLM provider is available.
        
        Returns:
            True if provider can be used, False otherwise
        """
        ...
