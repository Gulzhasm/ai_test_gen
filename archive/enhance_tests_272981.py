#!/usr/bin/env python3
"""
Enhance test cases for story 272981 with edge cases, accessibility, and cross-platform tests.
"""
import csv
import re
from pathlib import Path

def read_csv(file_path):
    """Read CSV file and return test cases."""
    test_cases = []
    current_tc = None
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get('Title', '').strip()
            step_action = row.get('Step Action', '').strip()
            step_expected = row.get('Step Expected', '').strip()
            test_step = row.get('Test Step', '').strip()
            
            if title and title != 'Title':
                # New test case
                if current_tc:
                    test_cases.append(current_tc)
                current_tc = {
                    'title': title,
                    'steps': []
                }
            
            if test_step and step_action:
                if current_tc:
                    current_tc['steps'].append({
                        'action': step_action,
                        'expected': step_expected
                    })
        
        if current_tc:
            test_cases.append(current_tc)
    
    return test_cases

def write_csv(test_cases, file_path):
    """Write test cases to CSV file."""
    def format_csv_value(value):
        """Format CSV value: quote non-empty values."""
        if value == '' or value is None:
            return ''
        import io
        output = io.StringIO()
        csv.writer(output, quoting=csv.QUOTE_MINIMAL).writerow([str(value)])
        formatted = output.getvalue().rstrip('\n\r')
        return formatted
    
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        header = ['ID', 'Work Item Type', 'Title', 'Test Step', 'Step Action', 'Step Expected',
                 'Area Path', 'Assigned To', 'State']
        f.write(','.join(header) + '\n')
        
        for tc in test_cases:
            # Header row
            row = [
                '',
                'Test Case',
                tc['title'],
                '',
                '',
                '',
                'Env\\ENV Kanda',
                'Gulzhas Mailybayeva <gulzhas.mailybayeva@kandasoft.com>',
                'Design'
            ]
            formatted_row = [format_csv_value(val) for val in row]
            f.write(','.join(formatted_row) + '\n')
            
            # Step rows
            for idx, step in enumerate(tc['steps'], start=1):
                row = [
                    '',
                    '',
                    '',
                    str(idx),
                    step['action'],
                    step['expected'],
                    '',
                    '',
                    ''
                ]
                formatted_row = [format_csv_value(val) for val in row]
                f.write(','.join(formatted_row) + '\n')

