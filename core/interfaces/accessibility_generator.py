"""
Interface for accessibility test generation.
"""
from abc import ABC, abstractmethod

from core.domain.story import UserStory
from core.domain.test_case import TestCase


class IAccessibilityGenerator(ABC):
    """Interface for generating accessibility tests."""
    
    @abstractmethod
    def generate_accessibility_tests(self, story: UserStory) -> list[TestCase]:
        """Generate accessibility tests for all required platforms.
        
        Args:
            story: The user story
            
        Returns:
            List of accessibility test cases
        """
    
    @abstractmethod
    def get_required_platforms(self) -> list[str]:
        """Get list of platforms that require accessibility testing.
        
        Returns:
            List of platform names
        """
