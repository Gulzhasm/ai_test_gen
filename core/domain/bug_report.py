"""Domain model for bug reports."""
from dataclasses import dataclass, field


@dataclass
class BugObservation:
    """An observation within a recreate step (the 'a.' sub-item)."""
    text: str
    is_not_expected: bool = True
    attachment: str | None = None
    expected_behaviors: list[str] = field(default_factory=list)


@dataclass
class RecreateStep:
    """A numbered recreate step."""
    number: int
    action: str
    observations: list[BugObservation] = field(default_factory=list)


@dataclass
class BugReport:
    """Domain entity representing a bug report following ENV Drawing Bug Template."""
    title: str
    issue: str
    steps: list[RecreateStep]
    severity: str = "2 - High"
    story_id: int | None = None
    iteration: str | None = None
    additional_info: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    system_info: list[str] = field(default_factory=list)

    @property
    def is_wcag(self) -> bool:
        """Check if this is a WCAG/accessibility bug based on title."""
        return "WCAG" in self.title.upper()

    def validate(self) -> list[str]:
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
