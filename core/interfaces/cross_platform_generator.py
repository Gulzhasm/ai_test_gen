"""
Interface for cross-platform test generation.
"""
from abc import ABC, abstractmethod
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase


class ICrossPlatformGenerator(ABC):
    """Interface for generating cross-platform tests."""
    
    @abstractmethod
    def generate_platform_tests(self, story: UserStory, base_tests: List[TestCase]) -> List[TestCase]:
        """Generate platform-specific variants of base tests.
        
        Args:
            story: The user story
            base_tests: Base functional tests to create platform variants for
            
        Returns:
            List of platform-specific test cases
        """
        pass
    
    @abstractmethod
    def get_supported_platforms(self) -> List[str]:
        """Get list of supported platforms.
        
        Returns:
            List of platform names
        """
        pass
