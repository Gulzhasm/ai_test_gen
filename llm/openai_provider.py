"""
OpenAI Provider
LLM provider using OpenAI API (GPT-4o-mini, GPT-4o, etc.)
"""
import os
from typing import Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class OpenAIProvider:
    """LLM provider using OpenAI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: int = 30,
        max_retries: int = 2
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name to use (gpt-4o-mini, gpt-4o, etc.)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on failure
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> Optional[OpenAI]:
        """Lazy initialization of OpenAI client."""
        if self._client is None and OPENAI_AVAILABLE and self.api_key:
            self._client = OpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=self.max_retries
            )
        return self._client

    def rewrite_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Rewrite text using OpenAI.

        Args:
            prompt: The prompt containing context and text to rewrite
            temperature: Temperature for generation (lower = more deterministic)
            max_tokens: Maximum tokens to generate

        Returns:
            Rewritten text or None if generation fails
        """
        if not OPENAI_AVAILABLE:
            print("OpenAI package not installed. Install with: pip install openai")
            return None

        if not self.client:
            print("OpenAI client not initialized. Check OPENAI_API_KEY.")
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that rewrites and enhances text while preserving the original meaning and key information."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9
            )

            generated_text = response.choices[0].message.content
            return generated_text.strip() if generated_text else None

        except Exception as e:
            error_type = type(e).__name__
            print(f"OpenAI API error ({error_type}): {e}")
            return None

    def is_available(self) -> bool:
        """Check if OpenAI is available.

        Returns:
            True if OpenAI client is configured and API key is valid
        """
        if not OPENAI_AVAILABLE:
            print("OpenAI package not installed. Install with: pip install openai")
            return False

        if not self.api_key:
            print("OpenAI API key not set. Set OPENAI_API_KEY environment variable.")
            return False

        try:
            # Make a minimal API call to verify the key works
            client = self.client
            if not client:
                return False

            # List models to verify API key is valid
            client.models.list()
            return True

        except Exception as e:
            print(f"OpenAI API key validation failed: {e}")
            return False
