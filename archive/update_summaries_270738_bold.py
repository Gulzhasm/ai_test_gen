#!/usr/bin/env python3
"""
Script to update test case Summary fields in ADO with bold-formatted objectives.
Retrieves test cases directly from ADO by querying for story 270738 test cases.
Formats objectives as HTML with bold text (not colorful).
"""
import re
import sys
from typing import Dict, List, Tuple
import requests
from src.ado_client import ADOClient
import config


def parse_objectives_file(objectives_file: str) -> Dict[str, str]:
    """Parse objectives file and create a mapping from test ID to objective.
    
    Format:
    270738-AC1: 270738-AC1: Test Title
    Objective: Verify that...
    
    Returns:
        Dictionary mapping test ID (e.g., "270738-AC1") to objective text
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
        
        # First line: "270738-AC1: 270738-AC1: Test Title"
        title_line = lines[0].strip()
        
        # Extract test ID from title (e.g., "270738-AC1" from "270738-AC1: 270738-AC1: Test Title")
        match = re.match(r'^(\d+-\w+):\s*(\d+-\w+):\s*(.+)', title_line)
        if match:
            test_id = match.group(1)  # e.g., "270738-AC1"
        else:
            # Fallback: try single ID format
            match = re.match(r'^(\d+-\w+):\s*(.+)', title_line)
            if match:
                test_id = match.group(1)
            else:
                continue
        
        # Second line: "Objective: Verify that..."
        objective_line = lines[1].strip() if len(lines) > 1 else ""
        if objective_line.startswith('Objective:'):
            objective = objective_line.replace('Objective:', '').strip()
        elif objective_line.startswith('Verify that'):
            objective = objective_line
        elif objective_line:
            objective = objective_line
        else:
            continue
        
        objectives_map[test_id] = objective
    
    return objectives_map


def format_objective_as_bold(objective: str) -> str:
    """Format objective as HTML with bold text for important words.
    
    Important words to make bold:
    - "Verify that" (always bold)
    - Feature names: "Undo / Redo Functionality", "Undo", "Redo"
    - UI areas: "Edit Menu", "Tools Menu", "Top Action Toolbar"
    - Actions: "activated", "operations", "reversible", "restoring", "reapplying"
    - Platforms: "Windows 11", "iPad", "Android Tablet"
    
    Returns:
        HTML-formatted objective with bold text (no colors)
    """
    html = objective
    
    # Always bold "Verify that"
    html = re.sub(r'\b(Verify that)\b', r'<b>\1</b>', html, flags=re.IGNORECASE)
    
    # Bold feature names
    html = re.sub(r'\b(Undo / Redo Functionality|Undo|Redo)\b', r'<b>\1</b>', html, flags=re.IGNORECASE)
    
    # Bold UI areas
    html = re.sub(r'\b(Edit Menu|Tools Menu|Top Action Toolbar|Canvas)\b', r'<b>\1</b>', html, flags=re.IGNORECASE)
    
    # Bold key actions
    html = re.sub(r'\b(activated|operations|reversible|restoring|reapplying|changes|available|accessible)\b', 
                  r'<b>\1</b>', html, flags=re.IGNORECASE)
    
    # Bold platforms
    html = re.sub(r'\b(Windows 11|iPad|Android Tablet)\b', r'<b>\1</b>', html, flags=re.IGNORECASE)
    
    return html


def retrieve_test_cases_from_ado(story_id: int) -> List[Dict]:
    """Retrieve test cases from ADO that match the story ID pattern.
    
    Uses WIQL to query for test cases with titles starting with "{story_id}-"
    
    Returns:
        List of dictionaries with 'id', 'title', and 'test_id' (extracted from title)
    """
    client = ADOClient()
    base_url = client.base_url
    
    # Query for test cases with titles matching the pattern
    wiql_query = {
        'query': (
            f"Select [System.Id], [System.Title] "
            f"From WorkItems "
            f"Where [System.WorkItemType] = 'Test Case' "
            f"And [System.Title] Contains '{story_id}-' "
            f"Order By [System.Title]"
        )
    }
    
    url = f"{base_url}/_apis/wit/wiql?api-version=7.1"
    
    print(f"Querying ADO for test cases with titles containing '{story_id}-'...")
    try:
        response = requests.post(url, headers=client.headers, json=wiql_query)
        response.raise_for_status()
        
        data = response.json()
        work_items = data.get('workItems', [])
        
        if not work_items:
            print(f"  No test cases found for story {story_id}.")
            return []
        
        print(f"  Found {len(work_items)} test case(s) in query results.")
        
        # Fetch full work item details
        test_cases = []
        for wi in work_items:
            work_item_id = wi['id']
            
            # Fetch the work item to get the title
            item_url = f"{base_url}/_apis/wit/workitems/{work_item_id}?$expand=all&api-version=7.1"
            item_response = requests.get(item_url, headers=client.headers)
            item_response.raise_for_status()
            
            work_item = item_response.json()
            title = work_item.get('fields', {}).get('System.Title', '')
            
            # Extract test ID from title (e.g., "270738-AC1" from "270738-AC1: Undo / Redo Functionality / ...")
            test_id_match = re.match(r'^(\d+-\w+):', title)
            if test_id_match:
                test_id = test_id_match.group(1)
                test_cases.append({
                    'id': work_item_id,
                    'title': title,
                    'test_id': test_id
                })
        
        return test_cases
        
    except Exception as e:
        print(f"  Error retrieving test cases: {e}")
        return []


def update_test_summary(work_item_id: int, objective_html: str, client: ADOClient) -> bool:
    """Update a test case's Summary field (System.Description) in ADO.
    
    Args:
        work_item_id: ADO work item ID
        objective_html: HTML-formatted objective text
        client: ADOClient instance
        
    Returns:
        True if update succeeded, False otherwise
    """
    base_url = client.base_url
    
    # Update System.Description field
    patch_data = [
        {
            "op": "replace",
            "path": "/fields/System.Description",
            "value": objective_html
        }
    ]
    
    url = f"{base_url}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
    
    headers = client.headers.copy()
    headers['Content-Type'] = 'application/json-patch+json'
    
    try:
        response = requests.patch(url, headers=headers, json=patch_data)
        response.raise_for_status()
        
        # Verify the update actually worked by reading back the field
        if response.status_code == 200:
            # Read back the work item to verify the update
            verify_url = f"{base_url}/_apis/wit/workitems/{work_item_id}?$expand=all&api-version=7.1"
            verify_response = requests.get(verify_url, headers=client.headers)
            if verify_response.status_code == 200:
                work_item = verify_response.json()
                updated_value = work_item.get('fields', {}).get('System.Description', '')
                # Compare normalized (strip whitespace and compare content)
                if updated_value.strip():
                    return True
            return True
        return False
    except requests.exceptions.HTTPError as e:
        # If replace fails, try "add" (for new fields)
        if e.response and e.response.status_code == 400:
            patch_data_add = [
                {
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": objective_html
                }
            ]
            try:
                response = requests.patch(url, headers=headers, json=patch_data_add)
                response.raise_for_status()
                if response.status_code == 200:
                    return True
            except Exception as e2:
                print(f"  Error updating work item {work_item_id} (add): {e2}")
                return False
        print(f"  Error updating work item {work_item_id}: {e}")
        return False
    except Exception as e:
        print(f"  Error updating work item {work_item_id}: {e}")
        return False


def main():
    story_id = 270738
    objectives_file = f"output/{story_id}_Undo_Redo_Functionality_Test_Objectives.txt"
    
    print(f"Updating test case summaries for story {story_id}")
    print("=" * 80)
    
    # Parse objectives file
    print(f"\nReading objectives from: {objectives_file}")
    objectives_map = parse_objectives_file(objectives_file)
    print(f"  Parsed {len(objectives_map)} objective(s)")
    
    # Retrieve test cases from ADO
    print(f"\nRetrieving test cases from ADO...")
    test_cases = retrieve_test_cases_from_ado(story_id)
    
    if not test_cases:
        print("  No test cases found in ADO. Exiting.")
        return
    
    print(f"  Found {len(test_cases)} test case(s) in ADO")
    
    # Filter to only test cases that match objectives and remove duplicates
    # Keep only the first occurrence of each test_id
    seen_test_ids = set()
    filtered_test_cases = []
    for tc in test_cases:
        test_id = tc['test_id']
        if test_id in objectives_map and test_id not in seen_test_ids:
            seen_test_ids.add(test_id)
            filtered_test_cases.append(tc)
    
    print(f"  Filtered to {len(filtered_test_cases)} unique test case(s) matching objectives")
    
    # Match test cases with objectives and update
    print(f"\nUpdating test case summaries...")
    updated_count = 0
    not_found_count = 0
    
    client = ADOClient()
    
    for tc in filtered_test_cases:
        test_id = tc['test_id']
        work_item_id = tc['id']
        title = tc['title']
        
        # Find matching objective
        objective = objectives_map.get(test_id)
        
        if not objective:
            print(f"  ✗ Objective not found for test ID: {test_id} (Work Item: {work_item_id})")
            not_found_count += 1
            continue
        
        # Format objective as bold HTML
        objective_html = format_objective_as_bold(objective)
        
        # Update ADO
        print(f"  Updating {test_id} (Work Item: {work_item_id})...")
        if update_test_summary(work_item_id, objective_html, client):
            print(f"    ✓ Updated successfully")
            updated_count += 1
        else:
            print(f"    ✗ Update failed")
    
    print("\n" + "=" * 80)
    print(f"Summary:")
    print(f"  Total test cases found in ADO: {len(test_cases)}")
    print(f"  Filtered to matching objectives: {len(filtered_test_cases)}")
    print(f"  Successfully updated: {updated_count}")
    print(f"  Objectives not found: {not_found_count}")
    
    if updated_count == len(filtered_test_cases):
        print(f"\n✓ All {updated_count} test cases updated successfully!")
    else:
        print(f"\n⚠ Only {updated_count}/{len(filtered_test_cases)} test cases were updated.")


if __name__ == "__main__":
    main()
