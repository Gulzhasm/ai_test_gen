#!/usr/bin/env python3
"""
Test Framework - Phase 1
Three main workflows:
1. Generate tests + objectives (CSV/TXT for debugging)
2. Update Summary field for existing tests
3. Generate + Upload directly to ADO test suite
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.balanced_test_builder import BalancedTestBuilder
from src.ado_client import ADOClient
from src.csv_generator import CSVGenerator
from src.objective_generator import ObjectiveGenerator
from src.quality_enforced_generator import QualityRules
from src.test_suite_uploader import TestSuiteUploader
import config


def workflow_1_generate(story_id: int):
    """Workflow 1: Generate comprehensive tests + objectives (CSV/TXT)."""
    print("=" * 80)
    print("WORKFLOW 1: GENERATE TESTS + OBJECTIVES")
    print("=" * 80)

    # Fetch story
    client = ADOClient()
    story_data = client.fetch_story_comprehensive(story_id)

    feature_name = story_data['title']
    acceptance_criteria = story_data['acceptance_criteria']

    print(f"\n→ Story: {feature_name}")
    print(f"→ ACs: {len(acceptance_criteria)}")

    # Extract context
    context = _extract_context(story_data)

    # Build tests
    builder = BalancedTestBuilder(story_id, feature_name)
    test_cases = _build_all_tests(builder, acceptance_criteria, context)

    # Validate
    print(f"\n→ Validating {len(test_cases)} tests...")
    validation_errors = []
    for tc in test_cases:
        errors = QualityRules.validate_test_case(tc)
        validation_errors.extend(errors)

    if validation_errors:
        print(f"  ✗ {len(validation_errors)} validation errors:")
        for err in validation_errors[:5]:
            print(f"    • {err}")
        return False

    print(f"  ✓ All tests passed validation")

    # Generate CSV
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)

    csv_gen = CSVGenerator()
    csv_file = output_dir / f"{story_id}_{_sanitize_filename(feature_name)}_TESTS.csv"
    csv_gen.generate_csv(test_cases=test_cases, output_file=str(csv_file))
    print(f"\n✓ CSV: {csv_file}")

    # Generate objectives
    obj_gen = ObjectiveGenerator()
    obj_file = output_dir / f"{story_id}_{_sanitize_filename(feature_name)}_OBJECTIVES.txt"
    obj_gen.generate_objectives_file(test_cases, str(obj_file))
    print(f"✓ Objectives: {obj_file}")

    print(f"\n{'=' * 80}")
    print(f"SUCCESS: Generated {len(test_cases)} tests")
    print(f"{'=' * 80}")
    return True


def workflow_2_update_summaries(csv_path: str, objectives_path: str):
    """Workflow 2: Update Summary field for existing tests."""
    print("=" * 80)
    print("WORKFLOW 2: UPDATE SUMMARIES")
    print("=" * 80)

    from update_objectives_from_uploaded_csv import update_objectives_from_csv

    result = update_objectives_from_csv(csv_path, objectives_path)

    if result:
        print(f"\n{'=' * 80}")
        print("SUCCESS: Updated all test summaries")
        print(f"{'=' * 80}")

    return result


def workflow_3_generate_and_upload(story_id: int):
    """Workflow 3: Generate tests + upload directly to ADO test suite."""
    print("=" * 80)
    print("WORKFLOW 3: GENERATE + UPLOAD TO TEST SUITE")
    print("=" * 80)

    # Fetch story
    client = ADOClient()
    story_data = client.fetch_story_comprehensive(story_id)

    feature_name = story_data['title']
    acceptance_criteria = story_data['acceptance_criteria']

    print(f"\n→ Story: {feature_name}")
    print(f"→ ACs: {len(acceptance_criteria)}")

    # Extract context
    context = _extract_context(story_data)

    # Build tests
    builder = BalancedTestBuilder(story_id, feature_name)
    test_cases = _build_all_tests(builder, acceptance_criteria, context)

    # Validate
    print(f"\n→ Validating {len(test_cases)} tests...")
    validation_errors = []
    for tc in test_cases:
        errors = QualityRules.validate_test_case(tc)
        validation_errors.extend(errors)

    if validation_errors:
        print(f"  ✗ {len(validation_errors)} validation errors:")
        for err in validation_errors[:5]:
            print(f"    • {err}")
        return False

    print(f"  ✓ All tests passed validation")

    # Generate debug files (CSV/TXT)
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)

    csv_gen = CSVGenerator()
    csv_file = output_dir / f"{story_id}_{_sanitize_filename(feature_name)}_DEBUG.csv"
    csv_gen.generate_csv(test_cases=test_cases, output_file=str(csv_file))
    print(f"\n→ Debug CSV: {csv_file}")

    obj_gen = ObjectiveGenerator()
    obj_file = output_dir / f"{story_id}_{_sanitize_filename(feature_name)}_DEBUG_OBJECTIVES.txt"
    obj_gen.generate_objectives_file(test_cases, str(obj_file))
    print(f"→ Debug Objectives: {obj_file}")

    # Find test suite
    print(f"\n→ Finding test suite for story {story_id}...")
    uploader = TestSuiteUploader(client)

    test_suite = uploader.find_test_suite_by_story_id(story_id)

    if not test_suite:
        print(f"  ✗ No test suite found for story {story_id}")
        return False

    print(f"  ✓ Found suite: {test_suite['name']} (ID: {test_suite['id']})")

    # Upload tests to suite
    print(f"\n→ Uploading {len(test_cases)} tests to suite...")
    uploaded_ids = uploader.upload_tests_to_suite(test_suite, test_cases)

    if not uploaded_ids:
        print(f"  ✗ Upload failed")
        return False

    print(f"  ✓ Uploaded {len(uploaded_ids)} tests")

    # Update objectives
    print(f"\n→ Updating objectives...")
    updated_count = uploader.update_test_objectives(uploaded_ids, test_cases)
    print(f"  ✓ Updated {updated_count} objectives")

    print(f"\n{'=' * 80}")
    print(f"SUCCESS: Uploaded {len(uploaded_ids)} tests to suite '{test_suite['name']}'")
    print(f"{'=' * 80}")
    return True


def _extract_context(story_data: dict) -> dict:
    """Extract context from story data."""
    description = story_data.get('description', '')
    acs = story_data.get('acceptance_criteria', [])
    qa = story_data.get('qa_prep', '')

    all_text = (description + ' ' + ' '.join(acs) + ' ' + qa).lower()

    context = {
        'entry_point': 'Properties Panel',
        'area': 'Canvas',
        'submenu_items': []
    }

    # Detect entry point
    if 'tools menu' in all_text:
        context['entry_point'] = 'Tools Menu'
    elif 'edit menu' in all_text:
        context['entry_point'] = 'Edit Menu'
    elif 'file menu' in all_text:
        context['entry_point'] = 'File Menu'
    elif 'properties panel' in all_text:
        context['entry_point'] = 'Properties Panel'

    # Detect area
    if 'dimensions panel' in all_text:
        context['area'] = 'Dimensions Panel'
    elif 'properties panel' in all_text:
        context['area'] = 'Properties Panel'

    return context


def _build_all_tests(builder, acceptance_criteria, context):
    """Build all test cases."""
    test_cases = []

    # AC1
    ac1 = builder.build_ac1_availability(context['entry_point'], context['submenu_items'])
    test_cases.append(ac1)

    # Primary AC tests
    for ac_idx, ac_bullet in enumerate(acceptance_criteria[1:], start=2):
        test_case = builder.build_primary_ac_test(ac_bullet, context['area'], ac_idx)
        test_cases.append(test_case)

        # Boundary tests for z-order operations
        if 'bring' in ac_bullet.lower() or 'send' in ac_bullet.lower():
            if 'front' in ac_bullet.lower():
                boundary = builder.build_boundary_test(ac_bullet, 'at_top', context['area'])
                test_cases.append(boundary)
            elif 'back' in ac_bullet.lower():
                boundary = builder.build_boundary_test(ac_bullet, 'at_bottom', context['area'])
                test_cases.append(boundary)

    # No selection boundary (if applicable)
    if any('bring' in ac.lower() or 'send' in ac.lower() for ac in acceptance_criteria):
        no_sel = builder.build_boundary_test(acceptance_criteria[1] if len(acceptance_criteria) > 1 else "",
                                             'no_selection', context['area'])
        test_cases.append(no_sel)

    # QA tests
    for qa_type in ['undo_redo', 'persistence', 'multi_select']:
        qa_test = builder.build_qa_test(qa_type, context['area'], context)
        test_cases.append(qa_test)

    # Accessibility tests
    for device in ['Windows 11', 'iPad', 'Android Tablet']:
        acc_test = builder.build_accessibility_test(device, context['area'])
        test_cases.append(acc_test)

    return test_cases


def _sanitize_filename(name: str) -> str:
    """Sanitize filename."""
    return name.replace(' ', '_').replace('/', '_').replace('—', '-')[:50]


def main():
    parser = argparse.ArgumentParser(
        description='Test Framework Phase 1',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='workflow', help='Workflow to run')

    # Workflow 1: Generate
    gen_parser = subparsers.add_parser('generate', help='Generate tests + objectives')
    gen_parser.add_argument('--story-id', type=int, required=True, help='Story ID')

    # Workflow 2: Update summaries
    update_parser = subparsers.add_parser('update-summaries', help='Update test summaries')
    update_parser.add_argument('--csv', required=True, help='Path to CSV file')
    update_parser.add_argument('--objectives', required=True, help='Path to objectives file')

    # Workflow 3: Generate + Upload
    upload_parser = subparsers.add_parser('generate-upload', help='Generate and upload to test suite')
    upload_parser.add_argument('--story-id', type=int, required=True, help='Story ID')

    args = parser.parse_args()

    if not config.ADO_PAT:
        print("ERROR: ADO_PAT environment variable not set")
        sys.exit(1)

    if args.workflow == 'generate':
        success = workflow_1_generate(args.story_id)
        sys.exit(0 if success else 1)

    elif args.workflow == 'update-summaries':
        success = workflow_2_update_summaries(args.csv, args.objectives)
        sys.exit(0 if success else 1)

    elif args.workflow == 'generate-upload':
        success = workflow_3_generate_and_upload(args.story_id)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
