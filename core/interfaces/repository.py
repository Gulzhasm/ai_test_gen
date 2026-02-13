"""
Repository interfaces for data access abstraction.

Following the Repository pattern to abstract data access from business logic.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from core.domain.story import UserStory
from core.domain.test_case import TestCase


class IStoryRepository(ABC):
    """Interface for story data access."""

    @abstractmethod
    def get_story(self, story_id: int) -> Optional[UserStory]:
        """Retrieve a user story by ID.

        Args:
            story_id: The story ID

        Returns:
            UserStory if found, None otherwise
        """
        pass

    @abstractmethod
    def get_qa_prep(self, story_id: int) -> Optional[str]:
        """Retrieve QA Prep content for a story.

        Args:
            story_id: The story ID

        Returns:
            QA Prep content if found, None otherwise
        """
        pass

    def update_qa_prep(self, story_id: int, summary_text: str) -> bool:
        """Update QA Prep child task with QA Planning Summary.

        Args:
            story_id: The parent story ID
            summary_text: Markdown-formatted QA Planning Summary

        Returns:
            True if updated successfully, False otherwise
        """
        return False


class ITestSuiteRepository(ABC):
    """Interface for test suite data access."""

    @abstractmethod
    def find_suite_by_story_id(self, story_id: int) -> Optional[Dict[str, Any]]:
        """Find test suite matching story ID pattern.

        Args:
            story_id: The story ID

        Returns:
            Suite info dict with 'id', 'name', 'plan_id' if found, None otherwise
        """
        pass

    @abstractmethod
    def create_suite(
        self,
        plan_id: int,
        suite_name: str,
        story_id: int
    ) -> Optional[Dict[str, Any]]:
        """Create a new test suite.

        Args:
            plan_id: Parent test plan ID
            suite_name: Name for the new suite
            story_id: Associated story ID

        Returns:
            Suite info dict if created, None otherwise
        """
        pass

    @abstractmethod
    def add_test_case_to_suite(
        self,
        plan_id: int,
        suite_id: int,
        test_case_id: int
    ) -> bool:
        """Add a test case to a test suite.

        Args:
            plan_id: Test plan ID
            suite_id: Test suite ID
            test_case_id: Test case work item ID

        Returns:
            True if successful, False otherwise
        """
        pass


class ITestCaseRepository(ABC):
    """Interface for test case data access."""

    @abstractmethod
    def create_test_case(
        self,
        title: str,
        steps: List[Dict[str, str]],
        objective: str,
        **kwargs
    ) -> Optional[int]:
        """Create a test case in the repository.

        Args:
            title: Test case title
            steps: List of step dicts with 'action' and 'expected'
            objective: Test case objective
            **kwargs: Additional fields (assigned_to, area_path, state)

        Returns:
            Work item ID if created, None otherwise
        """
        pass

    @abstractmethod
    def update_test_case(
        self,
        test_case_id: int,
        fields: Dict[str, Any]
    ) -> bool:
        """Update a test case.

        Args:
            test_case_id: Test case work item ID
            fields: Fields to update

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_test_case(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        """Get a test case by ID.

        Args:
            test_case_id: Test case work item ID

        Returns:
            Test case data if found, None otherwise
        """
        pass
