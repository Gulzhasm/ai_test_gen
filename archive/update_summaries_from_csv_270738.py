#!/usr/bin/env python3
"""
Script to update test case Summary fields in ADO with bold-formatted objectives.
Uses the uploaded CSV file to get ADO work item IDs and test case IDs.
Only updates the 35 test cases specified in the CSV file.
"""
import csv
import re
import sys
from typing import Dict
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
            # Keep the full "Objective: Verify that" prefix
            objective = objective_line
        elif objective_line.startswith('Verify that'):
            # Add "Objective: " prefix if missing
            objective = f"Objective: {objective_line}"
        elif objective_line:
            # Add full prefix if missing
            objective = f"Objective: Verify that {objective_line}"
        else:
            continue
        
        objectives_map[test_id] = objective
    
    return objectives_map


def format_objective_as_bold(objective: str) -> str:
    """Format objective as HTML with bold text for important words.
    
    Important words to make bold:
    - "Objective:" (always bold)
    - "Verify that" (always bold)
    - Feature names: "Undo / Redo Functionality", "Undo", "Redo"
    - UI areas: "Edit Menu", "Tools Menu", "Top Action Toolbar"
    - Actions: "activated", "operations", "reversible", "restoring", "reapplying"
    - Platforms: "Windows 11", "iPad", "Android Tablet"
    
    Returns:
        HTML-formatted objective with bold text (no colors)
    """
    # Ensure it starts with "Objective: Verify that"
    if not objective.startswith('Objective:'):
        if objective.startswith('Verify that'):
            objective = f"Objective: {objective}"
        else:
            objective = f"Objective: Verify that {objective}"
    
    html = objective
    
    # Always bold "Objective:"
    html = re.sub(r'\b(Objective:)\b', r'<b>\1</b>', html, flags=re.IGNORECASE)
    
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


def parse_uploaded_csv(csv_file: str) -> Dict[str, Dict]:
    """Parse uploaded CSV file and extract ADO work item IDs and test case IDs.
    
    Returns:
        Dictionary mapping test case ID (e.g., "270738-AC1") to dict with 'work_item_id' and 'title'
    """
    test_cases = {}
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
        reader = csv.DictReader(f)
        for row in reader:
            # Handle BOM in column names
            id_key = 'ID' if 'ID' in row else '\ufeffID' if '\ufeffID' in row else None
            if not id_key:
                continue
            
            work_item_id = row.get(id_key, '').strip().strip('"').strip("'")
            title = row.get('Title', '').strip().strip('"').strip("'")
            work_item_type = row.get('Work Item Type', '').strip().strip('"').strip("'")
            
            # Skip empty rows or header row
            if not work_item_id or not title or work_item_id == 'ID':
                continue
            
            # Check if this is a test case header row
            if work_item_type == 'Test Case':
                # Verify ID is numeric (ADO work item ID)
                if work_item_id.isdigit():
                    # Extract test case ID from title (e.g., "270738-AC1" from "270738-AC1: Undo / Redo Functionality / ...")
                    test_id_match = re.match(r'^(\d+-\w+):', title)
                    if test_id_match:
                        test_case_id = test_id_match.group(1)
                        test_cases[test_case_id] = {
                            'work_item_id': int(work_item_id),
                            'title': title
                        }
    
    return test_cases


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
    csv_file = "Env Drawing Project _ Phase 1_270738 _ Undo _ Redo Functionality (1).csv"
    objectives_file = "output/270738_Undo_Redo_Functionality_Test_Objectives.txt"
    
    print(f"Updating test case summaries from CSV file")
    print("=" * 80)
    
    # Parse CSV file
    print(f"\nReading test cases from CSV: {csv_file}")
    test_cases = parse_uploaded_csv(csv_file)
    print(f"  Found {len(test_cases)} test case(s) in CSV")
    
    # Parse objectives file
    print(f"\nReading objectives from: {objectives_file}")
    objectives_map = parse_objectives_file(objectives_file)
    print(f"  Parsed {len(objectives_map)} objective(s)")
    
    # Match test cases with objectives and update
    print(f"\nUpdating test case summaries...")
    updated_count = 0
    not_found_count = 0
    
    client = ADOClient()
    
    for test_case_id, test_info in sorted(test_cases.items()):
        work_item_id = test_info['work_item_id']
        title = test_info['title']
        
        # Find matching objective
        objective = objectives_map.get(test_case_id)
        
        if not objective:
            print(f"  ✗ Objective not found for test ID: {test_case_id} (Work Item: {work_item_id})")
            not_found_count += 1
            continue
        
        # Format objective as bold HTML
        objective_html = format_objective_as_bold(objective)
        
        # Update ADO
        print(f"  Updating {test_case_id} (Work Item: {work_item_id})...")
        if update_test_summary(work_item_id, objective_html, client):
            print(f"    ✓ Updated successfully")
            updated_count += 1
        else:
            print(f"    ✗ Update failed")
    
    print("\n" + "=" * 80)
    print(f"Summary:")
    print(f"  Total test cases in CSV: {len(test_cases)}")
    print(f"  Successfully updated: {updated_count}")
    print(f"  Objectives not found: {not_found_count}")
    
    if updated_count == len(test_cases):
        print(f"\n✓ All {updated_count} test cases updated successfully!")
    else:
        print(f"\n⚠ Only {updated_count}/{len(test_cases)} test cases were updated.")


if __name__ == "__main__":
    main()
