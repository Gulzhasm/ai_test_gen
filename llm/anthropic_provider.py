"""
Anthropic Provider
LLM provider using Anthropic Claude API (Claude 3.5 Sonnet, Claude 3 Haiku, etc.)
"""
import json
import os
from typing import Any, Dict, Optional

from core.interfaces.llm_provider import ILLMProvider, LLMResponse

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AnthropicProvider(ILLMProvider):
    """LLM provider using Anthropic Claude API."""

    # Model aliases for convenience
    MODELS = {
        "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3-haiku": "claude-3-haiku-20240307",
        "claude-3-opus": "claude-3-opus-20240229",
        "sonnet": "claude-3-5-sonnet-20241022",
        "haiku": "claude-3-haiku-20240307",
        "opus": "claude-3-opus-20240229",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet",
        timeout: int = 60,
        max_retries: int = 2,
        max_tokens: int = 4096
    ):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model name to use (claude-3-5-sonnet, claude-3-haiku, etc.)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on failure
            max_tokens: Default max tokens for generation
        """
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._model_alias = model
        self._model = self.MODELS.get(model, model)  # Resolve alias or use as-is
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_tokens = max_tokens
        self._client: Optional["anthropic.Anthropic"] = None

    @property
    def provider_name(self) -> str:
        """Name of the provider."""
        return "anthropic"

    @property
    def model(self) -> str:
        """Model being used."""
        return self._model

    @property
    def client(self) -> Optional["anthropic.Anthropic"]:
        """Lazy initialization of Anthropic client."""
        if self._client is None and ANTHROPIC_AVAILABLE and self._api_key:
            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=self._timeout,
                max_retries=self._max_retries
            )
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion using Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters (temperature, max_tokens)

        Returns:
            LLMResponse with generated content

        Raises:
            RuntimeError: If client not initialized
        """
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

        if not self.client:
            raise RuntimeError(
                "Anthropic client not initialized. Check ANTHROPIC_API_KEY."
            )

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.client.messages.create(
                model=self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                system=system_prompt or "",
                messages=messages,
                temperature=kwargs.get("temperature", 0.3)
            )

            # Extract content (may be multiple content blocks)
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            # Build usage dict
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }

            return LLMResponse(
                content=content,
                model=self._model,
                usage=usage,
                finish_reason=response.stop_reason
            )

        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic API error: {e}")

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON response from Claude.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If response is not valid JSON
        """
        # Enhance system prompt to request JSON
        json_system = system_prompt or ""
        if "json" not in json_system.lower():
            json_system = (
                f"{json_system}\n\n"
                "IMPORTANT: Respond with valid JSON only. "
                "Do not include any text before or after the JSON."
            ).strip()

        response = self.generate(prompt, json_system, **kwargs)

        # Extract JSON from response
        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse JSON from Claude response: {e}\n"
                f"Response content: {content[:500]}..."
            )

    def is_available(self) -> bool:
        """Check if Anthropic is available and configured.

        Returns:
            True if provider can be used
        """
        if not ANTHROPIC_AVAILABLE:
            print("Anthropic package not installed. Install with: pip install anthropic")
            return False

        if not self._api_key:
            print("Anthropic API key not set. Set ANTHROPIC_API_KEY environment variable.")
            return False

        return True

    def rewrite_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Rewrite text using Claude (compatibility method).

        Args:
            prompt: The prompt containing context and text to rewrite
            temperature: Temperature for generation (lower = more deterministic)
            max_tokens: Maximum tokens to generate

        Returns:
            Rewritten text or None if generation fails
        """
        if not self.is_available():
            return None

        try:
            system_prompt = (
                "You are a helpful assistant that rewrites and enhances text "
                "while preserving the original meaning and key information."
            )

            response = self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.content.strip() if response.content else None

        except Exception as e:
            error_type = type(e).__name__
            print(f"Anthropic API error ({error_type}): {e}")
            return None

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Note: This is an approximation. Anthropic doesn't provide
        a public tokenizer, so we use a rough estimate.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 characters per token for English text
        return len(text) // 4
