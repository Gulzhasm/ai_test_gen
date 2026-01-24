#!/usr/bin/env python3
"""
AI-Test-Gen with Improved Evidence-Based Generator.

This version uses the improved generator that prevents invented context
and generates comprehensive test cases based solely on evidence.

Usage:
    export ADO_PAT="your_pat_here"
    python main_improved.py --story-id <ADO_STORY_ID>
    python main_improved.py --story-id <ADO_STORY_ID> --upload
"""
import argparse
import sys
import os
import re
from pathlib import Path

import config
from src.ado_client import ADOClient
from src.test_generator_improved import ImprovedTestGenerator
from src.csv_generator import CSVGenerator
from src.objective_generator import ObjectiveGenerator
from src.qa_summary_generator import QASummaryGenerator
from src.validator import TestCaseValidator
from src.test_plan_finder import TestPlanFinder
from src.test_case_uploader import TestCaseUploader
from core.services.grounding_validator import GroundingValidator
from core.domain.grounded_spec import GroundedSpec


def sanitize_filename(text: str) -> str:
    """Sanitize text for use in filenames."""
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
                title = parts[1].strip() if len(parts) > 1 else title.replace(prefix, '').strip()
            else:
                title = title.replace(prefix, '').strip()
            break
    return title


def main():
    parser = argparse.ArgumentParser(
        description="""AI-Test-Gen with Improved Evidence-Based Generator.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  export ADO_PAT="your_pat_here"
  python main_improved.py --story-id 272780

  python main_improved.py --story-id 272780 --upload
  python main_improved.py --story-id 272780 --skip-summary
  python main_improved.py --story-id 272780 --validation-report
        """
    )
    parser.add_argument('--story-id', type=int, required=True,
                        help='Azure DevOps User Story ID')
    parser.add_argument('--upload', action='store_true',
                        help='Upload test cases directly to ADO')
    parser.add_argument('--plan-id', type=int, default=None,
                        help='Test Plan ID (if not provided, will auto-discover)')
    parser.add_argument('--suite-id', type=int, default=None,
                        help='Test Suite ID (if not provided, will auto-discover)')
    parser.add_argument('--project', type=str, default=None,
                        help=f'ADO Project name (default: {config.ADO_PROJECT})')
    parser.add_argument('--org', type=str, default=None,
                        help=f'ADO Organization (default: {config.ADO_ORG})')
    parser.add_argument('--area-path', type=str, default=None,
                        help=f'Area Path (default: {config.ADO_AREA_PATH})')
    parser.add_argument('--dry-run', action='store_true',
                        help='Generate files without validating against ADO')
    parser.add_argument('--skip-summary', action='store_true',
                        help='Skip QA Planning Summary generation')
    parser.add_argument('--validation-report', action='store_true',
                        help='Generate detailed grounding validation report')
    args = parser.parse_args()

    # Validate ADO_PAT
    if not config.ADO_PAT:
        print("ERROR: ADO_PAT environment variable is required")
        print("Set it with: export ADO_PAT='your_pat_here'")
        sys.exit(1)

    # Override config if provided
    if args.project:
        config.ADO_PROJECT = args.project
    if args.org:
        config.ADO_ORG = args.org
    if args.area_path:
        config.ADO_AREA_PATH = args.area_path

    print("=" * 80)
    print(f"AI-Test-Gen - Improved Evidence-Based Generator")
    print("=" * 80)
    print(f"Story ID: {args.story_id}")
    print(f"Project: {config.ADO_PROJECT}")
    print(f"Organization: {config.ADO_ORG}")
    print()

    # Initialize ADO client
    try:
        ado_client = ADOClient()
    except Exception as e:
        print(f"✗ Failed to initialize ADO client: {e}")
        sys.exit(1)

    # Fetch story data
    print(f"→ Fetching story {args.story_id} from ADO...")
    try:
        story_data = ado_client.extract_story_data(args.story_id)
        story_data['story_id'] = args.story_id  # Add story_id to dict
        story_title = story_data.get('title', 'Unknown')
        print(f"✓ Story: {story_title}")
    except Exception as e:
        print(f"✗ Failed to fetch story: {e}")
        sys.exit(1)

    # Parse acceptance criteria
    print(f"→ Parsing acceptance criteria...")
    ac_text = story_data.get('acceptance_criteria_text', '')
    if not ac_text:
        print("✗ No acceptance criteria found")
        sys.exit(1)

    criteria = ado_client.parse_acceptance_criteria(ac_text)
    print(f"✓ Found {len(criteria)} acceptance criteria")

    # Get QA Prep
    print(f"→ Fetching QA Prep content...")
    qa_prep_content = None
    try:
        qa_prep_content = ado_client.retrieve_qa_prep_subtask(args.story_id)
        if qa_prep_content:
            print(f"✓ QA Prep content found")
        else:
            print(f"⚠ No QA Prep content found (will use AC only)")
    except Exception as e:
        print(f"⚠ Failed to fetch QA Prep: {e}")

    # Generate test cases using improved generator
    print()
    print("=" * 80)
    print("GENERATING TEST CASES (IMPROVED EVIDENCE-BASED GENERATOR)")
    print("=" * 80)

    generator = ImprovedTestGenerator()
    test_cases = generator.generate_test_cases(story_data, criteria, qa_prep_content)

    print()
    print("=" * 80)
    print(f"✓ Generated {len(test_cases)} test cases")
    print("=" * 80)

    # Validate test cases
    print()
    print("→ Validating test cases...")
    validator = TestCaseValidator()
    is_valid, errors = validator.validate_test_cases(test_cases)

    if not is_valid:
        print(f"✗ Validation failed with {len(errors)} errors:")
        for error in errors[:20]:
            print(f"  ✗ {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")
        print()
        print("⚠ Continuing with test case generation despite validation errors...")
    else:
        print(f"✓ All test cases passed validation")

    # Generate grounding validation report if requested
    if args.validation_report:
        print()
        print("=" * 80)
        print("GROUNDING VALIDATION REPORT")
        print("=" * 80)
        grounded_spec = GroundedSpec.from_story_data(story_data, criteria, qa_prep_content)
        grounding_validator = GroundingValidator(grounded_spec)
        report = grounding_validator.generate_validation_report(test_cases)
        print(report)

        # Save report to file
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)
        report_file = output_dir / f"{args.story_id}_grounding_validation_report.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"✓ Validation report saved to {report_file}")

    # Generate objectives
    print()
    print("→ Generating objectives...")
    obj_generator = ObjectiveGenerator()
    objectives = {}
    for tc in test_cases:
        if 'objective' in tc:
            objectives[tc['id']] = tc['objective']
    print(f"✓ Generated {len(objectives)} objectives")

    # Generate objectives file
    feature_name = extract_feature_name(story_title)
    safe_feature_name = sanitize_filename(feature_name)
    objectives_filename = f"{args.story_id}_{safe_feature_name}_Test_Objectives_IMPROVED.txt"
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    objectives_path = output_dir / objectives_filename
    obj_generator.generate_objectives_file(test_cases, str(objectives_path))
    print(f"✓ Objectives file saved to {objectives_path}")

    # Generate QA Planning Summary (if not skipped)
    if not args.skip_summary:
        print()
        print("→ Generating QA Planning Summary...")
        summary_generator = QASummaryGenerator()
        summary = summary_generator.generate_summary(story_data, test_cases)
        print(f"✓ Generated QA Planning Summary")
    else:
        summary = None
        print("⚠ Skipped QA Planning Summary generation")

    # Generate CSV files
    print()
    print("→ Generating CSV files...")
    csv_filename = f"{args.story_id}_{safe_feature_name}_Test_Cases_IMPROVED.csv"
    csv_path = output_dir / csv_filename

    csv_gen = CSVGenerator()
    csv_gen.generate_csv(
        test_cases=test_cases,
        output_file=str(csv_path)
    )

    print(f"✓ CSV saved to {csv_path}")

    # Upload to ADO if requested
    if args.upload:
        print()
        print("=" * 80)
        print("UPLOADING TEST CASES TO ADO")
        print("=" * 80)

        # Find test plan and suite
        print(f"→ Finding test plan and suite...")
        test_plan_finder = TestPlanFinder(ado_client)

        if args.plan_id and args.suite_id:
            plan_id = args.plan_id
            suite_id = args.suite_id
            print(f"✓ Using provided Plan ID: {plan_id}, Suite ID: {suite_id}")
        else:
            plan_id, suite_id = test_plan_finder.find_test_plan_and_suite(args.story_id)
            if not plan_id or not suite_id:
                print("✗ Could not find test plan and suite. Provide --plan-id and --suite-id")
                sys.exit(1)
            print(f"✓ Found Plan ID: {plan_id}, Suite ID: {suite_id}")

        # Upload test cases
        print(f"→ Uploading {len(test_cases)} test cases...")
        uploader = TestCaseUploader(ado_client)

        try:
            created_ids = uploader.upload_test_cases(
                test_cases=test_cases,
                story_id=args.story_id,
                plan_id=plan_id,
                suite_id=suite_id,
                area_path=config.ADO_AREA_PATH
            )
            print(f"✓ Uploaded {len(created_ids)} test cases")
        except Exception as e:
            print(f"✗ Failed to upload test cases: {e}")
            sys.exit(1)

        # Upload objectives
        if objectives:
            print(f"→ Uploading objectives...")
            try:
                for tc_id, objective in objectives.items():
                    uploader.update_test_case_objective(tc_id, objective)
                print(f"✓ Uploaded {len(objectives)} objectives")
            except Exception as e:
                print(f"✗ Failed to upload objectives: {e}")

        # Upload QA Planning Summary
        if summary and not args.skip_summary:
            print(f"→ Uploading QA Planning Summary...")
            try:
                ado_client.update_work_item(args.story_id, {'QA Planning Summary': summary})
                print(f"✓ Uploaded QA Planning Summary")
            except Exception as e:
                print(f"✗ Failed to upload summary: {e}")

    print()
    print("=" * 80)
    print("✓ COMPLETE")
    print("=" * 80)
    print(f"Generated {len(test_cases)} comprehensive test cases")
    print(f"CSV: {csv_path}")
    print(f"Objectives: {objectives_path}")
    if args.validation_report:
        print(f"Validation Report: {output_dir / f'{args.story_id}_grounding_validation_report.txt'}")
    print()


if __name__ == '__main__':
    main()