def generate_edge_case_tests():
    """Generate edge case tests."""
    edge_cases = []
    
    # Edge Case 1: Support link clickability and browser opening
    edge_cases.append({
        'title': '272981-095: Help: About App / Tools Menu / Support link opens in default browser',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Click on the Support link in the About App dialog window.', 'expected': 'Support link is clicked.'},
            {'action': 'Verify that the default browser opens and navigates to the support URL.', 'expected': 'Default browser opens and navigates to the support URL.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 2: Escape key closes dialog
    edge_cases.append({
        'title': '272981-100: Help: About App / Tools Menu / Escape key closes dialog',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Press Escape key.', 'expected': 'Escape key is pressed.'},
            {'action': 'Verify that the About App dialog window closes.', 'expected': 'About App dialog window closes when Escape key is pressed.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 3: Dialog modal behavior - cannot interact with main app
    edge_cases.append({
        'title': '272981-105: Help: About App / Tools Menu / Dialog modal behavior',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Attempt to interact with the main application window (click on Canvas or menu).', 'expected': 'Interaction with main application is attempted.'},
            {'action': 'Verify that the main application window is disabled or non-interactive while the About App dialog is open.', 'expected': 'Main application window is disabled or non-interactive while About App dialog is open.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 4: Version string format validation
    edge_cases.append({
        'title': '272981-110: Help: About App / Tools Menu / Version string format validation',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Verify that the version string follows the format X.Y.Z.B (e.g., 1.0.0.56) with numeric values.', 'expected': 'Version string follows the format X.Y.Z.B with numeric values in the About App dialog window.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 5: Copyright year validation
    edge_cases.append({
        'title': '272981-115: Help: About App / Tools Menu / Copyright year validation',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Verify that the copyright text includes the current year or a valid year range.', 'expected': 'Copyright text includes the current year or a valid year range in the About App dialog window.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 6: Multiple dialog instances (should not be allowed)
    edge_cases.append({
        'title': '272981-120: Help: About App / Tools Menu / Multiple dialog instances prevention',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Attempt to open About App dialog again from Help Menu while the dialog is already open.', 'expected': 'Attempt to open About App dialog again is performed.'},
            {'action': 'Verify that only one About App dialog window is displayed (no duplicate dialogs).', 'expected': 'Only one About App dialog window is displayed with no duplicate dialogs.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 7: Window positioning and centering
    edge_cases.append({
        'title': '272981-125: Help: About App / Tools Menu / Dialog window positioning',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Verify that the About App dialog window is properly positioned and centered relative to the main application window.', 'expected': 'About App dialog window is properly positioned and centered relative to the main application window.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 8: Support link keyboard accessibility
    edge_cases.append({
        'title': '272981-130: Help: About App / Tools Menu / Support link keyboard accessibility',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application.', 'expected': ''},
            {'action': 'Open Help Menu using keyboard navigation.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option using keyboard navigation.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Navigate to the Support link using Tab key.', 'expected': 'Support link receives keyboard focus.'},
            {'action': 'Activate the Support link using Enter or Space key.', 'expected': 'Support link is activated using keyboard.'},
            {'action': 'Verify that the default browser opens and navigates to the support URL.', 'expected': 'Default browser opens and navigates to the support URL when Support link is activated via keyboard.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 9: Cross-platform - Support link (Windows 11)
    edge_cases.append({
        'title': '272981-135: Help: About App / Tools Menu / Support link opens in default browser (Windows 11)',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application on Windows 11.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Click on the Support link in the About App dialog window.', 'expected': 'Support link is clicked.'},
            {'action': 'Verify that the default browser opens and navigates to the support URL on Windows 11.', 'expected': 'Default browser opens and navigates to the support URL on Windows 11.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 10: Cross-platform - Support link (Tablets)
    edge_cases.append({
        'title': '272981-140: Help: About App / Tools Menu / Support link opens in default browser (Tablets)',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application on tablet (iPad or Android Tablet).', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Tap on the Support link in the About App dialog window.', 'expected': 'Support link is tapped.'},
            {'action': 'Verify that the default browser opens and navigates to the support URL on tablet (iPad or Android Tablet).', 'expected': 'Default browser opens and navigates to the support URL on tablet (iPad or Android Tablet).'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 11: Cross-platform - Version display (Windows 11)
    edge_cases.append({
        'title': '272981-145: Help: About App / Tools Menu / Version string displayed correctly (Windows 11)',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application on Windows 11.', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Verify that the full installed version string is displayed correctly in the About App dialog window on Windows 11.', 'expected': 'Full installed version string is displayed correctly in the About App dialog window on Windows 11.'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    # Edge Case 12: Cross-platform - Version display (Tablets)
    edge_cases.append({
        'title': '272981-150: Help: About App / Tools Menu / Version string displayed correctly (Tablets)',
        'steps': [
            {'action': 'PRE-REQ: ENV QuickDraw application is installed', 'expected': ''},
            {'action': 'Launch ENV QuickDraw application on tablet (iPad or Android Tablet).', 'expected': ''},
            {'action': 'Open Help Menu.', 'expected': 'Help Menu opens and is displayed.'},
            {'action': 'Select About App option.', 'expected': 'About App option is selected and About App dialog window opens.'},
            {'action': 'Verify that the full installed version string is displayed correctly in the About App dialog window on tablet (iPad or Android Tablet).', 'expected': 'Full installed version string is displayed correctly in the About App dialog window on tablet (iPad or Android Tablet).'},
            {'action': 'Close/Exit the QuickDraw application.', 'expected': ''}
        ]
    })
    
    return edge_cases

def main():
    csv_file = Path('output/272981_Test_Cases.csv')
    
    # Read existing test cases
    print(f"Reading existing test cases from {csv_file}...")
    test_cases = read_csv(csv_file)
    print(f"Found {len(test_cases)} existing test cases")
    
    # Generate edge case tests
    print("Generating edge case and additional cross-platform tests...")
    edge_cases = generate_edge_case_tests()
    print(f"Generated {len(edge_cases)} additional test cases")
    
    # Add edge cases to test cases
    test_cases.extend(edge_cases)
    
    # Write updated CSV
    print(f"Writing {len(test_cases)} test cases to {csv_file}...")
    write_csv(test_cases, csv_file)
    print(f"✓ Successfully updated {csv_file}")
    print(f"  Added {len(edge_cases)} new test cases covering:")
    print("    - Support link clickability and browser opening")
    print("    - Escape key to close dialog")
    print("    - Dialog modal behavior")
    print("    - Version string format validation")
    print("    - Copyright year validation")
    print("    - Multiple dialog instances prevention")
    print("    - Window positioning")
    print("    - Support link keyboard accessibility")
    print("    - Cross-platform tests for support link and version display")

if __name__ == '__main__':
    main()
