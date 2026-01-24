"""
CSV generator adapter - wraps legacy CSVGenerator.
"""
from typing import List

from core.domain.test_case import TestCase
from core.interfaces.output_generator import ICSVGenerator
from core.config import TestCaseConfig
from src.csv_generator import CSVGenerator as LegacyCSVGenerator


class CSVGeneratorAdapter(ICSVGenerator):
    """Adapter that wraps legacy CSVGenerator."""
    
    def __init__(self, config: TestCaseConfig):
        """Initialize adapter with configuration.
        
        Args:
            config: Test case configuration
        """
        self.config = config
        self.legacy_generator = LegacyCSVGenerator()
    
    def generate(self, test_cases: List[TestCase], output_path: str) -> None:
        """Generate CSV file from test cases.
        
        Args:
            test_cases: List of test cases to export
            output_path: Path to output CSV file
        """
        # Convert domain entities to legacy format
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
                'area': tc.category.value if hasattr(tc.category, 'value') else str(tc.category)
            }
            legacy_test_cases.append(legacy_tc)
        
        # Generate using legacy generator
        self.legacy_generator.generate_csv(legacy_test_cases, output_path)
