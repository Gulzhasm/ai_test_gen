"""
Judge Interface - Defines the contract for LLM-based test case validation.

The Judge is a cross-validation layer that uses a DIFFERENT LLM provider
than the generator to catch issues the generator misses. It evaluates
ALL test cases together (not per-test) to detect cross-test issues
like duplicates and missing AC coverage.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class IssueSeverity(Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class IssueCategory(Enum):
    """9 issue categories for test case validation."""
    FORBIDDEN_LANGUAGE = "forbidden_language"
    HALLUCINATED_CONTENT = "hallucinated_content"
    LOGICAL_CONTRADICTION = "logical_contradiction"
    MISSING_AC_COVERAGE = "missing_ac_coverage"
    DUPLICATE_OVERLAP = "duplicate_overlap"
    MISSING_SETUP = "missing_setup"
    INCONSISTENT_TERMINOLOGY = "inconsistent_terminology"
    INCONSISTENT_STEP_STRUCTURE = "inconsistent_step_structure"
    EMPTY_EXPECTED_RESULT = "empty_expected_result"


# Map categories to their default severity
CATEGORY_SEVERITY = {
    IssueCategory.FORBIDDEN_LANGUAGE: IssueSeverity.CRITICAL,
    IssueCategory.HALLUCINATED_CONTENT: IssueSeverity.CRITICAL,
    IssueCategory.LOGICAL_CONTRADICTION: IssueSeverity.MAJOR,
    IssueCategory.MISSING_AC_COVERAGE: IssueSeverity.MAJOR,
    IssueCategory.INCONSISTENT_STEP_STRUCTURE: IssueSeverity.MAJOR,
    IssueCategory.DUPLICATE_OVERLAP: IssueSeverity.MINOR,
    IssueCategory.MISSING_SETUP: IssueSeverity.MINOR,
    IssueCategory.INCONSISTENT_TERMINOLOGY: IssueSeverity.MINOR,
    IssueCategory.EMPTY_EXPECTED_RESULT: IssueSeverity.MINOR,
}


@dataclass
class JudgeIssue:
    """A single issue found by the Judge."""
    test_case_id: str
    category: IssueCategory
    severity: IssueSeverity
    description: str
    violating_text: str = ""
    suggested_fix: Optional[str] = None
    location: str = ""  # e.g., "step_3_action", "title"


@dataclass
class JudgeVerdict:
    """Result of judging the full test suite."""
    passed: bool = True
    total_issues: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    issues: List[JudgeIssue] = field(default_factory=list)
    ac_coverage: Dict[str, bool] = field(default_factory=dict)
    duplicate_groups: List[List[str]] = field(default_factory=list)
    corrected_test_cases: Optional[List[Dict]] = None
    rounds_used: int = 0

    def to_dict(self) -> Dict:
        """Serialize verdict for JSON output."""
        return {
            "passed": self.passed,
            "total_issues": self.total_issues,
            "critical_count": self.critical_count,
            "major_count": self.major_count,
            "minor_count": self.minor_count,
            "rounds_used": self.rounds_used,
            "issues": [
                {
                    "test_case_id": issue.test_case_id,
                    "category": issue.category.value,
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "violating_text": issue.violating_text,
                    "suggested_fix": issue.suggested_fix,
                    "location": issue.location,
                }
                for issue in self.issues
            ],
            "ac_coverage": self.ac_coverage,
            "duplicate_groups": self.duplicate_groups,
        }


class IJudge(ABC):
    """Interface for LLM-based test case validation (Judge layer)."""

    @abstractmethod
    def evaluate(
        self,
        test_cases: List[Dict],
        story_data: Dict,
        acceptance_criteria: List[str],
        app_config,
        rules,
    ) -> JudgeVerdict:
        """Evaluate ALL test cases against story context and rules."""
        pass

    @abstractmethod
    def fix_issues(
        self,
        test_cases: List[Dict],
        verdict: JudgeVerdict,
        story_data: Dict,
        acceptance_criteria: List[str],
        app_config,
    ) -> List[Dict]:
        """Fix issues found during evaluation. Returns corrected test cases."""
        pass
