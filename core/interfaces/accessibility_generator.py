"""
Interface for accessibility test generation.
"""
from abc import ABC, abstractmethod
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase


class IAccessibilityGenerator(ABC):
    """Interface for generating accessibility tests."""
    
    @abstractmethod
    def generate_accessibility_tests(self, story: UserStory) -> List[TestCase]:
        """Generate accessibility tests for all required platforms.
        
        Args:
            story: The user story
            
        Returns:
            List of accessibility test cases
        """
        pass
    
    @abstractmethod
    def get_required_platforms(self) -> List[str]:
        """Get list of platforms that require accessibility testing.
        
        Returns:
            List of platform names
        """
        pass
