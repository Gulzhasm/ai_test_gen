"""
Interface for edge case test generation.
"""
from abc import ABC, abstractmethod
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase


class IEdgeCaseGenerator(ABC):
    """Interface for generating edge case tests."""
    
    @abstractmethod
    def generate_edge_cases(self, story: UserStory, existing_tests: List[TestCase]) -> List[TestCase]:
        """Generate edge case tests.
        
        Args:
            story: The user story
            existing_tests: Already generated functional tests
            
        Returns:
            List of edge case test cases
        """
        pass
    
    @abstractmethod
    def is_applicable(self, story: UserStory) -> bool:
        """Check if edge cases are applicable for this story.
        
        Args:
            story: The user story to check
            
        Returns:
            True if edge cases should be generated
        """
        pass
