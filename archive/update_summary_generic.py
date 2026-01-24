#!/usr/bin/env python3
"""
Generic script to update Summary field (System.Description) for test cases in ADO.

Usage:
    python update_summary_generic.py <story_id>
        OR
    python update_summary_generic.py --csv <csv_file_path> [--objectives <objectives_file_path>]

Examples:
    python update_summary_generic.py 272981
    python update_summary_generic.py --csv output/272981_Test_Cases.csv
    python update_summary_generic.py --csv output/272981_Test_Cases.csv --objectives output/272981_Test_Objectives.txt
"""

import sys
import os
import csv
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ado_client import ADOClient
import config


def parse_objectives_file(filename: str) -> Dict[str, str]:
    """Parse objectives file and return dictionary mapping test case IDs to objectives.
    
    Expected format:
        272981-AC1: Title
        Objective: Objective text
        
        272981-005: Title
        Objective: Objective text
    """
    objectives = {}
    
    if not os.path.exists(filename):
        print(f"Error: Objectives file not found: {filename}")
        return objectives
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern matches: "272981-AC1: Title\nObjective: Objective text"
    pattern = r'(\d{6}-[\w\d]+):\s*(.+?)\nObjective:\s*(.+?)(?=\n\d{6}-|\Z)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        test_case_id = match.group(1)
        objective = match.group(3).strip()
        objectives[test_case_id] = objective
    
    return objectives


def parse_csv_file(filename: str) -> List[Dict[str, str]]:
    """Parse CSV file to extract test case information.
    
    Returns list of dicts with 'title' and optionally 'id' (work item ID).
    """
    test_cases = []
    
    if not os.path.exists(filename):
        print(f"Error: CSV file not found: {filename}")
        return test_cases
    
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Handle BOM in ID column
            id_key = 'ID' if 'ID' in row else '\ufeffID'
            work_item_id = row.get(id_key, '').strip('"').strip()
            title = row.get('Title', '').strip('"').strip()
            
            if title and title != 'Title':
                test_case = {
                    'title': title,
                    'id': work_item_id if work_item_id and work_item_id != 'ID' else None
                }
                test_cases.append(test_case)
    
    return test_cases


def extract_test_case_id_from_title(title: str) -> Optional[str]:
    """Extract test case ID from title (e.g., '272981-AC1: Help: About App...' -> '272981-AC1')."""
    match = re.match(r'(\d{6}-[\w\d]+):', title)
    if match:
        return match.group(1)
    return None


def find_test_case_by_title(client: ADOClient, title: str) -> Optional[int]:
    """Find work item ID by title using WIQL."""
    escaped_title = title.replace("'", "''")
    wiql_query = {
        "query": f"Select [System.Id] From WorkItems Where [System.WorkItemType]='Test Case' And [System.Title]='{escaped_title}'"
    }
    
    url = f"{client.base_url}/_apis/wit/wiql?api-version=7.1"
    try:
        import requests
        response_obj = requests.post(url, headers=client.headers, json=wiql_query)
        
        if response_obj.status_code == 200:
            data = response_obj.json()
            work_items = data.get('workItems', [])
            if work_items:
                return work_items[0]['id']
    except Exception as e:
        print(f"    Warning: Could not find test case by title: {e}")
    
    return None


