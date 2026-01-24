#!/usr/bin/env python3
"""
Script to update test case Summary fields in ADO with objectives from objectives file.
Retrieves tests from a test plan/suite and updates only the tests that match our generated test cases.
"""
import csv
import re
import sys
from typing import Dict, List, Optional
import requests
from src.ado_client import ADOClient
import config


def parse_objectives_file(objectives_file: str) -> Dict[str, str]:
    """Parse objectives file and create a mapping from test title to objective.
    
    Format:
    270471-AC1: Test Title
    Objective: Verify that...
    
    Returns:
        Dictionary mapping test title (without ID prefix) to objective text
    """
    objectives_map = {}
    
    with open(objectives_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by double newlines to get test blocks
    blocks = content.split('\n\n')
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        
        # First line: "270471-AC1: Test Title"
        title_line = lines[0].strip()
        # Extract title after the ID prefix (e.g., "270471-AC1: " or "270471-010: ")
        match = re.match(r'^\d+-\w+:\s*(.+)', title_line)
        if not match:
            continue
        
        test_title = match.group(1).strip()
        
        # Second line: "Objective: Verify that..."
        objective_line = lines[1].strip()
        if objective_line.startswith('Objective:'):
            objective = objective_line.replace('Objective:', '').strip()
            objectives_map[test_title] = objective
    
    return objectives_map


def parse_csv_titles(csv_file: str) -> List[str]:
    """Parse CSV file and extract test case titles (without ID prefix).
    
    Returns:
        List of test titles (without ID prefix like "270471-AC1: ")
    """
    titles = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get('Title', '').strip()
            if not title or title == 'Title':
                continue
            
            # Remove ID prefix if present (e.g., "270471-AC1: " or "270471-010: ")
            match = re.match(r'^\d+-\w+:\s*(.+)', title)
            if match:
                title = match.group(1).strip()
            
            if title and title not in titles:
                titles.append(title)
    
    return titles


def get_tests_from_suite(plan_id: int, suite_id: int) -> List[Dict]:
    """Retrieve all test cases from a test suite using ADO Test Plans API.
    
    Args:
        plan_id: Test plan ID
        suite_id: Test suite ID
        
    Returns:
        List of test case dictionaries with id, title, workItemId, etc.
    """
    client = ADOClient()
    base_url = config.BASE_URL
    
    # Try different API endpoints to get test cases from suite
    # First, try getting test cases directly from the suite
    url = f"{base_url}/_apis/test/plans/{plan_id}/suites/{suite_id}/testcases?api-version=7.1-preview.3"
    
    print(f"Retrieving tests from plan {plan_id}, suite {suite_id}...")
    try:
        response = requests.get(url, headers=client.headers)
        response.raise_for_status()
        
        data = response.json()
        test_cases_data = data.get('value', [])
        
        print(f"  Found {len(test_cases_data)} test case(s) in suite")
        
        # Extract work item IDs - try different possible structures
        work_item_ids = []
        if test_cases_data and len(test_cases_data) > 0:
            # Debug: print first item structure
            print(f"  Sample test case structure keys: {list(test_cases_data[0].keys())}")
        
        for tc in test_cases_data:
            # Try different possible paths for work item ID
            work_item_id = None
            if 'workItem' in tc:
                work_item_id = tc['workItem'].get('id')
            elif 'testCase' in tc:
                if isinstance(tc['testCase'], dict):
                    if 'workItem' in tc['testCase']:
                        work_item_id = tc['testCase']['workItem'].get('id')
                    elif 'id' in tc['testCase']:
                        work_item_id = tc['testCase'].get('id')
            elif 'id' in tc:
                # Maybe the ID is directly in the test case
                work_item_id = tc.get('id')
            
            if work_item_id:
                work_item_ids.append(work_item_id)
        
        if not work_item_ids:
            print("  No work items found in test suite")
            return []
        
        # Batch fetch work items to get titles
        batch_size = 200
        test_cases = []
        
        for i in range(0, len(work_item_ids), batch_size):
            batch_ids = work_item_ids[i:i + batch_size]
            ids_str = ','.join(map(str, batch_ids))
            
            url = f"{base_url}/_apis/wit/workitems?ids={ids_str}&api-version=7.1"
            response = requests.get(url, headers=client.headers)
            response.raise_for_status()
            
            batch_data = response.json()
            for work_item in batch_data.get('value', []):
                fields = work_item.get('fields', {})
                test_case = {
                    'id': work_item.get('id'),
                    'title': fields.get('System.Title', 'N/A'),
                    'state': fields.get('System.State', 'N/A'),
                    'summary': fields.get('System.Description', '')  # Current summary
                }
                test_cases.append(test_case)
        
        print(f"  Retrieved {len(test_cases)} test case(s)")
        return test_cases
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Try alternative: get test points
            print(f"  Test cases endpoint not found, trying test points endpoint...")
            url = f"{base_url}/_apis/test/plans/{plan_id}/suites/{suite_id}/testpoints?api-version=7.1-preview.2"
            response = requests.get(url, headers=client.headers)
            response.raise_for_status()
            
            data = response.json()
            test_points = data.get('value', [])
            
            print(f"  Found {len(test_points)} test point(s)")
            
            # Extract work item IDs
            work_item_ids = []
            for tp in test_points:
                work_item_id = tp.get('workItem', {}).get('id')
                if work_item_id:
                    work_item_ids.append(work_item_id)
            
            if not work_item_ids:
                print("  No work items found in test suite")
                return []
            
            # Batch fetch work items to get titles
            batch_size = 200
            test_cases = []
            
            for i in range(0, len(work_item_ids), batch_size):
                batch_ids = work_item_ids[i:i + batch_size]
                ids_str = ','.join(map(str, batch_ids))
                
                url = f"{base_url}/_apis/wit/workitems?ids={ids_str}&api-version=7.1"
                response = requests.get(url, headers=client.headers)
                response.raise_for_status()
                
                batch_data = response.json()
                for work_item in batch_data.get('value', []):
                    fields = work_item.get('fields', {})
                    test_case = {
                        'id': work_item.get('id'),
                        'title': fields.get('System.Title', 'N/A'),
                        'state': fields.get('System.State', 'N/A'),
                        'summary': fields.get('System.Description', '')  # Current summary
                    }
                    test_cases.append(test_case)
            
            print(f"  Retrieved {len(test_cases)} test case(s)")
            return test_cases
        else:
            raise


def match_test_title(test_title: str, our_titles: List[str]) -> Optional[str]:
    """Match a test title from ADO with our generated test titles.
    
    Handles cases where ADO title might have ID prefix or slight variations.
    
    Args:
        test_title: Test title from ADO
        our_titles: List of our generated test titles (without ID prefix)
        
    Returns:
        Matching title from our_titles if found, None otherwise
    """
    # Remove ID prefix if present
    match = re.match(r'^\d+-\w+:\s*(.+)', test_title)
    if match:
        test_title = match.group(1).strip()
    
    # Exact match
    if test_title in our_titles:
        return test_title
    
    # Try matching without extra whitespace
    test_title_normalized = ' '.join(test_title.split())
    for our_title in our_titles:
        our_title_normalized = ' '.join(our_title.split())
        if test_title_normalized == our_title_normalized:
            return our_title
    
    return None


def update_test_summaries(plan_id: int, suite_id: int, csv_file: str, objectives_file: str):
    """Main function to update test summaries.
    
    Args:
        plan_id: Test plan ID
        suite_id: Test suite ID
        csv_file: Path to CSV file with generated test cases
        objectives_file: Path to objectives TXT file
    """
    print("=" * 80)
    print("Updating Test Case Summaries with Objectives")
    print("=" * 80)
    
    # Parse objectives file
    print("\n1. Parsing objectives file...")
    objectives_map = parse_objectives_file(objectives_file)
    print(f"   Found {len(objectives_map)} objective(s)")
    
    # Parse CSV to get our test titles
    print("\n2. Parsing CSV file...")
    our_titles = parse_csv_titles(csv_file)
    print(f"   Found {len(our_titles)} test case title(s)")
    
    # Get tests from ADO test suite
    print("\n3. Retrieving tests from ADO test suite...")
    ado_tests = get_tests_from_suite(plan_id, suite_id)
    
    if not ado_tests:
        print("   No tests found in test suite. Exiting.")
        return
    
    # Match tests and update summaries
    print("\n4. Matching tests and updating summaries...")
    client = ADOClient()
    
    updated_count = 0
    skipped_count = 0
    not_found_count = 0
    
    for ado_test in ado_tests:
        test_id = ado_test['id']
        ado_title = ado_test['title']
        
        # Match with our titles
        matched_title = match_test_title(ado_title, our_titles)
        
        if not matched_title:
            print(f"   ⚠ Skipping test {test_id}: '{ado_title}' (not in our generated tests)")
            not_found_count += 1
            continue
        
        # Get objective for this test
        objective = objectives_map.get(matched_title)
        
        if not objective:
            print(f"   ⚠ Skipping test {test_id}: '{matched_title}' (no objective found)")
            skipped_count += 1
            continue
        
        # Check if summary already matches
        current_summary = ado_test.get('summary', '').strip()
        if current_summary == objective:
            print(f"   ✓ Test {test_id}: '{matched_title}' (already up to date)")
            continue
        
        # Update summary field
        print(f"   → Updating test {test_id}: '{matched_title}'")
        result = client.update_work_item_field(
            work_item_id=test_id,
            field_name='System.Description',
            field_value=objective
        )
        
        if result:
            print(f"     ✓ Successfully updated summary")
            updated_count += 1
        else:
            print(f"     ✗ Failed to update summary")
            skipped_count += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total tests in suite: {len(ado_tests)}")
    print(f"Tests updated: {updated_count}")
    print(f"Tests skipped (no match/no objective): {skipped_count + not_found_count}")
    print(f"Tests not found in our generated tests: {not_found_count}")
    print("=" * 80)


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("Usage: python3 update_test_summaries.py <plan_id> <suite_id> <csv_file> <objectives_file>")
        print("\nExample:")
        print("  python3 update_test_summaries.py 271600 271614 output/270471_Move___Rotate_Tool_Comprehensive_Test_Cases.csv output/270471_Move___Rotate_Tool_Comprehensive_Test_Objectives.txt")
        sys.exit(1)
    
    plan_id = int(sys.argv[1])
    suite_id = int(sys.argv[2])
    csv_file = sys.argv[3]
    objectives_file = sys.argv[4]
    
    update_test_summaries(plan_id, suite_id, csv_file, objectives_file)
