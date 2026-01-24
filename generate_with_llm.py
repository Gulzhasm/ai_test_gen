#!/usr/bin/env python3
"""
LLM-Powered Test Case Generator CLI
Generates comprehensive, rule-compliant test cases using OpenAI GPT-4o-mini.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from src.ado_client import ADOClient
from llm.test_generator import LLMTestGenerator, convert_to_csv_format
import config


def generate_tests_with_llm(story_id: int, output_dir: str = "output", mode: str = "comprehensive") -> bool:
    """Generate test cases for a story using LLM.

    Args:
        story_id: The ADO story ID
        output_dir: Directory to save output files
        mode: Generation mode - "comprehensive" (default) or "standard"

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"LLM Test Generation for Story {story_id}")
    print(f"Mode: {mode.upper()}")
    print(f"{'='*60}\n")

    # Check OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        print("ERROR: OPENAI_API_KEY not configured in .env file")
        return False

    # Initialize clients
    try:
        ado_client = ADOClient()
    except ValueError as e:
        print(f"ERROR: {e}")
        return False

    llm_generator = LLMTestGenerator(
        api_key=api_key,
        model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        mode=mode
    )

    # Step 1: Fetch story data from ADO
    print("Step 1: Fetching story data from ADO...")
    try:
        story_data = ado_client.fetch_story_comprehensive(story_id)
    except Exception as e:
        print(f"ERROR: Failed to fetch story: {e}")
        return False

    title = story_data['title']
    description = story_data['description']
    acceptance_criteria = story_data['acceptance_criteria']
    qa_prep = story_data['qa_prep']

    print(f"  Title: {title}")
    print(f"  Description: {len(description)} chars")
    print(f"  Acceptance Criteria: {len(acceptance_criteria)} bullets")
    print(f"  QA Prep: {len(qa_prep)} chars")

    if not acceptance_criteria:
        print("ERROR: No acceptance criteria found in story")
        return False

    # Extract feature name from title (usually the main part)
    feature_name = title

    # Step 2: Generate test cases with LLM
    print(f"\nStep 2: Generating test cases with {config.LLM_MODEL}...")
    result = llm_generator.generate_test_cases(
        story_id=str(story_id),
        feature_name=feature_name,
        description=description,
        acceptance_criteria=acceptance_criteria,
        qa_prep=qa_prep,
        area_path=config.ADO_AREA_PATH,
        assigned_to=config.ASSIGNED_TO
    )

    if not result or 'test_cases' not in result:
        print("ERROR: LLM test generation failed")
        return False

    test_cases = result['test_cases']
    print(f"  Generated {len(test_cases)} test cases")

    # Step 3: Generate objectives
    print("\nStep 3: Generating test objectives...")
    objectives_result = llm_generator.generate_objectives(test_cases)

    # Step 4: Save outputs
    print("\nStep 4: Saving outputs...")
    os.makedirs(output_dir, exist_ok=True)

    # Clean title for filename
    safe_title = "".join(c if c.isalnum() or c in ' _-' else '_' for c in title)
    safe_title = safe_title.replace(' ', '_')[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save CSV
    csv_filename = f"{story_id}_{safe_title}_LLM_TESTS.csv"
    csv_path = os.path.join(output_dir, csv_filename)

    csv_rows = convert_to_csv_format(test_cases)
    fieldnames = ["ID", "Work Item Type", "Title", "TestStep", "Step Action", "Step Expected", "Area Path", "AssignedTo", "State"]

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"  CSV saved: {csv_path}")

    # Save objectives
    if objectives_result and 'objectives' in objectives_result:
        objectives_filename = f"{story_id}_{safe_title}_LLM_OBJECTIVES.txt"
        objectives_path = os.path.join(output_dir, objectives_filename)

        with open(objectives_path, 'w', encoding='utf-8') as f:
            for obj in objectives_result['objectives']:
                f.write(f"{obj.get('test_case_id', 'XX')}: {obj.get('title', 'Unknown')}\n")
                f.write(f"{obj.get('objective', 'No objective')}\n\n")

        print(f"  Objectives saved: {objectives_path}")

    # Save raw JSON for debugging
    json_filename = f"{story_id}_{safe_title}_LLM_DEBUG.json"
    json_path = os.path.join(output_dir, json_filename)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'story_id': story_id,
            'title': title,
            'acceptance_criteria': acceptance_criteria,
            'test_cases': test_cases,
            'objectives': objectives_result.get('objectives', []) if objectives_result else []
        }, f, indent=2)

    print(f"  Debug JSON saved: {json_path}")

    # Summary
    print(f"\n{'='*60}")
    print("GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Story: {story_id} - {title}")
    print(f"  Test cases generated: {len(test_cases)}")
    print(f"  Output directory: {output_dir}")
    print(f"\nFiles created:")
    print(f"  - {csv_filename}")
    if objectives_result:
        print(f"  - {objectives_filename}")
    print(f"  - {json_filename}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate test cases using OpenAI LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_with_llm.py --story-id 273167
  python generate_with_llm.py --story-id 273167 --output-dir ./my_tests
        """
    )

    parser.add_argument(
        '--story-id',
        type=int,
        required=True,
        help='ADO Story ID to generate tests for'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for generated files (default: output)'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['comprehensive', 'standard'],
        default='comprehensive',
        help='Generation mode: comprehensive (default) adds edge checks, standard is minimal'
    )

    args = parser.parse_args()

    success = generate_tests_with_llm(
        story_id=args.story_id,
        output_dir=args.output_dir,
        mode=args.mode
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
