"""
Interface for test case generation strategies.
"""
from abc import ABC, abstractmethod
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase


class ITestGenerator(ABC):
    """Interface for test case generation strategies."""
    
    @abstractmethod
    def generate(self, story: UserStory) -> List[TestCase]:
        """Generate test cases from user story.
        
        Args:
            story: The user story to generate test cases from
            
        Returns:
            List of generated test cases
        """
        pass
    
    @abstractmethod
    def can_handle(self, story: UserStory) -> bool:
        """Check if this generator can handle the given story.
        
        Args:
            story: The user story to check
            
        Returns:
            True if this generator can handle the story
        """
        pass
