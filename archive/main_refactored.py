#!/usr/bin/env python3
"""
ADO Test Case Generator - Clean Architecture Implementation
Generic, extensible, and reusable framework for generating QA deliverables.

Usage:
    export ADO_PAT="your_pat_here"
    python main_refactored.py --story-id <STORY_ID>

Architecture:
    - Domain Layer: Core business entities and value objects
    - Application Layer: Use cases and application services
    - Infrastructure Layer: External dependencies (ADO, file I/O)
    - Interfaces: Abstractions for dependency inversion
"""
import argparse
import sys
from pathlib import Path

from core.config import AppConfig
from core.application.use_cases.generate_test_cases import GenerateTestCasesUseCase
from core.application.use_cases.export_deliverables import ExportDeliverablesUseCase
from infrastructure.ado.ado_repository import ADOStoryRepository
from infrastructure.generators.test_generator_adapter import TestGeneratorAdapter
from infrastructure.generators.edge_case_generator_adapter import GenericEdgeCaseGenerator
from infrastructure.generators.accessibility_generator_adapter import GenericAccessibilityGenerator
from infrastructure.generators.cross_platform_generator_adapter import GenericCrossPlatformGenerator
from infrastructure.output.csv_generator_adapter import CSVGeneratorAdapter
from infrastructure.output.objective_generator_adapter import ObjectiveGeneratorAdapter
from infrastructure.output.qa_summary_generator_adapter import QASummaryGeneratorAdapter


def main():
    """Main entry point with clean architecture."""
    parser = argparse.ArgumentParser(
        description='Generate ADO test cases from User Story (Clean Architecture)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  export ADO_PAT="your_pat_here"
  python main_refactored.py --story-id 270472
  
  python main_refactored.py --story-id 270472 --dry-run
  python main_refactored.py --story-id 270472 --debug-summary
        """
    )
    parser.add_argument('--story-id', type=int, required=True, 
                        help='Azure DevOps User Story ID')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Generate files without validating against ADO')
    parser.add_argument('--debug-summary', action='store_true',
                        help='Enable debug mode for summary generation')
    args = parser.parse_args()
    
    # Load configuration
    config = AppConfig.load()
    
    if not config.ado.pat:
        print("ERROR: ADO_PAT environment variable is required")
        print("Set it with: export ADO_PAT='your_pat_here'")
        sys.exit(1)
    
    # Ensure output directory exists
    Path(config.output.output_dir).mkdir(exist_ok=True)
    
    try:
        # Initialize infrastructure (dependency injection)
        story_repository = ADOStoryRepository(config.ado)
        test_generator = TestGeneratorAdapter(config.test_case)
        edge_case_generator = GenericEdgeCaseGenerator(config.test_case)
        accessibility_generator = GenericAccessibilityGenerator(config.test_case)
        cross_platform_generator = GenericCrossPlatformGenerator(config.test_case)
        csv_generator = CSVGeneratorAdapter(config.test_case)
        objective_generator = ObjectiveGeneratorAdapter(config.test_case)
        summary_generator = QASummaryGeneratorAdapter(config.test_case, debug=args.debug_summary)
        
        # Step 1: Retrieve story
        print("=" * 80)
        print("STEP 1: Extracting User Story from Azure DevOps")
        print("=" * 80)
        story = story_repository.get_story(args.story_id)
        
        if not story:
            print("ERROR: Could not retrieve story from Azure DevOps")
            sys.exit(1)
        
        if not story.acceptance_criteria_text:
            print("WARNING: No acceptance criteria found in field or comments!")
            print("Please ensure AC is in Microsoft.VSTS.Common.AcceptanceCriteria field or comments.")
            sys.exit(1)
        
        print(f"✓ Extracted story: {story.title}")
        print(f"  Acceptance Criteria Parsed: {len(story.acceptance_criteria)}")
        
        # Step 2: Generate test cases (use case)
        print("\n" + "=" * 80)
        print("STEP 2: Generating Test Cases")
        print("=" * 80)
        generate_use_case = GenerateTestCasesUseCase(
            test_generator=test_generator,
            edge_case_generator=edge_case_generator,
            accessibility_generator=accessibility_generator,
            cross_platform_generator=cross_platform_generator
        )
        test_cases = generate_use_case.execute(story)
        print(f"✓ Generated {len(test_cases)} test cases")
        
        # Step 3: Export deliverables (use case)
        print("\n" + "=" * 80)
        print("STEP 3: Exporting Deliverables")
        print("=" * 80)
        export_use_case = ExportDeliverablesUseCase(
            csv_generator=csv_generator,
            objective_generator=objective_generator,
            summary_generator=summary_generator,
            config=config
        )
        deliverables = export_use_case.execute(story, test_cases)
        
        print(f"✓ Generated CSV: {deliverables['csv']}")
        print(f"✓ Generated Objectives: {deliverables['objectives']}")
        print(f"✓ Generated QA Summary: {deliverables['summary']}")
        
        # Final Summary
        print("\n" + "=" * 80)
        print("GENERATION COMPLETE")
        print("=" * 80)
        print(f"Story ID: {args.story_id}")
        print(f"Story Title: {story.title}")
        print(f"Test Cases Generated: {len(test_cases)}")
        print(f"\nGenerated Deliverables:")
        print(f"  ✓ CSV Test Cases: {deliverables['csv']}")
        print(f"  ✓ Test Objectives: {deliverables['objectives']}")
        print(f"  ✓ QA Planning Summary: {deliverables['summary']}")
        
        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print("1. Review generated files for accuracy")
        print("2. Import CSV test cases to Azure DevOps")
        print("3. Update Summary fields with objectives:")
        print(f"   python update_summary_generic.py {args.story_id}")
        print("\n✓ All deliverables generated successfully!")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
