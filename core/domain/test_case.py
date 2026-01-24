"""
Test Case domain entity.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class TestCategory(str, Enum):
    """Test case categories."""
    AVAILABILITY = "Availability"
    BEHAVIOR = "Behavior"
    OPTIONS = "Options"
    GEOMETRY = "Geometry"
    SCOPE = "Scope"
    UNDO_REDO = "Undo Redo"
    TOOL_STATE = "Tool State"
    NEGATIVE = "Negative"
    EDGE_CASE = "Edge Case"
    ACCESSIBILITY = "Accessibility"
    VALIDATION = "Validation"


@dataclass
class TestStep:
    """Represents a single test step."""
    action: str
    expected: str
    step_number: Optional[int] = None


@dataclass
class TestCase:
    """Domain entity representing a test case."""
    id: str
    title: str
    steps: List[TestStep] = field(default_factory=list)
    objective: str = ""
    category: TestCategory = TestCategory.BEHAVIOR
    requires_object: bool = False
    is_accessibility: bool = False
    device: Optional[str] = None
    ui_area: Optional[str] = None
    
    def __post_init__(self):
        """Validate test case after initialization."""
        if not self.title:
            raise ValueError("Test case title cannot be empty")
        if not self.steps:
            raise ValueError("Test case must have at least one step")
        if not self.objective:
            raise ValueError("Test case must have an objective")