def format_objective_with_bold(objective_text: str) -> str:
    """Format objective text with bold 'Objective:' and important words."""
    formatted = "<b>Objective:</b> "
    
    # Important terms to bold (generic list that works for most features)
    important_terms = [
        # Multi-word phrases (longest first to avoid partial matches)
        (r'Accessibility Insights for Windows', True),
        (r'Save As dialog', True),
        (r'Close Project', True),
        (r'File menu', True),
        (r'file picker', True),
        (r'unsaved changes', True),
        (r'focus indicators', True),
        (r'readable labels', True),
        (r'Accessibility Scanner', True),
        (r'WCAG 2\.1 AA', True),
        (r'file not found', True),
        (r'access denied', True),
        (r'save failed', True),
        (r'Windows 11', True),
        (r'Android Tablet', True),
        (r'native OS', True),
        (r'Save As', True),
        (r'About App', True),
        (r'Help menu', True),
        (r'Tools Menu', True),
        # Single important words/phrases
        (r'\.qdraw', False),  # No word boundary for file extension
        (r'\bOpen…?\b', True),
        (r'\bSave\b', True),  # Word boundary to avoid matching "Save As" partially
        (r'\bVerify\b', True),
        (r'\bdisplays\b', True),
        (r'\blaunches\b', True),
        (r'\bcreates\b', True),
        (r'\bsaves\b', True),
        (r'\bcloses\b', True),
        (r'\bappears\b', True),
        (r'\bopens\b', True),
        (r'\bdialog\b', True),
        (r'\bwindow\b', True),
        (r'\bversion\b', True),
        (r'\bcopyright\b', True),
        (r'\bsupport link\b', True),
        (r'\bclickable\b', True),
        (r'\bclose\b', True),
        (r'\btab\b', True),
        (r'\bPDF\b', True),
        (r'\bPNG\b', True),
        (r'\bJPEG\b', True),
        (r'\biPad\b', True),
        (r'\bVoiceOver\b', True),
        (r'\bcorrupted\b', True),
        (r'\bkeyboard navigation\b', True),
        (r'\baccessibility\b', True),
    ]
    
    text = objective_text
    replacements = []
    
    for pattern, use_word_boundary in important_terms:
        flags = re.IGNORECASE
        for match in re.finditer(pattern, text, flags):
            start, end = match.span()
            word = match.group()
            # Check if this position is already marked for replacement
            overlap = False
            for (s, e, _) in replacements:
                if not (end <= s or start >= e):
                    overlap = True
                    break
            if not overlap:
                replacements.append((start, end, word))
    
    # Sort by position (reverse order to maintain indices)
    replacements.sort(key=lambda x: x[0], reverse=True)
    
    # Apply replacements
    for start, end, word in replacements:
        text = text[:start] + f'<b>{word}</b>' + text[end:]
    
    formatted += text
    return formatted


