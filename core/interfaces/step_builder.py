"""
Step builder interfaces for test case construction.

Abstracts the step building logic to enable different strategies.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class StepContext:
    """Context for building test steps."""
    feature_name: str
    entry_point: str
    story_id: int
    ac_text: str = ""
    requires_object: bool = False
    platform: Optional[str] = None
    qa_details: Optional[Dict] = None


class IStepTemplate(ABC):
    """Interface for step templates."""

    @abstractmethod
    def get_prereq_step(self) -> Dict[str, str]:
        """Get prerequisite step.

        Returns:
            Dict with 'action' and 'expected' keys
        """
        pass

    @abstractmethod
    def get_launch_step(self) -> Dict[str, str]:
        """Get application launch step.

        Returns:
            Dict with 'action' and 'expected' keys
        """
        pass

    @abstractmethod
    def get_close_step(self) -> Dict[str, str]:
        """Get application close step.

        Returns:
            Dict with 'action' and 'expected' keys
        """
        pass

    @abstractmethod
    def get_object_setup_steps(self) -> List[Dict[str, str]]:
        """Get steps for object/entity setup.

        Returns:
            List of step dicts
        """
        pass


class IStepBuilder(ABC):
    """Interface for building test steps."""

    @abstractmethod
    def build_setup_steps(self, context: StepContext) -> List[Dict[str, str]]:
        """Build setup steps (prereq, launch, object setup if needed).

        Args:
            context: Step building context

        Returns:
            List of step dicts
        """
        pass

    @abstractmethod
    def build_navigation_step(self, entry_point: str) -> Dict[str, str]:
        """Build navigation step to entry point.

        Args:
            entry_point: Target entry point

        Returns:
            Step dict
        """
        pass

    @abstractmethod
    def build_action_step(self, action: str) -> Dict[str, str]:
        """Build main action step.

        Args:
            action: Action description

        Returns:
            Step dict
        """
        pass

    @abstractmethod
    def build_verification_step(
        self,
        verification: str,
        expected: str
    ) -> Dict[str, str]:
        """Build verification step.

        Args:
            verification: What to verify
            expected: Expected result

        Returns:
            Step dict
        """
        pass

    @abstractmethod
    def build_teardown_steps(self) -> List[Dict[str, str]]:
        """Build teardown steps (close application).

        Returns:
            List of step dicts
        """
        pass

    @abstractmethod
    def build_undo_redo_steps(
        self,
        action: str,
        post_state: str,
        pre_state: str
    ) -> List[Dict[str, str]]:
        """Build undo/redo verification steps.

        Args:
            action: Action to undo/redo
            post_state: State after action
            pre_state: State before action

        Returns:
            List of step dicts
        """
        pass

    @abstractmethod
    def build_accessibility_prereq(
        self,
        platform: str,
        tool: str
    ) -> Dict[str, str]:
        """Build accessibility tool prerequisite step.

        Args:
            platform: Target platform
            tool: Accessibility tool name

        Returns:
            Step dict
        """
        pass
