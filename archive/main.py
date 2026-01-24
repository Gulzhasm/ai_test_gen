#!/usr/bin/env python3
"""
AI-Test-Gen: Comprehensive Evidence-Based Test Case Generator
Generates reviewer-proof test cases from Azure DevOps User Stories.

Usage:
    export ADO_PAT="your_pat_here"

    # Workflow 1: Generate test cases and objectives
    python3 main.py generate --story-id <STORY_ID>

    # Workflow 2: Upload objectives to existing ADO test cases
    python3 main.py upload-objectives --csv <CSV_FILE>
"""
import argparse
import sys
import os
from pathlib import Path

import config
from src.ado_client import ADOClient
from src.test_generator_improved import ImprovedTestGenerator
from src.csv_generator import CSVGenerator
from src.objective_generator import ObjectiveGenerator
from src.validator import TestCaseValidator
from core.services.grounding_validator import GroundingValidator
from core.domain.grounded_spec import GroundedSpec


def sanitize_filename(text: str) -> str:
    """Sanitize text for use in filenames."""
    import re
    text = re.sub(r'[:/\\<>"|?*]', '_', text)
    text = re.sub(r'[\s_]+', '_', text)
    text = text.strip('_')
    if len(text) > 50:
        text = text[:50]
    return text


def extract_feature_name(story_title: str) -> str:
    """Extract feature name from story title."""
    title = story_title.strip()
    for prefix in ['As a', 'As an', 'I want', 'I need']:
        if title.lower().startswith(prefix.lower()):
            parts = title.split(',')
            if len(parts) > 1:
                title = parts[1].strip()
            else:
                title = title.replace(prefix, '').strip()
            break
    return title


def workflow_generate(args):
    """Workflow 1: Generate test cases and objectives from story ID."""

    # Validate ADO_PAT
    if not config.ADO_PAT:
        print("ERROR: ADO_PAT environment variable is required")
        print("Set it with: export ADO_PAT='your_pat_here'")
        sys.exit(1)

    print("=" * 80)
    print("AI-TEST-GEN: COMPREHENSIVE TEST CASE GENERATION")
    print("=" * 80)
    print(f"Story ID: {args.story_id}")
    print(f"Project: {config.ADO_PROJECT}")
    print(f"Organization: {config.ADO_ORG}")
    print()

    try:
        # Initialize ADO client
        print("→ Connecting to Azure DevOps...")
        ado_client = ADOClient()
        print("✓ Connected")

        # Fetch story data
        print(f"\n→ Fetching story {args.story_id}...")
        story_data = ado_client.extract_story_data(args.story_id)
        story_data['story_id'] = args.story_id
        story_title = story_data.get('title', 'Unknown')
        print(f"✓ Story: {story_title}")

        # Parse acceptance criteria
        print(f"\n→ Parsing acceptance criteria...")
        ac_text = story_data.get('acceptance_criteria_text', '')
        if not ac_text:
            print("✗ No acceptance criteria found")
            sys.exit(1)
        criteria = ado_client.parse_acceptance_criteria(ac_text)
        print(f"✓ Found {len(criteria)} acceptance criteria")

        # Get QA Prep
        print(f"\n→ Fetching QA Prep content...")
        qa_prep_content = ado_client.retrieve_qa_prep_subtask(args.story_id)
        if qa_prep_content:
            print(f"✓ QA Prep content found ({len(qa_prep_content)} chars)")
        else:
            print(f"⚠ No QA Prep content found (will use AC only)")

        # Generate test cases
        print()
        print("=" * 80)
        print("GENERATING COMPREHENSIVE TEST CASES")
        print("=" * 80)
        print()

        generator = ImprovedTestGenerator()
        test_cases = generator.generate_test_cases(story_data, criteria, qa_prep_content)

        print()
        print("=" * 80)
        print(f"✓ Generated {len(test_cases)} test cases")
        print("=" * 80)

        # Validate test cases
        print(f"\n→ Validating test cases...")
        validator = TestCaseValidator()
        is_valid, errors = validator.validate_test_cases(test_cases)

        if not is_valid:
            print(f"⚠ Validation found {len(errors)} issues:")
            for error in errors[:10]:
                print(f"  • {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
        else:
            print(f"✓ All validation checks passed")

        # Grounding validation
        if not args.skip_grounding:
            print(f"\n→ Validating grounding (evidence-based)...")
            grounded_spec = GroundedSpec.from_story_data(story_data, criteria, qa_prep_content)
            grounding_validator = GroundingValidator(grounded_spec)
            is_grounded, grounding_errors = grounding_validator.validate_test_cases(test_cases)

            if not is_grounded:
                print(f"✗ Grounding validation failed with {len(grounding_errors)} errors:")
                for error in grounding_errors[:10]:
                    print(f"  • {error}")
                if len(grounding_errors) > 10:
                    print(f"  ... and {len(grounding_errors) - 10} more")
                if args.strict:
                    print("\n✗ STRICT MODE: Cannot proceed with ungrounded tests")
                    sys.exit(1)
            else:
                print(f"✓ All tests are evidence-based (grounded)")

        # Generate output files
        print()
        print("=" * 80)
        print("GENERATING OUTPUT FILES")
        print("=" * 80)

        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)

        feature_name = extract_feature_name(story_title)
        safe_feature_name = sanitize_filename(feature_name)

        # Generate CSV
        print(f"\n→ Generating CSV file...")
        csv_filename = f"{args.story_id}_{safe_feature_name}_Test_Cases.csv"
        csv_path = output_dir / csv_filename

        csv_gen = CSVGenerator()
        csv_gen.generate_csv(test_cases=test_cases, output_file=str(csv_path))
        print(f"✓ CSV: {csv_path}")

        # Generate objectives file
        print(f"\n→ Generating objectives file...")
        objectives_filename = f"{args.story_id}_{safe_feature_name}_Test_Objectives.txt"
        objectives_path = output_dir / objectives_filename

        obj_gen = ObjectiveGenerator()
        obj_gen.generate_objectives_file(test_cases, str(objectives_path))
        print(f"✓ Objectives: {objectives_path}")

        # Print summary
        print()
        print("=" * 80)
        print("✓ GENERATION COMPLETE")
        print("=" * 80)
        print(f"\nStory: {story_title}")
        print(f"Test Cases Generated: {len(test_cases)}")
        print(f"\nOutput Files:")
        print(f"  • CSV: {csv_path}")
        print(f"  • Objectives: {objectives_path}")
        print(f"\nNext Steps:")
        print(f"  1. Review generated test cases for accuracy")
        print(f"  2. Import CSV to Azure DevOps")
        print(f"  3. Run: python3 main.py upload-objectives --csv \"{csv_path}\"")
        print()

        # Print test case titles
        if args.verbose:
            print("\n" + "=" * 80)
            print("GENERATED TEST CASE TITLES")
            print("=" * 80)
            for tc in test_cases:
                print(f"  • {tc['title']}")
            print()

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def workflow_upload_objectives(args):
    """Workflow 2: Upload objectives to existing ADO test cases from CSV."""
    from update_objectives_from_csv import main as upload_main

    # Validate ADO_PAT
    if not config.ADO_PAT:
        print("ERROR: ADO_PAT environment variable is required")
        print("Set it with: export ADO_PAT='your_pat_here'")
        sys.exit(1)

    # Check CSV file exists
    if not os.path.exists(args.csv):
        print(f"ERROR: CSV file not found: {args.csv}")
        sys.exit(1)

    print("=" * 80)
    print("AI-TEST-GEN: UPLOAD OBJECTIVES TO ADO")
    print("=" * 80)
    print(f"CSV File: {args.csv}")
    if args.dry_run:
        print("MODE: DRY-RUN (no changes will be made)")
    print()

    # Call the upload function
    sys.argv = ['update_objectives_from_csv.py', args.csv]
    if args.dry_run:
        sys.argv.append('--dry-run')

    upload_main()


