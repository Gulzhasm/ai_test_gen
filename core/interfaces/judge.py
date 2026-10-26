"""
Judge Interface - Defines the contract for LLM-based test case validation.

The Judge is a cross-validation layer that uses a DIFFERENT LLM provider
than the generator to catch issues the generator misses. It evaluates
ALL test cases together (not per-test) to detect cross-test issues
like duplicates and missing AC coverage.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class IssueSeverity(Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class IssueCategory(Enum):
    """Issue categories for test case validation.

    The judge prompt lists its categories from this enum, so a category added
    here is automatically offered to the model and accepted by the parser.
    """
    FORBIDDEN_LANGUAGE = "forbidden_language"
    HALLUCINATED_CONTENT = "hallucinated_content"
    LOGICAL_CONTRADICTION = "logical_contradiction"
    MISSING_AC_COVERAGE = "missing_ac_coverage"
    DUPLICATE_OVERLAP = "duplicate_overlap"
    MISSING_SETUP = "missing_setup"
    INCONSISTENT_TERMINOLOGY = "inconsistent_terminology"
    INCONSISTENT_STEP_STRUCTURE = "inconsistent_step_structure"
    EMPTY_EXPECTED_RESULT = "empty_expected_result"
    VERIFY_IN_ACTION = "verify_in_action"
    # Name kept for compatibility: means "the configured context setup step is missing"
    MISSING_CREATE_FILE = "missing_create_file"
    UNDO_REDO_COMBINED = "undo_redo_combined"
    AMBIGUOUS_EXPECTED_RESULT = "ambiguous_expected_result"
    UNVERIFIABLE_EXPECTED_RESULT = "unverifiable_expected_result"
    # Reviewer rules (see core/services/quality/qa_rules_checker.py)
    TEAM_WORK_STEP = "team_work_step"          # confirm/agree/approve/check-documented steps
    DATABASE_CHANGE = "database_change"        # QA asked to change, restore or break the database
    LETTERED_ROLE = "lettered_role"            # Admin A, User N, P1, Pwd-Old...
    INLINE_COMMENT = "inline_comment"          # TBD, to be confirmed, bracket notes in test text
    OTHER = "other"


# Map categories to their default severity (used when the model omits one)
CATEGORY_SEVERITY = {
    IssueCategory.FORBIDDEN_LANGUAGE: IssueSeverity.CRITICAL,
    IssueCategory.HALLUCINATED_CONTENT: IssueSeverity.CRITICAL,
    IssueCategory.LOGICAL_CONTRADICTION: IssueSeverity.MAJOR,
    IssueCategory.MISSING_AC_COVERAGE: IssueSeverity.MAJOR,
    IssueCategory.INCONSISTENT_STEP_STRUCTURE: IssueSeverity.MAJOR,
    IssueCategory.EMPTY_EXPECTED_RESULT: IssueSeverity.MAJOR,
    IssueCategory.MISSING_CREATE_FILE: IssueSeverity.MAJOR,
    IssueCategory.AMBIGUOUS_EXPECTED_RESULT: IssueSeverity.MAJOR,
    IssueCategory.UNVERIFIABLE_EXPECTED_RESULT: IssueSeverity.MAJOR,
    IssueCategory.DATABASE_CHANGE: IssueSeverity.CRITICAL,
    IssueCategory.TEAM_WORK_STEP: IssueSeverity.MAJOR,
    IssueCategory.LETTERED_ROLE: IssueSeverity.MAJOR,
    IssueCategory.INLINE_COMMENT: IssueSeverity.MAJOR,
    IssueCategory.DUPLICATE_OVERLAP: IssueSeverity.MINOR,
    IssueCategory.MISSING_SETUP: IssueSeverity.MINOR,
    IssueCategory.INCONSISTENT_TERMINOLOGY: IssueSeverity.MINOR,
    IssueCategory.VERIFY_IN_ACTION: IssueSeverity.MINOR,
    IssueCategory.UNDO_REDO_COMBINED: IssueSeverity.MINOR,
    IssueCategory.OTHER: IssueSeverity.MINOR,
}

_SEVERITY_WEIGHT = {IssueSeverity.CRITICAL: 10, IssueSeverity.MAJOR: 3, IssueSeverity.MINOR: 1}
_UNCOVERED_AC_WEIGHT = 5


@dataclass
class JudgeIssue:
    """A single issue found by the Judge."""
    test_case_id: str
    category: IssueCategory
    severity: IssueSeverity
    description: str
    violating_text: str = ""
    suggested_fix: str | None = None
    location: str = ""  # e.g., "step_3_action", "title"


@dataclass
class JudgeVerdict:
    """Result of judging the full test suite.

    ``evaluated`` is False when the judge could not produce a verdict (call
    failed, unparseable response). Such a verdict never counts as a pass.
    """
    passed: bool = True
    total_issues: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    issues: list[JudgeIssue] = field(default_factory=list)
    ac_coverage: dict[str, bool] = field(default_factory=dict)
    duplicate_groups: list[list[str]] = field(default_factory=list)
    corrected_test_cases: list[dict] | None = None
    rounds_used: int = 0
    evaluated: bool = True
    error: str = ""

    @property
    def uncovered_acs(self) -> list[str]:
        """AC keys (1-based, as strings) the judge marked as not covered."""
        return [ac for ac, covered in self.ac_coverage.items() if not covered]

    @property
    def score(self) -> int:
        """Weighted defect score; lower is better. Used to keep the best version."""
        return (sum(_SEVERITY_WEIGHT[i.severity] for i in self.issues)
                + _UNCOVERED_AC_WEIGHT * len(self.uncovered_acs))

    def to_dict(self) -> dict:
        """Serialize verdict for JSON output."""
        return {
            "evaluated": self.evaluated,
            "error": self.error,
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
            "uncovered_acs": self.uncovered_acs,
            "duplicate_groups": self.duplicate_groups,
        }


class IJudge(ABC):
    """Interface for LLM-based test case validation (Judge layer)."""

    @abstractmethod
    def evaluate(
        self,
        test_cases: list[dict],
        story_data: dict,
        acceptance_criteria: list[str],
        app_config,
        rules,
    ) -> JudgeVerdict:
        """Evaluate ALL test cases against story context and rules."""

    @abstractmethod
    def fix_issues(
        self,
        test_cases: list[dict],
        verdict: JudgeVerdict,
        story_data: dict,
        acceptance_criteria: list[str],
        app_config,
    ) -> list[dict]:
        """Fix issues found during evaluation. Returns corrected test cases."""
