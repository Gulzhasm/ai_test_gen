#!/usr/bin/env python3
"""
Fix comprehensive test cases CSV for story 270471 to comply with strict ADO rules:
1. Fix ID sequencing (AC1, 005, 010, 015...)
2. Remove forbidden "or" and "e.g." from expected results
3. Remove expected results from PRE-REQ, Launch, Draw, Select, Close steps
4. Fix Assigned To format (email only)
5. Ensure titles have full ID prefix
"""
import csv
import re
from typing import List, Dict

STORY_ID = 270471
INPUT_CSV = "output/270471_Move___Rotate_Tool_Comprehensive_Test_Cases.csv"
OUTPUT_CSV = "output/270471_Move___Rotate_Tool_Comprehensive_Test_Cases.csv"
OUTPUT_OBJECTIVES = "output/270471_Move___Rotate_Tool_Comprehensive_Test_Objectives.txt"

# Steps that should NOT have expected results
NO_EXPECTED_PATTERNS = [
    r'^PRE-REQ:',
    r'^Launch',
    r'^Draw a shape',
    r'^Draw multiple',
    r'^Select the shape',
    r'^Select another',
    r'^Close/Exit',
    r'^Activate Move – Rotate tool without',
    r'^Switch to another',
    r'^Perform first rotation',
    r'^Perform second rotation',
    r'^Perform third rotation',
    r'^Perform multiple (Undo|Redo|rotations)',
]


def should_have_expected(action: str) -> bool:
    """Check if step should have expected result."""
    if not action:
        return False
    
    action_upper = action.strip().upper()
    
    # Check against patterns
    for pattern in NO_EXPECTED_PATTERNS:
        if re.match(pattern, action_upper, re.IGNORECASE):
            return False
    
    # Steps starting with "Verify" should have expected
    if action_upper.startswith('VERIFY'):
        return True
    
    # All other steps should have expected (unless matched above)
    return True


