"""
Adapter for existing TestGenerator to implement ITestGenerator interface.
"""
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase, TestCategory, TestStep
from core.interfaces.test_generator import ITestGenerator
from core.config import TestCaseConfig
from src.test_generator import TestGenerator as LegacyTestGenerator


class TestGeneratorAdapter(ITestGenerator):
    """Adapter that wraps legacy TestGenerator to implement ITestGenerator."""
    
    def __init__(self, config: TestCaseConfig):
        """Initialize adapter with configuration.
        
        Args:
            config: Test case configuration
        """
        self.config = config
        self.legacy_generator = LegacyTestGenerator()
    
    def can_handle(self, story: UserStory) -> bool:
        """Check if this generator can handle the story.
        
        Args:
            story: The user story
            
        Returns:
            True (always handles all stories)
        """
        return True
    
    def generate(self, story: UserStory) -> List[TestCase]:
        """Generate test cases from user story.
        
        Args:
            story: The user story
            
        Returns:
            List of generated test cases
        """
        # Convert UserStory to legacy format
        story_data = {
            'story_id': story.story_id,
            'title': story.title,
            'acceptance_criteria_text': story.acceptance_criteria_text
        }
        
        # Generate using legacy generator
        legacy_test_cases = self.legacy_generator.generate_test_cases(
            story_data,
            story.acceptance_criteria
        )
        
        # Convert to domain entities
        test_cases = []
        for legacy_tc in legacy_test_cases:
            # Convert steps
            steps = [
                TestStep(
                    action=step.get('action', ''),
                    expected=step.get('expected', ''),
                    step_number=idx + 1
                )
                for idx, step in enumerate(legacy_tc.get('steps', []))
            ]
            
            # Map category
            category_str = legacy_tc.get('area', 'Behavior')
            try:
                category = TestCategory(category_str)
            except ValueError:
                category = TestCategory.BEHAVIOR
            
            test_case = TestCase(
                id=legacy_tc.get('id', ''),
                title=legacy_tc.get('title', ''),
                steps=steps,
                objective=legacy_tc.get('objective', ''),
                category=category,
                requires_object=legacy_tc.get('requires_object', False),
                is_accessibility=legacy_tc.get('is_accessibility', False),
                device=legacy_tc.get('device'),
                ui_area=legacy_tc.get('area')
            )
            test_cases.append(test_case)
        
        return test_cases