def main():
    """Main entry point with workflow routing."""
    parser = argparse.ArgumentParser(
        description='AI-Test-Gen: Comprehensive Evidence-Based Test Case Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflows:

  1. Generate test cases and objectives:
     python3 main.py generate --story-id 273166

  2. Upload objectives to ADO:
     python3 main.py upload-objectives --csv output/273166_Feature_Test_Cases.csv

Examples:

  # Generate test cases
  export ADO_PAT="your_pat_here"
  python3 main.py generate --story-id 273166

  # Generate with validation report
  python3 main.py generate --story-id 273166 --verbose

  # Skip grounding validation (not recommended)
  python3 main.py generate --story-id 273166 --skip-grounding

  # Upload objectives (dry-run first)
  python3 main.py upload-objectives --csv output/273166_Test_Cases.csv --dry-run
  python3 main.py upload-objectives --csv output/273166_Test_Cases.csv
        """
    )

    subparsers = parser.add_subparsers(dest='workflow', help='Workflow to execute')

    # Workflow 1: Generate
    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate test cases and objectives from story ID'
    )
    generate_parser.add_argument(
        '--story-id',
        type=int,
        required=True,
        help='Azure DevOps User Story ID'
    )
    generate_parser.add_argument(
        '--skip-grounding',
        action='store_true',
        help='Skip grounding validation (not recommended)'
    )
    generate_parser.add_argument(
        '--strict',
        action='store_true',
        help='Fail if grounding validation fails'
    )
    generate_parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed output including test case titles'
    )

    # Workflow 2: Upload objectives
    upload_parser = subparsers.add_parser(
        'upload-objectives',
        help='Upload objectives to existing ADO test cases from CSV'
    )
    upload_parser.add_argument(
        '--csv',
        type=str,
        required=True,
        help='Path to CSV file with test case IDs'
    )
    upload_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without uploading to ADO'
    )

    args = parser.parse_args()

    if not args.workflow:
        parser.print_help()
        sys.exit(1)

    # Route to workflow
    if args.workflow == 'generate':
        workflow_generate(args)
    elif args.workflow == 'upload-objectives':
        workflow_upload_objectives(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
