"""
Anthropic Provider
LLM provider using the Anthropic Claude API (Claude Sonnet 5, Claude Opus 4.8, etc.)

Notes on current Claude models (Sonnet 5 / Opus 4.8 / Haiku 4.5):
- Sampling parameters (temperature/top_p/top_k) are rejected with a 400 on
  Sonnet 5 and Opus 4.8, so this provider never sends them. Callers may still
  pass temperature in kwargs; it is ignored.
- generate_json() supports native structured outputs: pass schema=<JSON schema>
  to guarantee valid JSON via output_config.format. Without a schema it falls
  back to instruction-based JSON with robust extraction.
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

    # Model aliases for convenience. Legacy Claude 3.x names are remapped to
    # current equivalents because the 3.x models are retired and would 404.
    MODELS = {
        "sonnet": "claude-sonnet-5",
        "opus": "claude-opus-4-8",
        "haiku": "claude-haiku-4-5",
        "claude-sonnet-5": "claude-sonnet-5",
        "claude-opus-4-8": "claude-opus-4-8",
        "claude-haiku-4-5": "claude-haiku-4-5",
        # Legacy aliases (retired models) -> current equivalents
        "claude-3-5-sonnet": "claude-sonnet-5",
        "claude-3-sonnet": "claude-sonnet-5",
        "claude-3-haiku": "claude-haiku-4-5",
        "claude-3-opus": "claude-opus-4-8",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-5",
        timeout: int = 120,
        max_retries: int = 2,
        max_tokens: int = 16000
    ):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model name or alias (claude-sonnet-5, claude-opus-4-8, sonnet, opus, haiku)
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
            **kwargs: Additional parameters (max_tokens, output_config).
                temperature is accepted for interface compatibility but NOT
                sent — current Claude models reject sampling parameters.

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

        request: Dict[str, Any] = {
            "model": self._model,
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            request["system"] = system_prompt
        if kwargs.get("output_config"):
            request["output_config"] = kwargs["output_config"]

        try:
            response = self.client.messages.create(**request)

            if response.stop_reason == "refusal":
                raise RuntimeError(
                    "Anthropic API refused the request (stop_reason=refusal)."
                )

            # Extract content (may be multiple content blocks)
            content = ""
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    content += block.text

            if response.stop_reason == "max_tokens":
                print(
                    f"  Warning: Claude hit max_tokens={request['max_tokens']} — "
                    "output may be truncated."
                )

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
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON response from Claude.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: Optional system prompt
            schema: Optional JSON schema. When provided, uses Claude's native
                structured outputs (output_config.format) which guarantees
                valid JSON matching the schema. Objects in the schema must set
                additionalProperties: false.
            **kwargs: Additional parameters (max_tokens; temperature ignored)

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If response is not valid JSON
        """
        if schema:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": schema}
            }
            response = self.generate(prompt, system_prompt, **kwargs)
            content = response.content.strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Failed to parse structured output from Claude: {e}\n"
                    f"Response content: {content[:500]}..."
                )

        # No schema: instruct for JSON and extract robustly
        json_system = system_prompt or ""
        if "json" not in json_system.lower():
            json_system = (
                f"{json_system}\n\n"
                "IMPORTANT: Respond with valid JSON only. "
                "Do not include any text before or after the JSON."
            ).strip()

        response = self.generate(prompt, json_system, **kwargs)
        content = self._extract_json_text(response.content)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse JSON from Claude response: {e}\n"
                f"Response content: {content[:500]}..."
            )

    @staticmethod
    def _extract_json_text(raw: str) -> str:
        """Extract a JSON payload from raw model output.

        Handles markdown code fences and surrounding prose by falling back to
        the outermost brace/bracket span.
        """
        content = raw.strip()

        # Strip markdown code fences
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # If it still doesn't look like bare JSON, take the outermost span
        if not (content.startswith("{") or content.startswith("[")):
            for open_ch, close_ch in (("{", "}"), ("[", "]")):
                start = content.find(open_ch)
                end = content.rfind(close_ch)
                if start != -1 and end > start:
                    return content[start:end + 1]

        return content

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
            temperature: Accepted for interface compatibility; not sent to the API
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
                max_tokens=max_tokens
            )

            return response.content.strip() if response.content else None

        except Exception as e:
            error_type = type(e).__name__
            print(f"Anthropic API error ({error_type}): {e}")
            return None

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Note: This is a local approximation (~4 chars/token). For exact counts
        use client.messages.count_tokens, which costs an API round-trip.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        return len(text) // 4