def clean_expected(expected: str) -> str:
    """Remove forbidden words and examples from expected result."""
    if not expected:
        return ""
    
    # Remove "or" phrases
    expected = re.sub(r'\s+or\s+[^,\.]+', '', expected, flags=re.IGNORECASE)
    expected = re.sub(r'\s+or\s+errors', '', expected, flags=re.IGNORECASE)
    expected = re.sub(r'\s+or\s+menu item', '', expected, flags=re.IGNORECASE)
    
    # Remove "e.g." examples
    expected = re.sub(r'\s*\(e\.g\.[^\)]+\)', '', expected)
    expected = re.sub(r'\s*e\.g\.[^,\.]+', '', expected)
    
    # Remove "without cumulative drift or errors" -> "without cumulative drift"
    expected = re.sub(r'without cumulative drift or errors', 'without cumulative drift', expected, flags=re.IGNORECASE)
    
    # Remove "role (e.g., button or menu item)" -> "role is exposed as a button"
    expected = re.sub(r'role \(e\.g\., button or menu item\)', 'role is exposed as a button', expected, flags=re.IGNORECASE)
    expected = re.sub(r'correct control role \(e\.g\., button\.', 'control role is exposed as a button.', expected, flags=re.IGNORECASE)
    expected = re.sub(r'correct control role is exposed as a button', 'control role is exposed as a button', expected, flags=re.IGNORECASE)
    # Fix "has control role is exposed" -> "control role is exposed"
    expected = re.sub(r'has control role is exposed', 'control role is exposed', expected, flags=re.IGNORECASE)
    expected = re.sub(r'role \(e\.g\., [^\)]+\)', 'role is correctly exposed', expected, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    expected = ' '.join(expected.split())
    
    return expected.strip()


def clean_action(action: str, title: str) -> str:
    """Clean action text, removing out-of-scope content and fixing tablet keyboard issues."""
    if not action:
        return ""
    
    # Remove mentions of hotkeys/tooltips (out of scope)
    action = re.sub(r'\s*\([^)]*hotkey[^)]*\)', '', action, flags=re.IGNORECASE)
    action = re.sub(r'\s*\([^)]*tooltip[^)]*\)', '', action, flags=re.IGNORECASE)
    action = re.sub(r'\s*out of scope[^\.]*', '', action, flags=re.IGNORECASE)
    
    # Fix iPad keyboard navigation -> touch + VoiceOver
    if 'iPad' in title:
        action = re.sub(r'using keyboard navigation', 'using VoiceOver swipe gestures', action, flags=re.IGNORECASE)
        action = re.sub(r'keyboard access', 'touch access with VoiceOver', action, flags=re.IGNORECASE)
        action = re.sub(r'keyboard only', 'touch with VoiceOver', action, flags=re.IGNORECASE)
        action = re.sub(r'Open Tools Menu using keyboard navigation', 'Open Tools Menu using touch', action, flags=re.IGNORECASE)
        action = re.sub(r'Navigate to Move – Rotate option using keyboard navigation', 'Navigate to Move – Rotate option using VoiceOver swipe gestures', action, flags=re.IGNORECASE)
        action = re.sub(r'Activate Move – Rotate tool using keyboard navigation', 'Activate Move – Rotate tool using touch', action, flags=re.IGNORECASE)
    
    # Fix Android Tablet keyboard navigation -> touch + accessibility scanner
    if 'Android Tablet' in title:
        action = re.sub(r'using keyboard navigation', 'using touch', action, flags=re.IGNORECASE)
        action = re.sub(r'keyboard access', 'touch access', action, flags=re.IGNORECASE)
        action = re.sub(r'keyboard only', 'touch', action, flags=re.IGNORECASE)
        action = re.sub(r'Open Tools Menu using keyboard navigation', 'Open Tools Menu using touch', action, flags=re.IGNORECASE)
        action = re.sub(r'Navigate to Move – Rotate option using keyboard navigation', 'Navigate to Move – Rotate option using touch', action, flags=re.IGNORECASE)
        action = re.sub(r'Activate Move – Rotate tool using keyboard navigation', 'Activate Move – Rotate tool using touch', action, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    action = ' '.join(action.split())
    
    return action.strip()


def clean_expected_for_tablet(expected: str, title: str) -> str:
    """Clean expected results for tablet tests, removing keyboard references."""
    if not expected:
        return ""
    
    # Fix iPad expected results
    if 'iPad' in title:
        expected = re.sub(r'using keyboard navigation', 'using VoiceOver swipe gestures', expected, flags=re.IGNORECASE)
        expected = re.sub(r'keyboard only', 'touch with VoiceOver', expected, flags=re.IGNORECASE)
        expected = re.sub(r'can be accessed and activated using keyboard only', 'can be accessed and activated using touch with VoiceOver', expected, flags=re.IGNORECASE)
    
    # Fix Android Tablet expected results
    if 'Android Tablet' in title:
        expected = re.sub(r'using keyboard navigation', 'using touch', expected, flags=re.IGNORECASE)
        expected = re.sub(r'keyboard only', 'touch', expected, flags=re.IGNORECASE)
        expected = re.sub(r'can be accessed and activated using keyboard only', 'can be accessed and activated using touch', expected, flags=re.IGNORECASE)
    
    return expected.strip()


def clean_title(title: str) -> str:
    """Clean test title, fixing tablet keyboard references."""
    # Fix iPad title
    title = re.sub(r'Keyboard access to tool \(iPad\)', 'Touch access with VoiceOver (iPad)', title, flags=re.IGNORECASE)
    
    # Fix Android Tablet title
    title = re.sub(r'Keyboard access to tool \(Android Tablet\)', 'Touch access (Android Tablet)', title, flags=re.IGNORECASE)
    
    return title


def get_next_test_id(index: int) -> str:
    """Generate test ID: AC1 first, then 005, 010, 015..."""
    if index == 0:
        return f"{STORY_ID}-AC1"
    else:
        # 005, 010, 015, 020, etc.
        num = (index * 5)
        return f"{STORY_ID}-{num:03d}"


def fix_csv():
    """Fix the comprehensive CSV file."""
    # Read CSV
    test_cases = []
    current_test = None
    
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get('Title', '').strip()
            step_action = row.get('Step Action', '').strip()
            step_expected = row.get('Step Expected', '').strip()
            
            # Check if this is a test case header row
            if title and row.get('Work Item Type', '').strip() == 'Test Case':
                # Save previous test case if exists
                if current_test:
                    test_cases.append(current_test)
                
                # Extract current ID from title
                match = re.match(r'(\d+)-(\w+):\s*(.+)', title)
                if match:
                    old_id_part = match.group(2)
                    title_part = match.group(3)
                else:
                    old_id_part = None
                    title_part = title
                
                # Start new test case
                current_test = {
                    'old_id': old_id_part,
                    'title_part': title_part,
                    'steps': [],
                    'area_path': row.get('Area Path', '').strip(),
                    'assigned_to': row.get('Assigned To', '').strip(),
                    'state': row.get('State', '').strip()
                }
            elif current_test and step_action:
                # This is a step row
                step_num = row.get('Test Step', '').strip()
                if step_num:
                    # Clean action (remove out-of-scope content, fix tablet keyboard issues)
                    cleaned_action = clean_action(step_action, current_test.get('title_part', ''))
                    
                    # Skip steps that mention out-of-scope content (hotkeys/tooltips)
                    if not cleaned_action or 'hotkey' in cleaned_action.lower() or 'tooltip' in cleaned_action.lower():
                        continue
                    
                    # Clean expected result
                    if should_have_expected(cleaned_action):
                        cleaned_expected = clean_expected(step_expected)
                    else:
                        cleaned_expected = ""
                    
                    current_test['steps'].append({
                        'step': step_num,
                        'action': cleaned_action,
                        'expected': cleaned_expected
                    })
        
        # Don't forget the last test case
        if current_test:
            test_cases.append(current_test)
    
    # Regenerate with correct IDs and clean actions
    fixed_test_cases = []
    for idx, tc in enumerate(test_cases):
        new_id = get_next_test_id(idx)
        # Clean title first
        cleaned_title_part = clean_title(tc['title_part'])
        full_title = f"{new_id}: {cleaned_title_part}"
        
        # Clean all step actions for this test case
        cleaned_steps = []
        for step in tc['steps']:
            cleaned_action = clean_action(step['action'], full_title)
            # Skip steps with out-of-scope content
            if cleaned_action and 'hotkey' not in cleaned_action.lower() and 'tooltip' not in cleaned_action.lower():
                # Re-clean expected if action changed
                if should_have_expected(cleaned_action):
                    cleaned_expected = clean_expected(step.get('expected', ''))
                    # Also clean expected for tablet-specific fixes
                    cleaned_expected = clean_expected_for_tablet(cleaned_expected, full_title)
                else:
                    cleaned_expected = ""
                cleaned_steps.append({
                    'step': step['step'],
                    'action': cleaned_action,
                    'expected': cleaned_expected
                })
        
        # Skip test cases with no valid steps
        if not cleaned_steps:
            continue
        
        fixed_test_cases.append({
            'id': new_id,
            'title': full_title,
            'steps': cleaned_steps,
            'area_path': tc['area_path'],
            'assigned_to': 'gulzhas.mailybayeva@kandasoft.com',  # Fixed format
            'state': tc['state']
        })
    
    # Write fixed CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        
        # Header
        writer.writerow(['ID', 'Work Item Type', 'Title', 'Test Step', 'Step Action', 'Step Expected',
                         'Area Path', 'Assigned To', 'State'])
        
        # Write test cases
        for tc in fixed_test_cases:
            # Test case header row
            writer.writerow([
                '',  # ID (blank for ADO import)
                'Test Case',
                tc['title'],
                '',
                '',
                '',
                tc['area_path'],
                tc['assigned_to'],
                tc['state']
            ])
            
            # Step rows
            for step in tc['steps']:
                writer.writerow([
                    '',
                    '',
                    '',
                    step['step'],
                    step['action'],
                    step['expected'],
                    '',
                    '',
                    ''
                ])
    
    print(f"✓ Fixed CSV: {len(fixed_test_cases)} test cases")
    print(f"✓ ID sequencing: AC1, 005, 010, 015...")
    print(f"✓ Removed forbidden words from expected results")
    print(f"✓ Removed expected results from setup steps")
    print(f"✓ Fixed Assigned To format")
    
    # Generate objectives file using new objective generation logic
    from src.test_generator import TestGenerator
    
    generator = TestGenerator()
    
    with open(OUTPUT_OBJECTIVES, 'w', encoding='utf-8') as f:
        for tc in fixed_test_cases:
            # Extract title without ID prefix
            title_without_id = tc['title'].split(': ', 1)[1] if ': ' in tc['title'] else tc['title']
            
            # Parse title to extract components for objective generation
            # Format: "Feature / Entry Point / Scenario"
            title_parts = title_without_id.split(' / ') if ' / ' in title_without_id else [title_without_id]
            
            feature = title_parts[0] if title_parts else "feature"
            ui_area = title_parts[1] if len(title_parts) > 1 else None
            scenario = title_parts[-1] if title_parts else ""
            
            # Determine category and device from scenario
            scenario_lower = scenario.lower()
            category = "availability" if "availability" in scenario_lower or "access" in scenario_lower else "behavior"
            
            # Check for device/platform in title
            device = None
            if "(iPad" in tc['title'] or "iPad" in scenario:
                device = "iPad"
            elif "(Android Tablet" in tc['title'] or "Android Tablet" in scenario:
                device = "Android Tablet"
            elif "Windows 11" in scenario:
                device = "Windows 11"
            
            # Check if accessibility test
            is_accessibility = "accessibility" in scenario_lower or "keyboard" in scenario_lower or "focus" in scenario_lower or "label" in scenario_lower or "role" in scenario_lower or "contrast" in scenario_lower or "touch" in scenario_lower or "voiceover" in scenario_lower.lower()
            
            # Generate objective using new logic
            objective = generator.generate_objective(
                title=tc['title'],
                scenario=scenario,
                feature=feature,
                category=category,
                ui_area=ui_area or "",
                device=device,
                is_accessibility=is_accessibility
            )
            
            f.write(f"{tc['id']}: {title_without_id}\n")
            f.write(f"{objective}\n\n")
    
    print(f"✓ Generated objectives file: {OUTPUT_OBJECTIVES}")
    print(f"\nSummary:")
    print(f"  Total test cases: {len(fixed_test_cases)}")
    print(f"  First ID: {fixed_test_cases[0]['id']}")
    print(f"  Second ID: {fixed_test_cases[1]['id'] if len(fixed_test_cases) > 1 else 'N/A'}")
    print(f"  Last ID: {fixed_test_cases[-1]['id']}")


if __name__ == '__main__':
    fix_csv()
