"""
Generic edge case generator implementation.
"""
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase, TestCategory, TestStep
from core.interfaces.edge_case_generator import IEdgeCaseGenerator
from core.config import TestCaseConfig


class GenericEdgeCaseGenerator(IEdgeCaseGenerator):
    """Generic edge case generator that works for any story."""
    
    def __init__(self, config: TestCaseConfig):
        """Initialize generator with configuration.
        
        Args:
            config: Test case configuration
        """
        self.config = config
    
    def is_applicable(self, story: UserStory) -> bool:
        """Check if edge cases are applicable.
        
        Args:
            story: The user story
            
        Returns:
            True if story has dialog/window interactions
        """
        story_lower = (story.title + ' ' + story.acceptance_criteria_text).lower()
        # Generate edge cases for dialogs, windows, links, etc.
        return any(keyword in story_lower for keyword in [
            'dialog', 'window', 'modal', 'link', 'close', 'escape',
            'version', 'copyright', 'support'
        ])
    
    def generate_edge_cases(self, story: UserStory, existing_tests: List[TestCase]) -> List[TestCase]:
        """Generate edge case tests.
        
        Args:
            story: The user story
            existing_tests: Already generated functional tests
            
        Returns:
            List of edge case test cases
        """
        edge_cases = []
        story_lower = (story.title + ' ' + story.acceptance_criteria_text).lower()
        feature_name = story.title.split(',')[0] if ',' in story.title else story.title
        
        # Extract feature name
        for prefix in ['As a', 'As an', 'I want', 'I need']:
            if feature_name.lower().startswith(prefix.lower()):
                feature_name = feature_name.replace(prefix, '').strip()
                break
        
        test_index = len(existing_tests)
        
        # Edge case: Escape key closes dialog/window
        if 'dialog' in story_lower or 'window' in story_lower:
            test_index += 1
            tc_id = f"{story.story_id}-{test_index * 5:03d}"
            steps = [
                TestStep(action="PRE-REQ: ENV QuickDraw application is installed", expected=""),
                TestStep(action="Launch ENV QuickDraw application.", expected=""),
                TestStep(action="Open the dialog/window.", expected=""),
                TestStep(action="Press the Escape key.", expected=""),
                TestStep(action="Verify that the dialog/window closes.", 
                        expected="Dialog/window closes when Escape key is pressed."),
                TestStep(action="Close/Exit the QuickDraw application.", expected="")
            ]
            edge_cases.append(TestCase(
                id=tc_id,
                title=f"{story.story_id}-{test_index * 5:03d}: {feature_name} / Dialog Window / Close dialog with Escape key",
                steps=steps,
                objective=f"Verify that the dialog/window can be closed using the Escape key.",
                category=TestCategory.EDGE_CASE,
                requires_object=False,
                is_accessibility=False
            ))
        
        # Edge case: Modal behavior
        if 'dialog' in story_lower or 'modal' in story_lower:
            test_index += 1
            tc_id = f"{story.story_id}-{test_index * 5:03d}"
            steps = [
                TestStep(action="PRE-REQ: ENV QuickDraw application is installed", expected=""),
                TestStep(action="Launch ENV QuickDraw application.", expected=""),
                TestStep(action="Open the dialog/window.", expected=""),
                TestStep(action="Attempt to interact with the main application window.", expected=""),
                TestStep(action="Verify that interaction with the main application is blocked while the dialog is open.",
                        expected="Main application window is unresponsive to interactions; dialog remains in focus."),
                TestStep(action="Close the dialog/window.", expected=""),
                TestStep(action="Close/Exit the QuickDraw application.", expected="")
            ]
            edge_cases.append(TestCase(
                id=tc_id,
                title=f"{story.story_id}-{test_index * 5:03d}: {feature_name} / Dialog Window / Dialog is modal",
                steps=steps,
                objective=f"Verify that the dialog behaves as a modal dialog, preventing interaction with the main application.",
                category=TestCategory.EDGE_CASE,
                requires_object=False,
                is_accessibility=False
            ))
        
        # Edge case: Multiple instances prevention
        if 'dialog' in story_lower or 'window' in story_lower:
            test_index += 1
            tc_id = f"{story.story_id}-{test_index * 5:03d}"
            steps = [
                TestStep(action="PRE-REQ: ENV QuickDraw application is installed", expected=""),
                TestStep(action="Launch ENV QuickDraw application.", expected=""),
                TestStep(action="Open the dialog/window.", expected="Dialog/window opens."),
                TestStep(action="Attempt to open the dialog/window again.", expected=""),
                TestStep(action="Verify that only one instance of the dialog/window is open.",
                        expected="No new dialog/window opens; the existing one remains in focus."),
                TestStep(action="Close the dialog/window.", expected=""),
                TestStep(action="Close/Exit the QuickDraw application.", expected="")
            ]
            edge_cases.append(TestCase(
                id=tc_id,
                title=f"{story.story_id}-{test_index * 5:03d}: {feature_name} / Dialog Window / Multiple dialog instances",
                steps=steps,
                objective=f"Verify that only one instance of the dialog/window can be open at a time.",
                category=TestCategory.NEGATIVE,
                requires_object=False,
                is_accessibility=False
            ))
        
        return edge_cases
