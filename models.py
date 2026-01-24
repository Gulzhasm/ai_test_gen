"""
Domain Models for Test Generation
Clean, typed data classes representing core domain concepts.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class DeviceType(Enum):
    """Device/platform types for testing."""
    WINDOWS_11 = "Windows 11"
    IPAD = "iPad"
    ANDROID_TABLET = "Android Tablet"
    TABLETS = "Tablets"  # Combined iPad/Android for functional tests


@dataclass
class UserStory:
    """User story from Azure DevOps."""
    story_id: int
    title: str
    description: str
    acceptance_criteria: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for legacy compatibility."""
        return {
            'story_id': self.story_id,
            'title': self.title,
            'description_text': self.description,
            'acceptance_criteria_text': self.acceptance_criteria
        }


@dataclass
class TestStep:
    """Single test step with action and expected result."""
    index: int
    action: str
    expected: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for legacy compatibility."""
        return {
            'action': self.action,
            'expected': self.expected
        }


@dataclass
class TestCase:
    """Test case with steps and metadata."""
    test_id: str
    title: str
    steps: List[TestStep]
    area: str
    requires_object: bool = False
    is_accessibility: bool = False
    device: Optional[str] = None
    objective: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for legacy compatibility."""
        return {
            'id': self.test_id,
            'title': self.title,
            'steps': [step.to_dict() for step in self.steps],
            'area': self.area,
            'requires_object': self.requires_object,
            'is_accessibility': self.is_accessibility,
            'device': self.device,
            'objective': self.objective
        }


@dataclass
class Objective:
    """Test objective mapped 1:1 to test case."""
    test_id: str
    title: str
    objective_text: str
    
    def format_for_ado(self, key_terms: List[str]) -> str:
        """Format with HTML for ADO Summary field."""
        import re
        
        # Remove "Verify that" prefix if present
        text = self.objective_text.strip()
        if text.lower().startswith('verify that '):
            text = text[12:]
        
        # Format: <b>Objective:</b> Verify that [text]
        formatted = f"<b>Objective:</b> Verify that {text}"
        
        # Make key terms bold
        for term in key_terms:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            formatted = pattern.sub(r'<b>\g<0></b>', formatted)
        
        return formatted


@dataclass
class SummaryPlan:
    """QA Planning Summary structure before rendering."""
    intro_facts: str
    bullet_themes: List[str]
    dependencies: List[str]
    accessibility_clause: str
    platform_clause: str
    
    def validate(self) -> tuple[bool, List[str]]:
        """Validate the summary plan structure."""
        errors = []
        
        if not self.intro_facts or len(self.intro_facts.strip()) < 20:
            errors.append("Intro facts too short or empty")
        
        if len(self.bullet_themes) < 6:
            errors.append(f"Too few bullets: {len(self.bullet_themes)} (minimum 6)")
        elif len(self.bullet_themes) > 9:
            errors.append(f"Too many bullets: {len(self.bullet_themes)} (maximum 9)")
        
        if not self.dependencies:
            errors.append("Dependencies list is empty")
        
        if not self.accessibility_clause or len(self.accessibility_clause.strip()) < 20:
            errors.append("Accessibility clause too short or empty")
        
        if not self.platform_clause or len(self.platform_clause.strip()) < 20:
            errors.append("Platform clause too short or empty")
        
        return len(errors) == 0, errors


@dataclass
class EvidenceModel:
    """Evidence sources for guardrails."""
    allowed_entry_points: List[str] = field(default_factory=list)
    allowed_behaviors: List[str] = field(default_factory=list)
    forbidden_words: List[str] = field(default_factory=list)
    description_text: str = ""
    ac_text: str = ""
    test_titles: List[str] = field(default_factory=list)
    
    def is_supported(self, term: str) -> bool:
        """Check if term is supported by evidence."""
        term_lower = term.lower()
        evidence_text = f"{self.description_text} {self.ac_text}".lower()
        
        # Check exact match in evidence
        if term_lower in evidence_text:
            return True
        
        # Check in test titles
        for title in self.test_titles:
            if term_lower in title.lower():
                return True
        
        # Check word boundaries
        import re
        pattern = r'\b' + re.escape(term_lower) + r'\b'
        if re.search(pattern, evidence_text):
            return True
        
        return False
    
    def is_forbidden(self, term: str) -> bool:
        """Check if term is forbidden."""
        term_lower = term.lower()
        return any(forbidden.lower() in term_lower for forbidden in self.forbidden_words)


@dataclass
class LintResult:
    """Result of linting operation."""
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def __bool__(self) -> bool:
        """Boolean conversion for easy checking."""
        return self.ok
    
    def add_error(self, error: str):
        """Add an error and mark as not ok."""
        self.errors.append(error)
        self.ok = False
    
    def add_warning(self, warning: str):
        """Add a warning (doesn't affect ok status)."""
        self.warnings.append(warning)
