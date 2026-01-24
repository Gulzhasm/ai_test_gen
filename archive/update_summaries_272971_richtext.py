#!/usr/bin/env python3
"""
Script to update test case Summary fields in ADO with rich text formatted objectives.
Uses the uploaded CSV file to get ADO work item IDs and titles.
Formats objectives as HTML with highlights for important test words.
"""
import csv
import re
import sys
from typing import Dict
import requests
from src.ado_client import ADOClient
import config


def format_objective_as_richtext(objective: str) -> str:
    """Format objective as rich text HTML with highlights for important test words.
    
    Important words to highlight:
    - "Verify", "Verify that"
    - Feature names: "Help: Contact Support", "Contact Support", "Help"
    - UI areas: "Tools Menu", "Help Menu"
    - Actions: "activated", "opens", "displays", "appears"
    - Platforms: "Windows 11", "iPad", "Android Tablet", "Tablets"
    - Accessibility terms: "keyboard", "focus", "VoiceOver", "Touch"
    
    Args:
        objective: Plain text objective starting with "Objective: Verify that..."
        
    Returns:
        HTML formatted string with highlights
    """
    # Remove "Objective:" prefix if present, we'll add it back formatted
    text = objective.replace('Objective:', '').strip()
    if text.startswith('Verify that'):
        text = text.replace('Verify that', 'Verify that', 1)
    
    # Important words/phrases to highlight (in order of specificity - longest first)
    highlight_patterns = [
        ('Help: Contact Support', '<strong style="color: #0078d4;">Help: Contact Support</strong>'),
        ('Contact Support', '<strong style="color: #0078d4;">Contact Support</strong>'),
        ('Tools Menu', '<strong style="color: #d83b01;">Tools Menu</strong>'),
        ('Help Menu', '<strong style="color: #d83b01;">Help Menu</strong>'),
        ('Windows 11', '<strong style="color: #107c10;">Windows 11</strong>'),
        ('Android Tablet', '<strong style="color: #107c10;">Android Tablet</strong>'),
        ('iPad', '<strong style="color: #107c10;">iPad</strong>'),
        ('Tablets', '<strong style="color: #107c10;">Tablets</strong>'),
        ('tablet (iPad or Android Tablet)', '<strong style="color: #107c10;">tablet (iPad or Android Tablet)</strong>'),
        ('VoiceOver', '<strong style="color: #8764b8;">VoiceOver</strong>'),
        ('keyboard navigation', '<strong style="color: #8764b8;">keyboard navigation</strong>'),
        ('keyboard-only', '<strong style="color: #8764b8;">keyboard-only</strong>'),
        ('keyboard access', '<strong style="color: #8764b8;">keyboard access</strong>'),
        ('Touch Access', '<strong style="color: #8764b8;">Touch Access</strong>'),
        ('focus indicators', '<strong style="color: #8764b8;">focus indicators</strong>'),
        ('visible focus', '<strong style="color: #8764b8;">visible focus</strong>'),
        ('logical tab order', '<strong style="color: #8764b8;">logical tab order</strong>'),
        ('Verify that', '<strong style="color: #007acc; font-weight: bold;">Verify that</strong>'),
        ('activated', '<em style="color: #0078d4;">activated</em>'),
        ('opens', '<em style="color: #0078d4;">opens</em>'),
        ('displays', '<em style="color: #0078d4;">displays</em>'),
        ('appears', '<em style="color: #0078d4;">appears</em>'),
        ('available', '<em style="color: #0078d4;">available</em>'),
        ('selectable', '<em style="color: #0078d4;">selectable</em>'),
    ]
    
    # Apply highlights (case-insensitive but preserve original case)
    html_text = text
    for pattern, replacement in highlight_patterns:
        # Use case-insensitive replacement while preserving original case
        pattern_re = re.compile(re.escape(pattern), re.IGNORECASE)
        html_text = pattern_re.sub(replacement, html_text)
    
    # Wrap in paragraph tag and add "Objective:" prefix
    html_content = f'<p><strong>Objective:</strong> {html_text}</p>'
    
    return html_content


