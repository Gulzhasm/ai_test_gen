"""
Generic accessibility test generator implementation.
"""
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase, TestCategory, TestStep
from core.interfaces.accessibility_generator import IAccessibilityGenerator
from core.config import TestCaseConfig


class GenericAccessibilityGenerator(IAccessibilityGenerator):
    """Generic accessibility generator that works for any story."""
    
    PLATFORMS = [
        ("Windows 11", "Accessibility Insights for Windows tool is installed"),
        ("iPad", "Apple built-in accessibility tools are available and enabled (e.g., VoiceOver)"),
        ("Android Tablet", "Accessibility Scanner (Google) Free tool is installed")
    ]
    
    def __init__(self, config: TestCaseConfig):
        """Initialize generator with configuration.
        
        Args:
            config: Test case configuration
        """
        self.config = config
    
    def get_required_platforms(self) -> List[str]:
        """Get list of platforms that require accessibility testing.
        
        Returns:
            List of platform names
        """
        return [platform[0] for platform in self.PLATFORMS]
    
    def generate_accessibility_tests(self, story: UserStory) -> List[TestCase]:
        """Generate accessibility tests for all required platforms.
        
        Args:
            story: The user story
            
        Returns:
            List of accessibility test cases
        """
        accessibility_tests = []
        feature_name = story.title.split(',')[0] if ',' in story.title else story.title
        
        # Extract feature name
        for prefix in ['As a', 'As an', 'I want', 'I need']:
            if feature_name.lower().startswith(prefix.lower()):
                feature_name = feature_name.replace(prefix, '').strip()
                break
        
        # Determine UI area from story
        story_lower = (story.title + ' ' + story.acceptance_criteria_text).lower()
        ui_area = 'Tools Menu'
        if 'help menu' in story_lower:
            ui_area = 'Help Menu'
        elif 'file menu' in story_lower:
            ui_area = 'File Menu'
        elif 'edit menu' in story_lower:
            ui_area = 'Edit Menu'
        elif 'properties panel' in story_lower:
            ui_area = 'Properties Panel'
        
        # Generate accessibility test for each platform
        test_index = 100  # Start from a high number to avoid conflicts
        for device, tool_pre_req in self.PLATFORMS:
            test_index += 1
            tc_id = f"{story.story_id}-{test_index * 5:03d}"
            
            steps = [
                TestStep(action="PRE-REQ: ENV QuickDraw application is installed", expected=""),
                TestStep(action=f"PRE-REQ: {tool_pre_req}", expected=""),
                TestStep(action="Launch ENV QuickDraw application.", expected=""),
                TestStep(action=f"Open {ui_area} using keyboard navigation.", expected=""),
                TestStep(action=f"Navigate to {feature_name} option using keyboard navigation.", expected=""),
                TestStep(action=f"Activate {feature_name} using keyboard navigation.", expected=""),
                TestStep(action="Verify that keyboard navigation is fully functional with logical tab order.",
                        expected="All menu items and controls can be accessed using keyboard navigation with logical tab order."),
                TestStep(action="Verify that visible focus indicators are present on focused controls.",
                        expected="Visible focus indicators are displayed on all focused controls."),
                TestStep(action="Verify that focus order follows logical sequence.",
                        expected="Focus order follows logical sequence matching visual layout."),
                TestStep(action="Verify that all controls have readable labels and correct ARIA roles.",
                        expected="All controls have meaningful accessible names and correct ARIA roles for screen readers."),
                TestStep(action="Close/Exit the QuickDraw application.", expected="")
            ]
            
            accessibility_tests.append(TestCase(
                id=tc_id,
                title=f"{story.story_id}-{test_index * 5:03d}: {feature_name} / {ui_area} / Keyboard Navigation / Focus Visibility / Labels And Roles ({device})",
                steps=steps,
                objective=f"Verify that {feature_name} is accessible via keyboard navigation, has visible focus indicators, and proper labeling on {device}.",
                category=TestCategory.ACCESSIBILITY,
                requires_object=False,
                is_accessibility=True,
                device=device,
                ui_area=ui_area
            ))
        
        return accessibility_tests
