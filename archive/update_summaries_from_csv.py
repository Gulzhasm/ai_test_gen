#!/usr/bin/env python3
"""
Script to update test case Summary fields in ADO with objectives from objectives file.
Uses the uploaded CSV file to get ADO work item IDs and titles.
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
    270471-AC1: Test Title
    Objective: Verify that...
    
    Returns:
        Dictionary mapping test ID (e.g., "270471-AC1") to objective text
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
        
        # Extract test ID from title (e.g., "270471-AC1" from "270471-AC1: Test Title")
        match = re.match(r'^(\d+-\w+):\s*(.+)', title_line)
        if match:
            test_id = match.group(1)  # e.g., "270471-AC1"
            full_title = title_line  # Keep full title for fallback matching
        
            # Second line: "Objective: Verify that..." or "Verify that..." or just the objective text
            objective_line = lines[1].strip() if len(lines) > 1 else ""
            if objective_line.startswith('Objective:'):
                objective = objective_line.replace('Objective:', '').strip()
            elif objective_line.startswith('Verify that'):
                objective = objective_line
            elif objective_line:
                objective = objective_line
            else:
                continue  # Skip if no objective found
            
            # Map by test ID (primary) and also by full title (fallback)
            objectives_map[test_id] = objective
            objectives_map[full_title] = objective
    
    return objectives_map


def parse_uploaded_csv(csv_file: str) -> Dict[str, str]:
    """Parse uploaded CSV file and extract ADO work item IDs and titles.
    
    Returns:
        Dictionary mapping ADO work item ID to test title
    """
    id_to_title = {}
    
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
                    id_to_title[work_item_id] = title
    
    return id_to_title


def update_test_summary(work_item_id: int, objective: str) -> bool:
    """Update a test case's Summary field (System.Description) in ADO.
    
    Args:
        work_item_id: ADO work item ID
        objective: Objective text to set as Summary
        
    Returns:
        True if successful, False otherwise
    """
    client = ADOClient()
    base_url = config.BASE_URL
    
    # Update work item using PATCH
    url = f"{base_url}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
    
    headers = client.headers.copy()
    headers['Content-Type'] = 'application/json-patch+json'
    
    # Try "replace" first (works if field exists or is empty)
    patch_doc_replace = [
        {
            "op": "replace",
            "path": "/fields/System.Description",
            "value": objective
        }
    ]
    
    try:
        response = requests.patch(url, json=patch_doc_replace, headers=headers)
        response.raise_for_status()
        # Verify the update actually worked by reading back the field
        if response.status_code == 200:
            # Read back the work item to verify the update
            verify_url = f"{base_url}/_apis/wit/workitems/{work_item_id}?$expand=all&api-version=7.1"
            verify_response = requests.get(verify_url, headers=client.headers)
            if verify_response.status_code == 200:
                work_item = verify_response.json()
                updated_value = work_item.get('fields', {}).get('System.Description', '')
                if updated_value.strip() == objective.strip():
                    return True
                else:
                    print(f"  Warning: Update reported success but field value doesn't match for {work_item_id}")
                    return False
            return True
        return False
    except requests.exceptions.HTTPError as e:
        # If replace fails, try "add" (for new fields)
        if e.response and e.response.status_code == 400:
            patch_doc_add = [
                {
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": objective
                }
            ]
            try:
                response = requests.patch(url, json=patch_doc_add, headers=headers)
                response.raise_for_status()
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                pass
        
        print(f"  Error updating {work_item_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  Error updating {work_item_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}")
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 update_summaries_from_csv.py <uploaded_csv> <objectives_file>")
        sys.exit(1)
    
    uploaded_csv = sys.argv[1]
    objectives_file = sys.argv[2]
    
    print(f"Reading uploaded CSV: {uploaded_csv}")
    id_to_title = parse_uploaded_csv(uploaded_csv)
    print(f"  Found {len(id_to_title)} test cases")
    
    print(f"\nReading objectives file: {objectives_file}")
    objectives_map = parse_objectives_file(objectives_file)
    print(f"  Found {len(objectives_map)} objectives")
    
    # Match IDs to objectives
    matched = 0
    updated = 0
    failed = 0
    not_found = 0
    
    print(f"\nUpdating test case summaries (only tests created by this tool)...")
    for work_item_id_str, title in id_to_title.items():
        work_item_id = int(work_item_id_str)
        
        # Extract test ID from title (e.g., "270471-AC1" from "270471-AC1: Test Title...")
        # Only process tests that match our test ID pattern (e.g., 270471-AC1, 270471-005)
        objective = None
        match = re.match(r'^(\d+-\w+):', title)
        if not match:
            # Skip tests that don't match our test ID pattern (not created by us)
            continue
        
        test_id = match.group(1)  # e.g., "270471-AC1"
        
        # Only update tests that match our test ID pattern (story ID prefix)
        # Extract story ID from objectives to ensure we only update our tests
        story_id_from_test = test_id.split('-')[0] if '-' in test_id else None
        if not story_id_from_test:
            continue
        
        # Try matching by test ID first (most reliable)
        objective = objectives_map.get(test_id)
        
        # Fallback: try matching by full title
        if not objective:
            objective = objectives_map.get(title)
        
        # Fallback: try partial title match
        if not objective:
            match = re.match(r'^\d+-\w+:\s*(.+)', title)
            if match:
                title_without_id = match.group(1).strip()
                # Try to find by title without ID (partial match)
                for full_title, obj in objectives_map.items():
                    if ':' in full_title and title_without_id in full_title:
                        objective = obj
                        break
        
        if objective:
            matched += 1
            print(f"  Updating {work_item_id} ({title[:60]}...): ", end='')
            if update_test_summary(work_item_id, objective):
                updated += 1
                print("✓")
            else:
                failed += 1
                print("✗")
        else:
            not_found += 1
            print(f"  No objective found for {work_item_id}: {title[:60]}...")
    
    print(f"\nSummary:")
    print(f"  Total test cases: {len(id_to_title)}")
    print(f"  Matched with objectives: {matched}")
    print(f"  Successfully updated: {updated}")
    print(f"  Failed to update: {failed}")
    print(f"  Objectives not found: {not_found}")


if __name__ == '__main__':
    main()
