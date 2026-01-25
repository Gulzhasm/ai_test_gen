"""
Output generator interfaces for test artifacts.

Abstracts the output generation for different formats.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

from core.domain.test_case import TestCase
from core.domain.story import UserStory


class IOutputGenerator(ABC):
    """Base interface for output generation."""

    @abstractmethod
    def generate(
        self,
        test_cases: List[TestCase],
        output_path: str
    ) -> str:
        """Generate output file from test cases.

        Args:
            test_cases: List of test case objects
            output_path: Path for output file

        Returns:
            Path to generated file
        """
        pass


class ICSVGenerator(IOutputGenerator):
    """Interface for CSV file generation."""

    @abstractmethod
    def generate(self, test_cases: List[TestCase], output_path: str) -> str:
        """Generate CSV file from test cases.

        Args:
            test_cases: List of test cases to export
            output_path: Path to output CSV file

        Returns:
            Path to generated file
        """
        pass

    @abstractmethod
    def generate_from_dicts(
        self,
        test_cases: List[Dict],
        output_file: str,
        include_headers: bool = True
    ) -> str:
        """Generate CSV file from test case dictionaries.

        Args:
            test_cases: List of test case dictionaries
            output_file: Path for output CSV
            include_headers: Whether to include header row

        Returns:
            Path to generated CSV file
        """
        pass


class IObjectiveGenerator(ABC):
    """Interface for objectives file generation."""

    @abstractmethod
    def generate(self, test_cases: List[TestCase], output_path: str) -> str:
        """Generate objectives file from test cases.

        Args:
            test_cases: List of test cases
            output_path: Path to output objectives file

        Returns:
            Path to generated file
        """
        pass

    @abstractmethod
    def format_objective(self, objective: str) -> str:
        """Format a single objective with proper formatting.

        Args:
            objective: Raw objective text

        Returns:
            Formatted objective with HTML bolding
        """
        pass

    @abstractmethod
    def format_objective_for_ado(self, objective: str) -> str:
        """Format objective for ADO Description field.

        Args:
            objective: Raw objective text

        Returns:
            HTML-formatted objective for ADO
        """
        pass

    @abstractmethod
    def generate_objectives_file(
        self,
        test_cases: List[Dict],
        output_path: str
    ) -> str:
        """Generate objectives text file from dictionaries.

        Args:
            test_cases: List of test case dictionaries
            output_path: Path for output file

        Returns:
            Path to generated file
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
