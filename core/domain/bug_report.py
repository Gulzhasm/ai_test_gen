"""Domain model for bug reports."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BugObservation:
    """An observation within a recreate step (the 'a.' sub-item)."""
    text: str
    is_not_expected: bool = True
    attachment: Optional[str] = None
    expected_behaviors: List[str] = field(default_factory=list)


@dataclass
class RecreateStep:
    """A numbered recreate step."""
    number: int
    action: str
    observations: List[BugObservation] = field(default_factory=list)


@dataclass
class BugReport:
    """Domain entity representing a bug report following ENV Drawing Bug Template."""
    title: str
    issue: str
    steps: List[RecreateStep]
    severity: str = "2 - High"
    story_id: Optional[int] = None
    iteration: Optional[str] = None
    additional_info: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    system_info: List[str] = field(default_factory=list)

    @property
    def is_wcag(self) -> bool:
        """Check if this is a WCAG/accessibility bug based on title."""
        return "WCAG" in self.title.upper()

    def validate(self) -> List[str]:
        """Validate bug report fields. Returns list of error messages."""
        errors = []
        if not self.title:
            errors.append("Bug title is required")
        if not self.issue:
            errors.append("Issue description is required")
        if not self.steps:
            errors.append("At least one recreate step is required")
        if not self.title.startswith("DRAW:"):
            errors.append("Title must start with 'DRAW:'")
        return errors
