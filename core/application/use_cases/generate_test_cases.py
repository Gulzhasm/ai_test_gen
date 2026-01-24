"""
Use case: Generate test cases from user story.
"""
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase
from core.interfaces.test_generator import ITestGenerator
from core.interfaces.edge_case_generator import IEdgeCaseGenerator
from core.interfaces.accessibility_generator import IAccessibilityGenerator
from core.interfaces.cross_platform_generator import ICrossPlatformGenerator


class GenerateTestCasesUseCase:
    """Use case for generating test cases from a user story."""
    
    def __init__(
        self,
        test_generator: ITestGenerator,
        edge_case_generator: IEdgeCaseGenerator,
        accessibility_generator: IAccessibilityGenerator,
        cross_platform_generator: ICrossPlatformGenerator
    ):
        """Initialize use case with dependencies.
        
        Args:
            test_generator: Main test case generator
            edge_case_generator: Edge case generator
            accessibility_generator: Accessibility test generator
            cross_platform_generator: Cross-platform test generator
        """
        self.test_generator = test_generator
        self.edge_case_generator = edge_case_generator
        self.accessibility_generator = accessibility_generator
        self.cross_platform_generator = cross_platform_generator
    
    def execute(self, story: UserStory) -> List[TestCase]:
        """Execute test case generation.
        
        Args:
            story: The user story to generate tests for
            
        Returns:
            Complete list of generated test cases
        """
        test_cases: List[TestCase] = []
        
        # Generate base functional tests
        if self.test_generator.can_handle(story):
            test_cases.extend(self.test_generator.generate(story))
        
        # Generate edge cases if applicable
        if self.edge_case_generator.is_applicable(story):
            edge_cases = self.edge_case_generator.generate_edge_cases(story, test_cases)
            test_cases.extend(edge_cases)
        
        # Generate accessibility tests
        accessibility_tests = self.accessibility_generator.generate_accessibility_tests(story)
        test_cases.extend(accessibility_tests)
        
        # Generate cross-platform tests
        functional_tests = [tc for tc in test_cases if not tc.is_accessibility]
        platform_tests = self.cross_platform_generator.generate_platform_tests(story, functional_tests)
        test_cases.extend(platform_tests)
        
        return test_cases
