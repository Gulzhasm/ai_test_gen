"""
Generic cross-platform test generator implementation.
"""
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase, TestCategory, TestStep
from core.interfaces.cross_platform_generator import ICrossPlatformGenerator
from core.config import TestCaseConfig


class GenericCrossPlatformGenerator(ICrossPlatformGenerator):
    """Generic cross-platform generator that works for any story."""
    
    PLATFORMS = ["Windows 11", "Tablets"]
    
    def __init__(self, config: TestCaseConfig):
        """Initialize generator with configuration.
        
        Args:
            config: Test case configuration
        """
        self.config = config
    
    def get_supported_platforms(self) -> List[str]:
        """Get list of supported platforms.
        
        Returns:
            List of platform names
        """
        return self.PLATFORMS
    
    def generate_platform_tests(self, story: UserStory, base_tests: List[TestCase]) -> List[TestCase]:
        """Generate platform-specific variants of base tests.
        
        Args:
            story: The user story
            base_tests: Base functional tests to create platform variants for
            
        Returns:
            List of platform-specific test cases
        """
        platform_tests = []
        
        # Only generate platform variants for key functional tests (limit to avoid duplication)
        key_tests = [
            tc for tc in base_tests 
            if not tc.is_accessibility 
            and tc.category in [TestCategory.BEHAVIOR, TestCategory.OPTIONS, TestCategory.SCOPE]
        ][:3]  # Limit to 3 key tests
        
        test_index = len(base_tests) + 50  # Start from higher number
        
        for base_test in key_tests:
            for platform in self.PLATFORMS:
                test_index += 1
                tc_id = f"{story.story_id}-{test_index * 5:03d}"
                
                # Clone steps and adapt for platform
                steps = []
                for step in base_test.steps:
                    action = step.action
                    expected = step.expected
                    
                    # Adapt launch step for platform
                    if "Launch ENV QuickDraw application" in action:
                        if platform == "Tablets":
                            action = "Launch ENV QuickDraw application on tablet (iPad or Android Tablet)."
                        else:
                            action = f"Launch ENV QuickDraw application on {platform}."
                    
                    # Adapt interaction verbs for tablets
                    if platform == "Tablets":
                        action = action.replace("Click", "Tap").replace("click", "tap")
                    
                    # Adapt expected results
                    if expected and platform in expected:
                        pass  # Already platform-specific
                    elif expected and platform == "Tablets":
                        expected = expected.replace("Windows 11", "tablet (iPad or Android Tablet)")
                    
                    steps.append(TestStep(
                        action=action,
                        expected=expected,
                        step_number=step.step_number
                    ))
                
                # Create platform-specific title
                title = base_test.title
                if f"({platform})" not in title:
                    title = f"{title} ({platform})"
                
                platform_tests.append(TestCase(
                    id=tc_id,
                    title=title,
                    steps=steps,
                    objective=base_test.objective.replace("Windows 11", platform) if "Windows 11" in base_test.objective else base_test.objective,
                    category=base_test.category,
                    requires_object=base_test.requires_object,
                    is_accessibility=False,
                    device=platform,
                    ui_area=base_test.ui_area
                ))
        
        return platform_tests
