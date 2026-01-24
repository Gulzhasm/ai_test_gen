#!/usr/bin/env python3
"""
Update ADO test case Summary fields with objectives using CSV with ADO IDs.

This script:
1. Reads CSV file with ADO work item IDs (already uploaded)
2. Reads objectives TXT file
3. Maps objectives to ADO IDs by test case ID (272264-AC1, 272264-005, etc.)
4. Updates Summary field in ADO for each test case

Usage:
    python3 update_objectives_from_uploaded_csv.py <CSV_FILE> <OBJECTIVES_FILE> [--dry-run]

Example:
    python3 update_objectives_from_uploaded_csv.py \\
        "output/Env Drawing Project _ Phase 1_272264 _ Line Style Options — Color, Thickness, Dashed Line.csv" \\
        "output/272264_Line_Style_Options_—_Color,_Thickness,_Dashed_Line_Test_Objectives.txt" \\
        --dry-run
"""
import csv
import sys
import os
import re
import argparse
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ado_client import ADOClient
import config


def parse_csv_for_ado_ids(csv_file_path: str) -> Dict[str, str]:
    """
    Parse CSV file to extract ADO work item IDs and their test case IDs.

    Args:
        csv_file_path: Path to uploaded CSV with ADO IDs

    Returns:
        Dict mapping test_case_id (e.g., "272264-AC1") to ADO work_item_id (e.g., "278255")
    """
    ado_id_map = {}

    try:
        with open(csv_file_path, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = [h.strip() for h in next(reader)]  # Read header

            for row_num, row in enumerate(reader, start=2):
                row_dict = dict(zip(header, row))

                # Check if this is a test case header row
                work_item_id = row_dict.get('ID', '').strip().strip('"')
                work_item_type = row_dict.get('Work Item Type', '').strip().strip('"')
                title = row_dict.get('Title', '').strip().strip('"')

                if work_item_id and work_item_type == 'Test Case' and title:
                    # Extract test case ID from title (e.g., "272264-AC1" from "272264-AC1: Line Style...")
                    test_case_id_match = re.match(r'(\d+-(AC1|\d{3})):', title)
                    if test_case_id_match:
                        test_case_id = test_case_id_match.group(1)
                        ado_id_map[test_case_id] = work_item_id

    except FileNotFoundError:
        print(f"ERROR: CSV file not found: {csv_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to parse CSV file: {e}")
        sys.exit(1)

    return ado_id_map


def parse_objectives_file(objectives_file_path: str) -> Dict[str, str]:
    """
    Parse objectives TXT file to extract objectives by test case ID.

    Args:
        objectives_file_path: Path to objectives TXT file

    Returns:
        Dict mapping test_case_id to objective HTML
    """
    objectives_map = {}

    try:
        with open(objectives_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by double newline to separate test cases
        blocks = content.strip().split('\n\n')

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 2:
                # First line: test case ID and title
                first_line = lines[0]
                # Extract test case ID (e.g., "272264-AC1")
                test_case_id_match = re.match(r'(\d+-(AC1|\d{3})):', first_line)
                if test_case_id_match:
                    test_case_id = test_case_id_match.group(1)

                    # Second line: objective
                    if len(lines) > 1:
                        objective_html = lines[1].strip()

                        # Clean up duplicate "Verify that" if present
                        # Format: "Objective: Verify that Verify that ..." -> "Objective: Verify that ..."
                        objective_html = re.sub(r'(<b>Objective:</b>\s+Verify that\s+)Verify that\s+', r'\1', objective_html, flags=re.IGNORECASE)

                        objectives_map[test_case_id] = objective_html

    except FileNotFoundError:
        print(f"ERROR: Objectives file not found: {objectives_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to parse objectives file: {e}")
        sys.exit(1)

    return objectives_map


def update_test_summary(work_item_id: str, objective_html: str, client: ADOClient) -> bool:
    """
    Update a test case's Summary field (System.Description) in ADO.

    Args:
        work_item_id: ADO work item ID
        objective_html: HTML-formatted objective text
        client: ADOClient instance

    Returns:
        True if successful, False otherwise
    """
    try:
        # Update System.Description field using replace operation
        result = client.update_work_item_field(
            int(work_item_id),
            'System.Description',
            objective_html,
            operation='replace'
        )

        return result is not None

    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail.get('message', e.response.text[:200])}"
            except:
                error_msg += f" - {e.response.text[:200]}"
        print(f"      ✗ Error updating test case {work_item_id}: {error_msg}")
        return False


def update_objectives_from_csv(csv_file_path: str, objectives_file_path: str, dry_run: bool = False) -> bool:
    """
    Update ADO test case Summary fields with objectives from CSV.

    Args:
        csv_file_path: Path to CSV file with ADO IDs (exported from ADO)
        objectives_file_path: Path to objectives TXT file
        dry_run: If True, show what would be updated without actually updating

    Returns:
        True if all updates succeeded, False otherwise
    """
    if not os.path.exists(csv_file_path):
        print(f"ERROR: CSV file not found: {csv_file_path}")
        return False

    if not os.path.exists(objectives_file_path):
        print(f"ERROR: Objectives file not found: {objectives_file_path}")
        return False

    if not config.ADO_PAT:
        print("ERROR: ADO_PAT environment variable is required")
        print("Set it with: export ADO_PAT='your_pat_here'")
        return False

    print(f"CSV File: {csv_file_path}")
    print(f"Objectives File: {objectives_file_path}")
    if dry_run:
        print("DRY-RUN MODE: No changes will be made to ADO")
    print()

    # Step 1: Parse CSV to get ADO IDs
    print("Step 1: Parsing CSV file for ADO work item IDs...")
    ado_id_map = parse_csv_for_ado_ids(csv_file_path)
    print(f"✓ Found {len(ado_id_map)} test cases with ADO IDs")

    if not ado_id_map:
        print("ERROR: No test cases with ADO IDs found in CSV")
        return False

    # Step 2: Parse objectives file
    print("\nStep 2: Parsing objectives file...")
    objectives_map = parse_objectives_file(objectives_file_path)
    print(f"✓ Found {len(objectives_map)} objectives")

    if not objectives_map:
        print("ERROR: No objectives found in objectives file")
        return False

    # Step 3: Match and update
    print("\nStep 3: Matching and updating ADO test cases...")
    client = ADOClient()
    updated_count = 0
    failed_count = 0
    skipped_count = 0

    for test_case_id, ado_id in sorted(ado_id_map.items()):
        print(f"\n[{test_case_id}] ADO ID: {ado_id}")

        if test_case_id not in objectives_map:
            print(f"  ⚠ No objective found for {test_case_id}, skipping")
            skipped_count += 1
            continue

        objective_html = objectives_map[test_case_id]
        print(f"  Objective: {objective_html[:100]}...")

        if dry_run:
            print(f"  [DRY-RUN] Would update Summary field")
            updated_count += 1
        else:
            # Update in ADO
            if update_test_summary(ado_id, objective_html, client):
                print(f"  ✓ Successfully updated Summary field")
                updated_count += 1
            else:
                print(f"  ✗ Failed to update Summary field")
                failed_count += 1

    # Final summary
    print("\n" + "-" * 40)
    print(f"Total test cases in CSV: {len(ado_id_map)}")
    print(f"Successfully updated: {updated_count}")
    print(f"Failed: {failed_count}")
    print(f"Skipped (no objective): {skipped_count}")

    return failed_count == 0


def main():
    """Main function to update objectives from uploaded CSV."""
    parser = argparse.ArgumentParser(
        description='Update ADO test case Summary fields with objectives from uploaded CSV.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 update_objectives_from_uploaded_csv.py \\
      "output/272264_uploaded.csv" \\
      "output/272264_Test_Objectives.txt" \\
      --dry-run

  python3 update_objectives_from_uploaded_csv.py \\
      "output/272264_uploaded.csv" \\
      "output/272264_Test_Objectives.txt"

CSV Format Requirements:
  - Must be exported from ADO after uploading test cases
  - Must contain columns: ID, Work Item Type, Title
  - ID column has ADO work item IDs (e.g., 278255)
  - Title contains test case ID (e.g., "272264-AC1: Line Style...")

Objectives File Format:
  - First line: <TEST_CASE_ID>: <Title>
  - Second line: Objective: Verify that ...
  - Blank line between test cases
        """
    )
    parser.add_argument(
        'csv_file',
        help='Path to CSV file with ADO IDs (exported from ADO)'
    )
    parser.add_argument(
        'objectives_file',
        help='Path to objectives TXT file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without actually updating ADO'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("UPDATING TEST CASE OBJECTIVES FROM UPLOADED CSV")
    print("=" * 80)

    success = update_objectives_from_csv(args.csv_file, args.objectives_file, args.dry_run)

    print("\n" + "=" * 80)
    print("UPDATE COMPLETED" if success else "UPDATE FAILED")
    print("=" * 80)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
