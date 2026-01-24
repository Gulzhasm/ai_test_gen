"""
Use case: Export test case deliverables (CSV, Objectives, Summary).
"""
from pathlib import Path
from typing import List

from core.domain.story import UserStory
from core.domain.test_case import TestCase
from core.domain.feature import FeatureExtractor
from core.interfaces.output_generator import ICSVGenerator, IObjectiveGenerator, IQASummaryGenerator
from core.config import AppConfig


class ExportDeliverablesUseCase:
    """Use case for exporting test case deliverables."""
    
    def __init__(
        self,
        csv_generator: ICSVGenerator,
        objective_generator: IObjectiveGenerator,
        summary_generator: IQASummaryGenerator,
        config: AppConfig
    ):
        """Initialize use case with dependencies.
        
        Args:
            csv_generator: CSV file generator
            objective_generator: Objectives file generator
            summary_generator: QA summary generator
            config: Application configuration
        """
        self.csv_generator = csv_generator
        self.objective_generator = objective_generator
        self.summary_generator = summary_generator
        self.config = config
    
    def execute(
        self,
        story: UserStory,
        test_cases: List[TestCase]
    ) -> dict:
        """Execute deliverables export.
        
        Args:
            story: The user story
            test_cases: Generated test cases
            
        Returns:
            Dictionary with paths to generated files:
            {
                'csv': str,
                'objectives': str,
                'summary': str
            }
        """
        # Ensure output directory exists
        output_dir = Path(self.config.output.output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Extract feature name for filenames
        feature_name = FeatureExtractor.extract_feature_name(story.title)
        feature_name_safe = FeatureExtractor.sanitize_filename(feature_name)
        
        # Generate file paths
        csv_path = str(output_dir / f"{story.story_id}_{feature_name_safe}_Test_Cases.csv")
        objectives_path = str(output_dir / f"{story.story_id}_{feature_name_safe}_Test_Objectives.txt")
        summary_path = str(output_dir / f"{story.story_id}_{feature_name_safe}_qa_summary.txt")
        
        # Generate CSV
        self.csv_generator.generate(test_cases, csv_path)
        
        # Generate objectives
        self.objective_generator.generate(test_cases, objectives_path)
        
        # Generate QA summary
        summary_text = self.summary_generator.generate(story, test_cases)
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_text)
        
        return {
            'csv': csv_path,
            'objectives': objectives_path,
            'summary': summary_path
        }
