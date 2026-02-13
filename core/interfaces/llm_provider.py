"""
LLM Provider interface for AI-powered test enhancement.

Abstracts LLM interactions to enable different providers (OpenAI, Ollama, etc.).
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 60


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class ILLMProvider(ABC):
    """Interface for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Model being used."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with generated content
        """
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON response.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dictionary
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured.

        Returns:
            True if provider can be used
        """
        pass


class ITestCaseCorrector(ABC):
    """Interface for LLM-based test case correction."""

    @abstractmethod
    def correct_test_cases(
        self,
        test_cases: List[Dict],
        story_id: str,
        feature_name: str,
        acceptance_criteria: List[str],
        qa_prep: Optional[str] = None
    ) -> List[Dict]:
        """Correct and enhance test cases using LLM.

        Args:
            test_cases: List of test case dictionaries
            story_id: Story identifier
            feature_name: Name of the feature
            acceptance_criteria: List of AC bullets
            qa_prep: Optional QA Prep content

        Returns:
            Corrected test cases
        """
        pass

    @abstractmethod
    def validate_and_fix(
        self,
        test_case: Dict,
        rules: Dict[str, Any]
    ) -> Dict:
        """Validate test case and fix issues using LLM.

        Args:
            test_case: Test case to validate
            rules: Validation rules to apply

        Returns:
            Fixed test case
        """
        pass
