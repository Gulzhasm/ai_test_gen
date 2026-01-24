"""
QA Summary generator adapter - wraps legacy QASummaryGenerator.
"""
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase
from core.interfaces.output_generator import IQASummaryGenerator
from core.config import TestCaseConfig
from src.qa_summary_generator import QASummaryGenerator as LegacyQASummaryGenerator


class QASummaryGeneratorAdapter(IQASummaryGenerator):
    """Adapter that wraps legacy QASummaryGenerator."""
    
    def __init__(self, config: TestCaseConfig, debug: bool = False):
        """Initialize adapter with configuration.
        
        Args:
            config: Test case configuration
            debug: Enable debug mode
        """
        self.config = config
        self.debug = debug
        self.legacy_generator = LegacyQASummaryGenerator(debug=debug)
    
    def generate(self, story: UserStory, test_cases: List[TestCase]) -> str:
        """Generate QA planning summary.
        
        Args:
            story: The user story
            test_cases: Generated test cases
            
        Returns:
            QA summary text
        """
        # Convert domain entities to legacy format
        story_data = {
            'story_id': story.story_id,
            'title': story.title,
            'description_text': story.description,
            'acceptance_criteria_text': story.acceptance_criteria_text
        }
        
        legacy_test_cases = []
        for tc in test_cases:
            legacy_tc = {
                'id': tc.id,
                'title': tc.title,
                'steps': [
                    {
                        'action': step.action,
                        'expected': step.expected
                    }
                    for step in tc.steps
                ],
                'objective': tc.objective,
                'area': tc.category.value if hasattr(tc.category, 'value') else str(tc.category),
                'requires_object': tc.requires_object,
                'is_accessibility': tc.is_accessibility,
                'device': tc.device
            }
            legacy_test_cases.append(legacy_tc)
        
        # Generate using legacy generator
        return self.legacy_generator.generate_summary(story_data, legacy_test_cases)
