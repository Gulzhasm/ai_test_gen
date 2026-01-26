"""
OpenAI Provider
LLM provider using OpenAI API (GPT-4o-mini, GPT-4o, etc.)

Implements humanistic prompt engineering for natural, professional test generation.
"""
import os
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class OpenAIProvider:
    """LLM provider using OpenAI API with humanistic prompt engineering."""

    # Default system prompt for test generation - writes like a senior QA engineer
    DEFAULT_SYSTEM_PROMPT = """You are a senior QA engineer with 10+ years of experience writing test cases.

Your writing style:
- Professional but approachable - write how you'd explain to a colleague
- Specific and actionable - every instruction should be immediately executable
- Concise - no filler words or unnecessary explanations
- Observable outcomes - describe what the tester will actually see

When writing test content:
- Use active voice: "Click Save" not "The Save button should be clicked"
- Name UI elements specifically: "Edit Menu", "Properties Panel", "Canvas"
- Describe visual feedback: "Dialog closes", "Button highlights", "List updates"
- Avoid: "works correctly", "functions as expected", "is successful"

Be deterministic - the same input should always produce the same high-quality output."""

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
        self._model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[OpenAI] = None

    @property
    def provider_name(self) -> str:
        """Name of the provider."""
        return "openai"

    @property
    def model(self) -> str:
        """Model being used."""
        return self._model

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

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
        **kwargs
    ) -> Optional[LLMResponse]:
        """Generate text completion.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (uses humanistic default if None)
            temperature: Temperature for generation (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            LLMResponse with generated content or None on failure
        """
        if not OPENAI_AVAILABLE or not self.client:
            return None

        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt or self.DEFAULT_SYSTEM_PROMPT
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

            content = response.choices[0].message.content
            return LLMResponse(
                content=content.strip() if content else "",
                model=self._model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                },
                finish_reason=response.choices[0].finish_reason
            )

        except Exception as e:
            print(f"OpenAI generation error: {e}")
            return None

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Generate JSON response.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: Optional system prompt
            temperature: Temperature (default lower for JSON consistency)
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dictionary or None on failure
        """
        # Add JSON instruction to system prompt
        json_system = (system_prompt or self.DEFAULT_SYSTEM_PROMPT) + "\n\nReturn ONLY valid JSON, no explanation."

        response = self.generate(
            prompt=prompt,
            system_prompt=json_system,
            temperature=temperature,
            **kwargs
        )

        if not response or not response.content:
            return None

        try:
            # Try to extract JSON from response
            content = response.content.strip()

            # Handle markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content

            return json.loads(content)

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return None

    def rewrite_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Rewrite text using OpenAI (legacy method for compatibility).

        Args:
            prompt: The prompt containing context and text to rewrite
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            Rewritten text or None if generation fails
        """
        response = self.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.content if response else None

    def is_available(self) -> bool:
        """Check if OpenAI is available and configured.

        Returns:
            True if provider can be used
        """
        if not OPENAI_AVAILABLE:
            return False

        if not self.api_key:
            return False

        return self.client is not None
