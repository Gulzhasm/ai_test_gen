"""
Validator interfaces for test case quality assurance.

Abstracts validation logic to enable configurable quality gates.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    suggestion: Optional[str] = None


class IValidator(ABC):
    """Interface for test case validation."""

    @abstractmethod
    def validate(self, test_case: Dict) -> List[ValidationResult]:
        """Validate a single test case.

        Args:
            test_case: Test case dictionary to validate

        Returns:
            List of validation results
        """
        pass

    @abstractmethod
    def validate_batch(self, test_cases: List[Dict]) -> Dict[str, List[ValidationResult]]:
        """Validate multiple test cases.

        Args:
            test_cases: List of test case dictionaries

        Returns:
            Dict mapping test case IDs to their validation results
        """
        pass

    @abstractmethod
    def is_valid(self, test_case: Dict) -> bool:
        """Check if test case passes all validations.

        Args:
            test_case: Test case dictionary

        Returns:
            True if no ERROR severity issues found
        """
        pass


class IQualityGate(ABC):
    """Interface for quality gate rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the quality gate."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this gate checks."""
        pass

    @abstractmethod
    def check(self, test_case: Dict) -> ValidationResult:
        """Run the quality gate check.

        Args:
            test_case: Test case dictionary

        Returns:
            ValidationResult with check outcome
        """
        pass


class ITitleValidator(IQualityGate):
    """Interface for title format validation."""

    @abstractmethod
    def validate_format(self, title: str, story_id: int) -> ValidationResult:
        """Validate title follows correct format.

        Args:
            title: Test case title
            story_id: Associated story ID

        Returns:
            ValidationResult
        """
        pass


class IStepValidator(IQualityGate):
    """Interface for step validation."""

    @abstractmethod
    def validate_step_count(self, steps: List[Dict]) -> ValidationResult:
        """Validate step count is within bounds.

        Args:
            steps: List of test steps

        Returns:
            ValidationResult
        """
        pass

    @abstractmethod
    def validate_first_step(self, steps: List[Dict]) -> ValidationResult:
        """Validate first step is a prerequisite.

        Args:
            steps: List of test steps

        Returns:
            ValidationResult
        """
        pass

    @abstractmethod
    def validate_last_step(self, steps: List[Dict]) -> ValidationResult:
        """Validate last step is close/exit.

        Args:
            steps: List of test steps

        Returns:
            ValidationResult
        """
        pass


class IContentValidator(IQualityGate):
    """Interface for content validation (forbidden words, etc.)."""

    @abstractmethod
    def validate_no_forbidden_words(self, text: str) -> ValidationResult:
        """Check text doesn't contain forbidden words.

        Args:
            text: Text to check

        Returns:
            ValidationResult with any found forbidden words
        """
        pass

    @abstractmethod
    def validate_area_term(self, area: str) -> ValidationResult:
        """Validate area term is allowed.

        Args:
            area: Area term to validate

        Returns:
            ValidationResult
        """
        pass