def parse_objectives_file(objectives_file: str) -> Dict[str, str]:
    """Parse objectives file and create a mapping from test ID to objective.
    
    Format:
    272971-AC1: 272971-AC1: Test Title
    Objective: Verify that...
    
    Returns:
        Dictionary mapping test ID (e.g., "272971-AC1") to objective text
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
        
        # First line: "272971-AC1: 272971-AC1: Test Title" or "272971-AC1: Test Title"
        title_line = lines[0].strip()
        
        # Extract test ID from title (e.g., "272971-AC1" from "272971-AC1: 272971-AC1: Test Title")
        # Handle both formats: "ID: ID: Title" and "ID: Title"
        match = re.match(r'^(\d+-\w+):\s*(?:\d+-\w+:\s*)?(.+)', title_line)
        if match:
            test_id = match.group(1)  # e.g., "272971-AC1"
            full_title = title_line  # Keep full title for fallback matching
        
            # Second line: "Objective: Verify that..." or "Verify that..." or just the objective text
            objective_line = lines[1].strip() if len(lines) > 1 else ""
            if objective_line.startswith('Objective:'):
                objective = objective_line  # Keep "Objective:" prefix
            elif objective_line.startswith('Verify that'):
                objective = f"Objective: {objective_line}"
            elif objective_line:
                objective = f"Objective: {objective_line}"
            else:
                continue  # Skip if no objective found
            
            # Map by test ID (primary) and also by full title (fallback)
            objectives_map[test_id] = objective
            objectives_map[full_title] = objective
    
    return objectives_map


def parse_uploaded_csv(csv_file: str) -> Dict[str, Dict[str, str]]:
    """Parse uploaded CSV file and extract ADO work item IDs, titles, and test IDs.
    
    Returns:
        Dictionary mapping ADO work item ID to dict with 'title' and 'test_id'
    """
    id_to_info = {}
    
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
                    # Extract test ID from title (e.g., "272971-AC1" from "272971-AC1: Help: Contact Support...")
                    test_id_match = re.match(r'^(\d+-\w+):', title)
                    test_id = test_id_match.group(1) if test_id_match else None
                    
                    id_to_info[work_item_id] = {
                        'title': title,
                        'test_id': test_id
                    }
    
    return id_to_info


def update_test_summary(work_item_id: int, objective_html: str) -> bool:
    """Update a test case's Summary field (System.Description) in ADO with HTML content.
    
    Args:
        work_item_id: ADO work item ID
        objective_html: HTML formatted objective to set as Summary
        
    Returns:
        True if successful, False otherwise
    """
    client = ADOClient()
    base_url = config.BASE_URL
    
    # Update work item using PATCH
    url = f"{base_url}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
    
    headers = client.headers.copy()
    headers['Content-Type'] = 'application/json-patch+json'
    
    # Use "replace" operation for System.Description
    patch_doc = [
        {
            "op": "replace",
            "path": "/fields/System.Description",
            "value": objective_html
        }
    ]
    
    try:
        response = requests.patch(url, json=patch_doc, headers=headers)
        response.raise_for_status()
        
        # Verify the update actually worked by reading back the field
        if response.status_code == 200:
            # Read back the work item to verify the update
            verify_url = f"{base_url}/_apis/wit/workitems/{work_item_id}?$expand=all&api-version=7.1"
            verify_response = requests.get(verify_url, headers=client.headers)
            if verify_response.status_code == 200:
                work_item = verify_response.json()
                updated_value = work_item.get('fields', {}).get('System.Description', '')
                # ADO may normalize HTML, so check if content is present (not empty)
                # Remove HTML tags for comparison to check if content is there
                import re
                content_only_sent = re.sub(r'<[^>]+>', '', objective_html).strip()
                content_only_received = re.sub(r'<[^>]+>', '', updated_value).strip()
                
                if content_only_received and len(content_only_received) > 10:
                    # Content was updated (may have different HTML formatting)
                    return True
                else:
                    print(f"  Warning: Update reported success but field appears empty for {work_item_id}")
                    return False
            return True
        return False
    except requests.exceptions.HTTPError as e:
        print(f"  Error updating {work_item_id}: {e}")
        if e.response:
            print(f"  Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"  Unexpected error updating {work_item_id}: {e}")
        return False


def main():
    csv_file = "output/Env Drawing Project _ Phase 1_272971 _ Help_ Contact Support.csv"
    objectives_file = "output/272971_Help_Contact_Support_Test_Objectives.txt"
    
    print(f"Reading CSV file: {csv_file}")
    id_to_info = parse_uploaded_csv(csv_file)
    print(f"Found {len(id_to_info)} test cases in CSV")
    
    print(f"\nReading objectives file: {objectives_file}")
    objectives_map = parse_objectives_file(objectives_file)
    print(f"Found {len(objectives_map)} objectives")
    
    print("\nMatching objectives to test cases...")
    matched = 0
    not_found = []
    
    for work_item_id, info in id_to_info.items():
        test_id = info['test_id']
        title = info['title']
        
        # Try to find objective by test ID first, then by full title
        objective = None
        if test_id and test_id in objectives_map:
            objective = objectives_map[test_id]
        elif title in objectives_map:
            objective = objectives_map[title]
        
        if objective:
            # Format as rich text HTML
            objective_html = format_objective_as_richtext(objective)
            
            # Update ADO
            print(f"\nUpdating {work_item_id} ({test_id})...")
            print(f"  Title: {title[:60]}...")
            print(f"  Objective: {objective[:80]}...")
            
            success = update_test_summary(int(work_item_id), objective_html)
            if success:
                matched += 1
                print(f"  ✓ Updated successfully")
            else:
                print(f"  ✗ Failed to update")
                not_found.append((work_item_id, test_id, title))
        else:
            print(f"\n✗ Objective not found for {work_item_id} ({test_id})")
            print(f"  Title: {title}")
            not_found.append((work_item_id, test_id, title))
    
    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"  Total test cases in CSV: {len(id_to_info)}")
    print(f"  Successfully updated: {matched}")
    print(f"  Not found/Failed: {len(not_found)}")
    
    if not_found:
        print(f"\nTest cases not updated:")
        for work_item_id, test_id, title in not_found:
            print(f"  - {work_item_id} ({test_id}): {title[:60]}...")


if __name__ == "__main__":
    main()
