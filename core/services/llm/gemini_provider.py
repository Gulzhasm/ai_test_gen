"""
Gemini Provider
LLM provider using Google Gemini API (gemini-2.0-flash, gemini-2.0-flash-lite, etc.)
"""
import json
import os
import time
import re
from typing import Any, Dict, List, Optional

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Fallback chain: if primary model is rate-limited, try these in order
FALLBACK_MODELS = {
    "gemini-2.0-flash": ["gemini-2.0-flash-lite"],
    "gemini-2.0-flash-lite": [],
}


class GeminiProvider:
    """LLM provider using Google Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        timeout: int = 90,
        max_retries: int = 1
    ):
        """Initialize Gemini provider.

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            model: Model name (gemini-2.0-flash, gemini-2.0-flash-lite, etc.)
            timeout: Request timeout in seconds
            max_retries: Maximum retries per model before trying fallback (default: 1)
        """
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = None
        self._fallback_models = FALLBACK_MODELS.get(model, [])

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    @property
    def client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None and GEMINI_AVAILABLE and self._api_key:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if an error is a rate limit (429) error."""
        error_str = str(error)
        return '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str

    def _get_retry_delay(self, error: Exception) -> float:
        """Extract retry delay from error message, or return default."""
        match = re.search(r'retry in (\d+\.?\d*)s', str(error))
        if match:
            return float(match.group(1))
        return 5.0

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs
    ) -> Optional[Dict]:
        """Generate text completion using Gemini.

        Tries primary model first, falls back to alternate models on rate limit.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            Dict with content, model, usage, finish_reason
        """
        if not GEMINI_AVAILABLE or not self.client:
            return None

        config = genai.types.GenerateContentConfig(
            system_instruction=system_prompt or "",
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # Try primary model with retries
        models_to_try = [self._model] + self._fallback_models
        for model_name in models_to_try:
            for attempt in range(self._max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )

                    content = response.text or ""
                    usage = {}
                    if response.usage_metadata:
                        usage = {
                            "prompt_tokens": response.usage_metadata.prompt_token_count or 0,
                            "completion_tokens": response.usage_metadata.candidates_token_count or 0,
                            "total_tokens": response.usage_metadata.total_token_count or 0
                        }

                    if model_name != self._model:
                        print(f"  Used fallback model: {model_name}")

                    return {
                        "content": content.strip(),
                        "model": model_name,
                        "usage": usage,
                        "finish_reason": "stop"
                    }

                except Exception as e:
                    if self._is_rate_limit_error(e) and attempt < self._max_retries:
                        delay = self._get_retry_delay(e)
                        print(f"  Gemini rate limited ({model_name}), retrying in {delay:.0f}s (attempt {attempt + 1}/{self._max_retries})...")
                        time.sleep(delay)
                        continue
                    elif self._is_rate_limit_error(e) and self._fallback_models:
                        print(f"  {model_name} rate limited after {self._max_retries} retries, trying fallback...")
                        break  # Break inner loop to try next model
                    else:
                        print(f"Gemini generation error: {e}")
                        return None

        print(f"Gemini generation failed: all models rate limited")
        return None

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 16000,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Generate JSON response from Gemini.

        Uses Gemini's native JSON response mode for reliable JSON output.
        Falls back to alternate models on rate limit.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: Optional system prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            Parsed JSON dictionary or None on failure
        """
        if not GEMINI_AVAILABLE or not self.client:
            return None

        config = genai.types.GenerateContentConfig(
            system_instruction=system_prompt or "",
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        )

        models_to_try = [self._model] + self._fallback_models
        for model_name in models_to_try:
            for attempt in range(self._max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )

                    content = response.text or ""
                    content = content.strip()

                    # Handle markdown code blocks (fallback)
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                    if model_name != self._model:
                        print(f"  Used fallback model: {model_name}")

                    return json.loads(content)

                except json.JSONDecodeError as e:
                    print(f"Gemini JSON parsing error: {e}")
                    # Fallback: try non-JSON mode
                    result = self.generate(prompt, system_prompt, temperature, max_tokens)
                    if result and result.get("content"):
                        try:
                            text = result["content"]
                            if text.startswith("```json"):
                                text = text[7:]
                            if text.startswith("```"):
                                text = text[3:]
                            if text.endswith("```"):
                                text = text[:-3]
                            return json.loads(text.strip())
                        except json.JSONDecodeError:
                            return None
                    return None
                except Exception as e:
                    if self._is_rate_limit_error(e) and attempt < self._max_retries:
                        delay = self._get_retry_delay(e)
                        print(f"  Gemini rate limited ({model_name}), retrying in {delay:.0f}s (attempt {attempt + 1}/{self._max_retries})...")
                        time.sleep(delay)
                        continue
                    elif self._is_rate_limit_error(e) and self._fallback_models:
                        print(f"  {model_name} rate limited after {self._max_retries} retries, trying fallback...")
                        break  # Break inner loop to try next model
                    else:
                        print(f"Gemini generation error: {e}")
                        return None

        print(f"Gemini generation failed: all models rate limited")
        return None

    def is_available(self) -> bool:
        """Check if Gemini is available and configured."""
        if not GEMINI_AVAILABLE:
            print("Google GenAI package not installed. Install with: pip install google-genai")
            return False
        if not self._api_key:
            print("Gemini API key not set. Set GEMINI_API_KEY environment variable.")
            return False
        return True

    def rewrite_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Rewrite text using Gemini (compatibility method)."""
        result = self.generate(
            prompt=prompt,
            system_prompt="You are a helpful assistant that rewrites and enhances text while preserving the original meaning.",
            temperature=temperature,
            max_tokens=max_tokens
        )
        return result["content"] if result else None
