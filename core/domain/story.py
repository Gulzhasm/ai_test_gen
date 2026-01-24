"""
User Story domain entity.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class UserStory:
    """Domain entity representing a user story."""
    story_id: int
    title: str
    description: str
    acceptance_criteria_text: str
    acceptance_criteria: List[str]
    
    def __post_init__(self):
        """Validate story after initialization."""
        if not self.story_id:
            raise ValueError("Story ID cannot be empty")
        if not self.title:
            raise ValueError("Story title cannot be empty")
        if not self.acceptance_criteria_text:
            raise ValueError("Story must have acceptance criteria")
