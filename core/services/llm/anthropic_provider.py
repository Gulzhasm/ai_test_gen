"""
Anthropic Provider
LLM provider using the Anthropic Claude API (Claude Opus 5.5, Claude Sonnet 5.5, Claude Fable 5.1, ...).

Request shape for current Claude models:
- Thinking is adaptive and always on for Opus 5.5 / Sonnet 5.5 / Fable 5.1; depth is set with
  output_config.effort. Opus 5.5 defaults to "medium", so this provider sends an explicit effort
  (default "high", override with ANTHROPIC_EFFORT or the effort= argument).
- Sampling parameters (temperature/top_p/top_k) are rejected on current models, so they are never
  sent. Callers may still pass temperature; it is ignored.
- Thinking tokens count toward max_tokens, so a floor (ANTHROPIC_MIN_OUTPUT_TOKENS, default 32000)
  protects callers that pass small budgets, and requests above 16000 tokens are streamed to stay
  clear of HTTP timeouts.
- Refusals: on Opus 5.5 / Sonnet 5.5 / Fable 5.1 the server-side fallback ("fallbacks": "default",
  beta server-side-fallback-2026-07-01) re-runs a declined request on Anthropic's recommended
  fallback model. Disable with ANTHROPIC_FALLBACKS=off.
- Prompt caching: top-level cache_control caches the request prefix (the large, stable system
  prompt), so repeated stories in one session pay for it once.
- generate_json() supports native structured outputs: pass schema=<JSON schema> to guarantee valid
  JSON via output_config.format. Without a schema it falls back to instruction-based JSON with
  robust extraction.
"""
import json
import os
from typing import Any, Optional

from core.interfaces.llm_provider import ILLMProvider, LLMResponse

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models whose request surface supports effort + server-side fallbacks ("default" form).
_CURRENT_GEN = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1")
_EFFORT_LEVELS = {"low", "medium", "high", "xhigh", "max"}


