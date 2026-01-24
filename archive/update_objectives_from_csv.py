#!/usr/bin/env python3
"""
Generic script to update test case Summary fields in ADO with objectives based on CSV titles.

Usage:
    python update_objectives_from_csv.py <csv_file_path>

Example:
    python update_objectives_from_csv.py output/Env_Drawing_Project_Phase_1_270738_Undo_Redo_Functionality.csv

The CSV file must contain columns:
    - ID: ADO work item ID (e.g., "278025")
    - Work Item Type: Should be "Test Case"
    - Title: Test case title (format: "StoryID-ID: Feature / Area / Scenario")
"""
import csv
import sys
import os
import re
import argparse
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ado_client import ADOClient
from src.test_generator import TestGenerator
from src.objective_generator import ObjectiveGenerator
import config


def parse_csv_for_test_cases(csv_file_path: str) -> List[Dict]:
    """Parse CSV file to extract test case IDs and titles.
    
    Args:
        csv_file_path: Path to the CSV file
        
    Returns:
        List of dictionaries with 'work_item_id', 'title', 'test_case_id' (e.g., "270738-AC1")
    """
    test_cases = []
    
    try:
        with open(csv_file_path, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = [h.strip() for h in next(reader)]  # Read header
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                row_dict = dict(zip(header, row))
                
                # Check if this is a test case header row
                work_item_id = row_dict.get('ID', '').strip().strip('"')
                work_item_type = row_dict.get('Work Item Type', '').strip()
                title = row_dict.get('Title', '').strip().strip('"')
                
                if work_item_id and work_item_type == 'Test Case' and title:
                    # Extract test case ID from title (e.g., "270738-AC1" from "270738-AC1: Undo Redo / ...")
                    test_case_id_match = re.match(r'(\d+-(AC1|\d{3})):', title)
                    test_case_id = test_case_id_match.group(1) if test_case_id_match else None
                    
                    test_cases.append({
                        'work_item_id': int(work_item_id),
                        'title': title,
                        'test_case_id': test_case_id,  # e.g., "270738-AC1"
                        'row_number': row_num
                    })
    except FileNotFoundError:
        print(f"ERROR: CSV file not found: {csv_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to parse CSV file: {e}")
        sys.exit(1)
    
    return test_cases


def generate_objective_from_title(title: str, test_generator: TestGenerator) -> str:
    """Generate objective from test case title using existing TestGenerator rules.
    
    Args:
        title: Test case title (format: "StoryID-ID: Feature / Area / Scenario")
        test_generator: TestGenerator instance
        
    Returns:
        Objective text starting with "Verify that"
    """
    # Parse title to extract components
    # Format: "270738-AC1: Undo Redo / Toolbar and Edit Menu / Undo Redo Controls Available and Disabled State"
    title_parts = []
    if ': ' in title:
        title_without_id = title.split(': ', 1)[-1]
        if ' / ' in title_without_id:
            title_parts = [p.strip() for p in title_without_id.split(' / ')]
    
    # Extract feature, area, scenario
    feature = title_parts[0] if len(title_parts) > 0 else "Feature"
    area = title_parts[1] if len(title_parts) > 1 else ""
    scenario = title_parts[2] if len(title_parts) > 2 else title_parts[-1] if title_parts else ""
    
    # Extract device from title if present
    device = None
    if '(Windows 11)' in title:
        device = "Windows 11"
    elif '(iPad)' in title:
        device = "iPad"
    elif '(Android Tablet)' in title:
        device = "Android Tablet"
    elif '(Tablets)' in title:
        device = "Tablets"
    
    # Determine if accessibility test
    is_accessibility = 'Section 508' in title or 'WCAG' in title or 'Accessibility' in area
    
    # Determine UI area from area or feature
    ui_area = area if area else feature
    
    # Generate objective using TestGenerator (uses existing rules)
    objective = test_generator.generate_objective(
        title=title,
        scenario=scenario,
        feature=feature,
        category=area,
        ui_area=ui_area,
        device=device,
        is_accessibility=is_accessibility
    )
    
    return objective


def format_objective_for_ado_summary(objective_text: str, objective_gen: ObjectiveGenerator) -> str:
    """Format objective for ADO Summary field - ONLY the objective text, no ID/title prefix.
    
    Format: <b>Objective:</b> Verify that ...
    
    Args:
        objective_text: Objective text (should start with "Verify that")
        objective_gen: ObjectiveGenerator instance
        
    Returns:
        HTML-formatted objective string
    """
    # Remove "Verify that" prefix if present (will be added by format_objective_for_ado)
    objective_clean = objective_text.strip()
    if objective_clean.lower().startswith('verify that '):
        objective_clean = objective_clean[12:]
    
    # Format: <b>Objective:</b> Verify that ...
    formatted = objective_gen.format_objective_for_ado(objective_clean)
    
    return formatted


def update_test_summary(work_item_id: int, objective_html: str, client: ADOClient) -> bool:
    """Update a test case's Summary field (System.Description) in ADO.
    
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
            work_item_id,
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


def main():
    """Main function to update objectives from CSV."""
    parser = argparse.ArgumentParser(
        description='Update ADO test case Summary fields with objectives based on CSV titles.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_objectives_from_csv.py output/test_cases.csv
  python update_objectives_from_csv.py "output/Env Drawing Project _ Phase 1_270738 _ Undo _ Redo Functionality (2).csv"

CSV Format Requirements:
  - Must contain columns: ID, Work Item Type, Title
  - ID: ADO work item ID (e.g., "278025")
  - Work Item Type: Should be "Test Case"
  - Title: Test case title (format: "StoryID-ID: Feature / Area / Scenario")
        """
    )
    parser.add_argument(
        'csv_file',
        help='Path to CSV file containing test case IDs and titles'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without actually updating ADO'
    )
    
    args = parser.parse_args()
    csv_file_path = args.csv_file
    
    if not os.path.exists(csv_file_path):
        print(f"ERROR: CSV file not found: {csv_file_path}")
        sys.exit(1)
    
    if not config.ADO_PAT:
        print("ERROR: ADO_PAT environment variable is required")
        print("Set it with: export ADO_PAT='your_pat_here'")
        sys.exit(1)
    
    print("=" * 80)
    print("UPDATING TEST CASE OBJECTIVES FROM CSV")
    print("=" * 80)
    print(f"CSV File: {csv_file_path}")
    if args.dry_run:
        print("DRY-RUN MODE: No changes will be made to ADO")
    print()
    
    # Parse CSV
    print("Step 1: Parsing CSV file...")
    test_cases = parse_csv_for_test_cases(csv_file_path)
    print(f"✓ Found {len(test_cases)} test cases in CSV")
    
    if not test_cases:
        print("ERROR: No test cases found in CSV")
        print("Ensure CSV contains rows with:")
        print("  - ID: ADO work item ID")
        print("  - Work Item Type: 'Test Case'")
        print("  - Title: Test case title")
        sys.exit(1)
    
    # Initialize clients
    print("\nStep 2: Initializing ADO client and generators...")
    client = ADOClient()
    test_generator = TestGenerator()
    objective_gen = ObjectiveGenerator()
    print("✓ Initialized")
    
    # Generate objectives and update ADO
    print("\nStep 3: Generating objectives and updating ADO...")
    updated_count = 0
    failed_count = 0
    objectives_summary = []
    
    for idx, tc in enumerate(test_cases, start=1):
        work_item_id = tc['work_item_id']
        title = tc['title']
        test_case_id = tc['test_case_id']
        
        print(f"\n[{idx}/{len(test_cases)}] Test Case ID: {work_item_id}")
        print(f"  Title: {title}")
        
        # Generate objective from title
        try:
            objective_text = generate_objective_from_title(title, test_generator)
            print(f"  Generated objective: {objective_text[:100]}...")
            
            # Format for ADO (NO ID/title prefix)
            objective_html = format_objective_for_ado_summary(objective_text, objective_gen)
            
            # Store for summary
            objectives_summary.append({
                'work_item_id': work_item_id,
                'test_case_id': test_case_id,
                'title': title,
                'objective': objective_text,
                'objective_html': objective_html
            })
            
            if args.dry_run:
                print(f"  [DRY-RUN] Would update Summary field")
                updated_count += 1
            else:
                # Update in ADO
                if update_test_summary(work_item_id, objective_html, client):
                    print(f"  ✓ Successfully updated Summary field")
                    updated_count += 1
                else:
                    print(f"  ✗ Failed to update Summary field")
                    failed_count += 1
                    
        except Exception as e:
            print(f"  ✗ Error processing test case: {e}")
            failed_count += 1
    
    # Final summary
    print("\n" + "=" * 80)
    print("UPDATE COMPLETED")
    print("=" * 80)
    print(f"Total test cases processed: {len(test_cases)}")
    print(f"Successfully updated: {updated_count}")
    print(f"Failed: {failed_count}")
    
    # Print objectives summary
    if objectives_summary:
        print("\n" + "=" * 80)
        print("UPDATED OBJECTIVES SUMMARY")
        print("=" * 80)
        for obj in objectives_summary:
            print(f"\nTest Case ID: {obj['work_item_id']}")
            if obj['test_case_id']:
                print(f"Test Case Prefix: {obj['test_case_id']}")
            print(f"Title: {obj['title']}")
            print(f"Objective: {obj['objective']}")
            print("-" * 80)
    
    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
