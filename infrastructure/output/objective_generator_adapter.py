"""
Objective generator adapter - wraps legacy ObjectiveGenerator.
"""
from typing import List

from core.domain.test_case import TestCase
from core.interfaces.output_generator import IObjectiveGenerator
from core.config import TestCaseConfig
from src.objective_generator import ObjectiveGenerator as LegacyObjectiveGenerator


class ObjectiveGeneratorAdapter(IObjectiveGenerator):
    """Adapter that wraps legacy ObjectiveGenerator."""
    
    def __init__(self, config: TestCaseConfig):
        """Initialize adapter with configuration.
        
        Args:
            config: Test case configuration
        """
        self.config = config
        self.legacy_generator = LegacyObjectiveGenerator()
    
    def generate(self, test_cases: List[TestCase], output_path: str) -> None:
        """Generate objectives file from test cases.
        
        Args:
            test_cases: List of test cases
            output_path: Path to output objectives file
        """
        # Convert domain entities to legacy format
        legacy_test_cases = []
        for tc in test_cases:
            legacy_tc = {
                'id': tc.id,
                'title': tc.title,
                'objective': tc.objective
            }
            legacy_test_cases.append(legacy_tc)
        
        # Generate using legacy generator
        self.legacy_generator.generate_objectives_file(legacy_test_cases, output_path)
