"""
Quality Standards Interface - Defines test case quality metrics and thresholds.

Provides domain-agnostic quality evaluation criteria.
"""
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Protocol, List, Dict, Optional
from enum import Enum


class QualityLevel(Enum):
    """Quality assessment levels."""
    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"            # 70-89%
    ACCEPTABLE = "acceptable"  # 50-69%
    POOR = "poor"            # 30-49%
    UNACCEPTABLE = "unacceptable"  # 0-29%


@dataclass
class StepQualityMetrics:
    """Quality metrics for a single test step."""
    action_specificity: float  # 0-1: How specific is the action?
    expected_observability: float  # 0-1: How observable is the expected result?
    has_generic_phrases: bool  # Contains "works as expected", "perform action", etc.
    action_length: int  # Character count
    expected_length: int  # Character count
    issues: List[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Calculate overall step quality score."""
        base = (self.action_specificity * 0.4 + self.expected_observability * 0.4)
        penalty = 0.3 if self.has_generic_phrases else 0
        return max(0, min(1, base * 0.8 + 0.2 - penalty))


@dataclass
class TestCaseQualityMetrics:
    """Quality metrics for a complete test case."""
    title_quality: float  # 0-1: Title follows pattern and is descriptive
    step_metrics: List[StepQualityMetrics] = field(default_factory=list)
    has_prereq: bool = False
    has_launch: bool = False
    has_close: bool = False
    has_verification_steps: bool = False
    objective_quality: float = 0.0
    issues: List[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Calculate overall test case quality score."""
        if not self.step_metrics:
            return 0.0

        # Step quality average
        step_avg = sum(s.overall_score for s in self.step_metrics) / len(self.step_metrics)

        # Structure bonuses
        structure_score = 0.0
        if self.has_prereq:
            structure_score += 0.15
        if self.has_launch:
            structure_score += 0.15
        if self.has_close:
            structure_score += 0.1
        if self.has_verification_steps:
            structure_score += 0.2

        # Weighted combination
        return (
            self.title_quality * 0.15 +
            step_avg * 0.45 +
            structure_score * 0.25 +
            self.objective_quality * 0.15
        )

    @property
    def quality_level(self) -> QualityLevel:
        """Get quality level based on overall score."""
        score = self.overall_score
        if score >= 0.9:
            return QualityLevel.EXCELLENT
        elif score >= 0.7:
            return QualityLevel.GOOD
        elif score >= 0.5:
            return QualityLevel.ACCEPTABLE
        elif score >= 0.3:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNACCEPTABLE


@dataclass
class QualityIssue:
    """Represents a quality issue found in a test case."""
    severity: str  # "critical", "major", "minor"
    location: str  # "title", "step_3_action", "step_5_expected", "objective"
    description: str
    suggestion: Optional[str] = None


@dataclass
class CorrectionResult:
    """Result of LLM correction for a test case."""
    original_test: Dict
    corrected_test: Dict
    changes_made: List[str]
    quality_before: float
    quality_after: float
    confidence: float  # 0-1: How confident is the correction


class IQualityAnalyzer(Protocol):
    """Interface for test case quality analysis."""

    @abstractmethod
    def analyze_test_case(self, test_case: Dict) -> TestCaseQualityMetrics:
        """
        Analyze quality of a single test case.

        Args:
            test_case: Test case dictionary with id, title, steps, objective

        Returns:
            Quality metrics for the test case
        """
        ...

    @abstractmethod
    def analyze_step(self, action: str, expected: str) -> StepQualityMetrics:
        """
        Analyze quality of a single test step.

        Args:
            action: Step action text
            expected: Expected result text

        Returns:
            Quality metrics for the step
        """
        ...

    @abstractmethod
    def find_issues(self, test_case: Dict) -> List[QualityIssue]:
        """
        Find quality issues in a test case.

        Args:
            test_case: Test case dictionary

        Returns:
            List of quality issues found
        """
        ...


class ITestCorrector(Protocol):
    """Interface for LLM-based test case correction."""

    @abstractmethod
    def correct_test_case(
        self,
        test_case: Dict,
        quality_metrics: TestCaseQualityMetrics,
        feature_context: Optional[str] = None
    ) -> CorrectionResult:
        """
        Correct a test case using LLM.

        Args:
            test_case: Test case to correct
            quality_metrics: Quality analysis results
            feature_context: Optional context about the feature

        Returns:
            Correction result with improved test case
        """
        ...

    @abstractmethod
    def enhance_step(
        self,
        action: str,
        expected: str,
        feature_name: str,
        step_context: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Enhance a single step using LLM.

        Args:
            action: Original action text
            expected: Original expected result
            feature_name: Name of the feature being tested
            step_context: Optional context about the step

        Returns:
            Enhanced step with action and expected keys
        """
        ...


# Quality threshold constants
QUALITY_THRESHOLDS = {
    "min_action_length": 15,
    "min_expected_length": 10,
    "max_action_length": 200,
    "max_expected_length": 150,
    "min_verification_steps": 1,
    "min_total_steps": 4,
    "max_total_steps": 20,
}

# Generic phrases that indicate poor quality
GENERIC_PHRASES = [
    "works as expected",
    "perform the action described",
    "perform action",
    "verify functionality",
    "works correctly",
    "should work",
    "is completed successfully",
    "as expected",
    "as described",
    "the feature works",
    "the action is performed",
]

# Patterns for high-quality steps
HIGH_QUALITY_PATTERNS = {
    "action_verbs": [
        "click", "select", "enter", "type", "navigate", "open", "close",
        "verify", "confirm", "check", "expand", "collapse", "drag", "drop",
        "enable", "disable", "toggle", "submit", "save", "cancel", "apply",
        "scroll", "zoom", "pan", "rotate", "resize", "move", "copy", "paste",
    ],
    "specific_objects": [
        "button", "field", "input", "menu", "panel", "dialog", "option",
        "checkbox", "dropdown", "list", "table", "cell", "row", "column",
        "tab", "window", "link", "label", "icon", "tooltip", "message",
    ],
    "observable_outcomes": [
        "is displayed", "is visible", "appears", "shows", "opens", "closes",
        "is enabled", "is disabled", "is selected", "is highlighted",
        "is flagged", "contains", "displays", "indicates", "updates",
        "changes to", "moves to", "returns to", "persists", "remains",
    ],
}