def infer_objectives_file_path(story_id: Optional[int] = None, csv_file: Optional[str] = None) -> Optional[str]:
    """Infer objectives file path from story_id or csv_file."""
    if story_id:
        # Try common locations
        possible_paths = [
            f"output/{story_id}_Test_Objectives.txt",
            f"{story_id}_Test_Objectives.txt",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
    
    if csv_file:
        # Replace Test_Cases.csv with Test_Objectives.txt
        objectives_file = csv_file.replace('_Test_Cases.csv', '_Test_Objectives.txt')
        if os.path.exists(objectives_file):
            return objectives_file
        
        # Try in same directory
        csv_dir = os.path.dirname(csv_file) if os.path.dirname(csv_file) else '.'
        csv_basename = os.path.basename(csv_file)
        if '_Test_Cases.csv' in csv_basename:
            story_part = csv_basename.replace('_Test_Cases.csv', '')
            objectives_file = os.path.join(csv_dir, f"{story_part}_Test_Objectives.txt")
            if os.path.exists(objectives_file):
                return objectives_file
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Update Summary field (System.Description) for test cases in ADO',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_summary_generic.py 272981
  python update_summary_generic.py --csv output/272981_Test_Cases.csv
  python update_summary_generic.py --csv output/272981_Test_Cases.csv --objectives output/272981_Test_Objectives.txt
        """
    )
    
    parser.add_argument('story_id', nargs='?', type=int, help='User story ID (if not using --csv)')
    parser.add_argument('--csv', type=str, help='Path to CSV file containing test cases')
    parser.add_argument('--objectives', type=str, help='Path to objectives file (auto-detected if not provided)')
    
    args = parser.parse_args()
    
    if not config.ADO_PAT:
        print("ERROR: ADO_PAT environment variable is required")
        sys.exit(1)
    
    # Determine input method
    if args.csv:
        csv_file = args.csv
        story_id = None
        print("=" * 80)
        print("UPDATING SUMMARY FIELD FROM CSV FILE")
        print("=" * 80)
        print(f"CSV file: {csv_file}")
    elif args.story_id:
        story_id = args.story_id
        csv_file = None
        print("=" * 80)
        print("UPDATING SUMMARY FIELD FOR USER STORY")
        print("=" * 80)
        print(f"Story ID: {story_id}")
    else:
        parser.print_help()
        sys.exit(1)
    
    # Determine objectives file
    objectives_file = args.objectives
    if not objectives_file:
        objectives_file = infer_objectives_file_path(story_id, csv_file)
    
    if not objectives_file:
        print("\nERROR: Could not find objectives file.")
        print("Please specify it with --objectives option.")
        sys.exit(1)
    
    print(f"Objectives file: {objectives_file}")
    print("=" * 80)
    
    # Parse objectives
    print(f"\n1. Reading objectives file...")
    objectives = parse_objectives_file(objectives_file)
    print(f"   Found {len(objectives)} objectives")
    
    if not objectives:
        print("   Error: No objectives found. Exiting.")
        sys.exit(1)
    
    # Initialize ADO client
    client = ADOClient()
    
    # Get test cases
    test_cases_from_ado = []
    
    if story_id:
        # Retrieve test cases from ADO using story ID
        print(f"\n2. Retrieving test cases from ADO for story {story_id}...")
        result = client.verify_test_cases_exist(story_id)
        
        if result['total_found'] == 0:
            print("   Error: No test cases found in ADO. Exiting.")
            sys.exit(1)
        
        print(f"   Found {result['total_found']} test case(s)")
        test_cases_from_ado = result['test_cases']
        
    elif csv_file:
        # Parse CSV and verify test cases exist in ADO
        print(f"\n2. Parsing CSV file...")
        csv_test_cases = parse_csv_file(csv_file)
        print(f"   Found {len(csv_test_cases)} test case(s) in CSV")
        
        if not csv_test_cases:
            print("   Error: No test cases found in CSV. Exiting.")
            sys.exit(1)
        
        # Verify and retrieve test cases from ADO
        print(f"\n3. Verifying test cases exist in ADO...")
        test_cases_from_ado = []
        
        for csv_tc in csv_test_cases:
            title = csv_tc['title']
            work_item_id = csv_tc.get('id')
            
            # If we have work item ID from CSV, use it directly
            if work_item_id and work_item_id.isdigit():
                # Verify it exists
                try:
                    import requests
                    url = f"{client.base_url}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
                    response = requests.get(url, headers=client.headers)
                    if response.status_code == 200:
                        data = response.json()
                        fields = data.get('fields', {})
                        if fields.get('System.WorkItemType') == 'Test Case':
                            test_cases_from_ado.append({
                                'id': int(work_item_id),
                                'title': fields.get('System.Title', title),
                                'state': fields.get('System.State', 'N/A'),
                                'work_item_type': 'Test Case'
                            })
                            continue
                except:
                    pass
            
            # Otherwise, find by title
            found_id = find_test_case_by_title(client, title)
            if found_id:
                test_cases_from_ado.append({
                    'id': found_id,
                    'title': title,
                    'state': 'N/A',
                    'work_item_type': 'Test Case'
                })
            else:
                print(f"   ⚠ Warning: Test case not found in ADO: {title[:60]}...")
        
        print(f"   Verified {len(test_cases_from_ado)} test case(s) in ADO")
        
        if not test_cases_from_ado:
            print("   Error: No test cases found in ADO. Exiting.")
            sys.exit(1)
    
    # Match test cases with objectives and update
    step_num = "3" if story_id else "4"
    print(f"\n{step_num}. Updating System.Description (Summary field)...")
    print("-" * 80)
    
    success_count = 0
    fail_count = 0
    not_found_count = 0
    
    for test_case in test_cases_from_ado:
        work_item_id = test_case['id']
        title = test_case['title']
        
        # Extract test case ID from title
        test_case_id = extract_test_case_id_from_title(title)
        
        if not test_case_id:
            print(f"   ✗ [{work_item_id}] Could not extract test case ID from title: {title[:50]}...")
            fail_count += 1
            continue
        
        # Find matching objective
        if test_case_id not in objectives:
            print(f"   ✗ [{work_item_id}] {test_case_id}: Objective not found")
            not_found_count += 1
            continue
        
        objective = objectives[test_case_id]
        
        # Format objective with bold "Objective:" and important words
        formatted_objective = format_objective_with_bold(objective)
        
        # Update System.Description using replace operation
        update_result = client.update_work_item_field(
            work_item_id,
            'System.Description',
            formatted_objective
        )
        
        if update_result:
            print(f"   ✓ [{work_item_id}] {test_case_id}: Updated")
            success_count += 1
        else:
            print(f"   ✗ [{work_item_id}] {test_case_id}: Failed to update")
            fail_count += 1
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if story_id:
        print(f"Story ID: {story_id}")
    else:
        print(f"CSV file: {csv_file}")
    print(f"Objectives file: {objectives_file}")
    print(f"Total test cases found: {len(test_cases_from_ado)}")
    print(f"Successfully updated: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Objective not found: {not_found_count}")
    print(f"\nField updated: System.Description")
    print("\nNote: System.Description is the field that displays in the Summary tab")
    print("      in ADO Test Plans. Please refresh your Test Plan view to see the updates.")
    print("=" * 80)


if __name__ == '__main__':
    main()
