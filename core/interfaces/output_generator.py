"""
Interface for output generation (CSV, Objectives, Summary).
"""
from abc import ABC, abstractmethod
from typing import List

from core.domain.test_case import TestCase
from core.domain.story import UserStory


class ICSVGenerator(ABC):
    """Interface for CSV file generation."""
    
    @abstractmethod
    def generate(self, test_cases: List[TestCase], output_path: str) -> None:
        """Generate CSV file from test cases.
        
        Args:
            test_cases: List of test cases to export
            output_path: Path to output CSV file
        """
        pass


class IObjectiveGenerator(ABC):
    """Interface for objectives file generation."""
    
    @abstractmethod
    def generate(self, test_cases: List[TestCase], output_path: str) -> None:
        """Generate objectives file from test cases.
        
        Args:
            test_cases: List of test cases
            output_path: Path to output objectives file
        """
        pass


class IQASummaryGenerator(ABC):
    """Interface for QA summary generation."""
    
    @abstractmethod
    def generate(self, story: UserStory, test_cases: List[TestCase]) -> str:
        """Generate QA planning summary.
        
        Args:
            story: The user story
            test_cases: Generated test cases
            
        Returns:
            QA summary text
        """
        pass