class AnthropicProvider(ILLMProvider):
    """LLM provider using Anthropic Claude API."""

    # Aliases resolve to current models. Retired names map to current equivalents so old
    # configs keep working instead of failing with 404.
    MODELS = {
        "opus": "claude-opus-5-5",
        "sonnet": "claude-sonnet-5-5",
        "haiku": "claude-haiku-5-5",
        "fable": "claude-fable-5-1",
        # Previous generations kept as explicit IDs
        "claude-sonnet-5": "claude-sonnet-5",
        "claude-opus-4-8": "claude-opus-4-8",
        "claude-haiku-4-5": "claude-haiku-4-5",
        # Retired models -> current equivalents
        "claude-3-5-sonnet": "claude-sonnet-5-5",
        "claude-3-sonnet": "claude-sonnet-5-5",
        "claude-3-haiku": "claude-haiku-5-5",
        "claude-3-opus": "claude-opus-5-5",
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-opus-5-5",
        timeout: int = 120,
        max_retries: int = 2,
        max_tokens: int = 32000,
        effort: str | None = None,
    ):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY; without it the SDK's own
                credential chain is not used here, so set the key or an auth profile env var)
            model: Model id or alias (opus, sonnet, haiku, fable)
            timeout: Request timeout in seconds (streamed requests use at least 600)
            max_retries: SDK retries for 408/409/429/5xx and connection errors
            max_tokens: Default output budget (thinking included)
            effort: low | medium | high | xhigh | max (default: ANTHROPIC_EFFORT or "high")
        """
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._model_alias = model
        self._model = self.MODELS.get(model, model)
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_tokens = max_tokens
        effort = (effort or os.getenv("ANTHROPIC_EFFORT") or "high").lower()
        self._effort = effort if effort in _EFFORT_LEVELS else "high"
        self._min_output = int(os.getenv("ANTHROPIC_MIN_OUTPUT_TOKENS", "32000"))
        self._fallbacks = os.getenv("ANTHROPIC_FALLBACKS", "default").lower() not in ("off", "false", "0", "")
        self._client: anthropic.Anthropic | None = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    @property
    def _is_current_gen(self) -> bool:
        return self._model.startswith(_CURRENT_GEN)

    @property
    def client(self) -> Optional["anthropic.Anthropic"]:
        """Lazy initialization of Anthropic client."""
        if self._client is None and ANTHROPIC_AVAILABLE and self._api_key:
            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=max(self._timeout, 600),
                max_retries=self._max_retries
            )
        return self._client

    def _build_request(self, prompt: str, system_prompt: str | None, kwargs: dict) -> dict[str, Any]:
        max_tokens = int(kwargs.get("max_tokens") or self._max_tokens)
        if self._is_current_gen:
            max_tokens = max(max_tokens, self._min_output)
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            # Cache the stable prefix (system prompt + rules); verify with usage.cache_read_input_tokens
            "cache_control": {"type": "ephemeral"},
        }
        if system_prompt:
            request["system"] = system_prompt
        output_config = dict(kwargs.get("output_config") or {})
        if self._is_current_gen:
            output_config.setdefault("effort", kwargs.get("effort") or self._effort)
        if output_config:
            request["output_config"] = output_config
        return request

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion using Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: max_tokens, output_config, effort. temperature is accepted for interface
                compatibility but NOT sent - current Claude models reject sampling parameters.
        """
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("Anthropic package not installed. Install with: pip install anthropic")
        if not self.client:
            raise RuntimeError("Anthropic client not initialized. Check ANTHROPIC_API_KEY.")

        request = self._build_request(prompt, system_prompt, kwargs)
        use_fallbacks = self._fallbacks and self._is_current_gen

        try:
            if use_fallbacks or request["max_tokens"] > 16000:
                extra: dict[str, Any] = {}
                if use_fallbacks:
                    extra = {"betas": [_FALLBACK_BETA], "extra_body": {"fallbacks": "default"}}
                with self.client.beta.messages.stream(**request, **extra) as stream:
                    response = stream.get_final_message()
            else:
                response = self.client.messages.create(**request)
        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic API error: {e}") from e

        if response.stop_reason == "refusal":
            category = getattr(getattr(response, "stop_details", None), "category", None)
            raise RuntimeError(f"Anthropic API refused the request (stop_reason=refusal, category={category}).")

        content = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")

        if response.stop_reason == "max_tokens":
            print(f"  Warning: Claude hit max_tokens={request['max_tokens']} - output may be truncated.")

        usage = response.usage
        usage_dict = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.input_tokens + usage.output_tokens,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        }
        return LLMResponse(
            content=content,
            model=getattr(response, "model", self._model),
            usage=usage_dict,
            finish_reason=response.stop_reason,
        )

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema: dict[str, Any] | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Generate JSON response from Claude.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: Optional system prompt
            schema: Optional JSON schema. When provided, uses native structured outputs
                (output_config.format), which guarantees valid JSON matching the schema.
                Objects in the schema must set additionalProperties: false.
            **kwargs: max_tokens, effort (temperature ignored)
        """
        if schema:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
            response = self.generate(prompt, system_prompt, **kwargs)
            content = response.content.strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse structured output from Claude: {e}\n"
                                 f"Response content: {content[:500]}...") from e

        json_system = system_prompt or ""
        if "json" not in json_system.lower():
            json_system = (f"{json_system}\n\nIMPORTANT: Respond with valid JSON only. "
                           "Do not include any text before or after the JSON.").strip()

        response = self.generate(prompt, json_system, **kwargs)
        content = self._extract_json_text(response.content)
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from Claude response: {e}\n"
                             f"Response content: {content[:500]}...") from e

    @staticmethod
    def _extract_json_text(raw: str) -> str:
        """Extract a JSON payload from raw model output (code fences, surrounding prose)."""
        content = raw.strip()
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        if not (content.startswith("{") or content.startswith("[")):
            for open_ch, close_ch in (("{", "}"), ("[", "]")):
                start, end = content.find(open_ch), content.rfind(close_ch)
                if start != -1 and end > start:
                    return content[start:end + 1]
        return content

    def is_available(self) -> bool:
        if not ANTHROPIC_AVAILABLE:
            print("Anthropic package not installed. Install with: pip install anthropic")
            return False
        if not self._api_key:
            print("Anthropic API key not set. Set ANTHROPIC_API_KEY environment variable.")
            return False
        return True

    def rewrite_text(self, prompt: str, temperature: float = 0.3, max_tokens: int = 500) -> str | None:
        """Rewrite text using Claude (compatibility method; temperature is not sent)."""
        if not self.is_available():
            return None
        try:
            response = self.generate(
                prompt=prompt,
                system_prompt=("You are a helpful assistant that rewrites and enhances text "
                               "while preserving the original meaning and key information."),
                max_tokens=max_tokens,
                effort="low",
            )
            return response.content.strip() if response.content else None
        except Exception as e:  # noqa: BLE001
            print(f"Anthropic API error ({type(e).__name__}): {e}")
            return None

    def count_tokens(self, text: str) -> int:
        """Local estimate (~4 chars/token); use client.messages.count_tokens for exact counts."""
        return len(text) // 4
