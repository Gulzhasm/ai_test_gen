#!/usr/bin/env python3
"""
Update Test Objectives file for story 272981 with new edge case tests.
"""
from pathlib import Path

def update_objectives():
    objectives_file = Path('output/272981_Test_Objectives.txt')
    
    # Read existing objectives
    with open(objectives_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add new objectives for edge case tests
    new_objectives = """
272981-095: 272981-095: Help: About App / Tools Menu / Support link opens in default browser
Objective: Verify that the support link in the About App dialog window is clickable and opens the default browser with the support URL.

272981-100: 272981-100: Help: About App / Tools Menu / Escape key closes dialog
Objective: Verify that pressing the Escape key closes the About App dialog window.

272981-105: 272981-105: Help: About App / Tools Menu / Dialog modal behavior
Objective: Verify that the About App dialog window behaves as a modal dialog, preventing interaction with the main application window while open.

272981-110: 272981-110: Help: About App / Tools Menu / Version string format validation
Objective: Verify that the version string displayed in the About App dialog window follows the correct format (X.Y.Z.B) with numeric values.

272981-115: 272981-115: Help: About App / Tools Menu / Copyright year validation
Objective: Verify that the copyright text displayed in the About App dialog window includes a valid year or year range.

272981-120: 272981-120: Help: About App / Tools Menu / Multiple dialog instances prevention
Objective: Verify that only one About App dialog window can be open at a time, preventing duplicate dialog instances.

272981-125: 272981-125: Help: About App / Tools Menu / Dialog window positioning
Objective: Verify that the About App dialog window is properly positioned and centered relative to the main application window.

272981-130: 272981-130: Help: About App / Tools Menu / Support link keyboard accessibility
Objective: Verify that the support link in the About App dialog window is accessible via keyboard navigation and can be activated using Enter or Space key.

272981-135: 272981-135: Help: About App / Tools Menu / Support link opens in default browser (Windows 11)
Objective: Verify that the support link in the About App dialog window opens the default browser with the support URL on Windows 11.

272981-140: 272981-140: Help: About App / Tools Menu / Support link opens in default browser (Tablets)
Objective: Verify that the support link in the About App dialog window opens the default browser with the support URL on tablet (iPad or Android Tablet).

272981-145: 272981-145: Help: About App / Tools Menu / Version string displayed correctly (Windows 11)
Objective: Verify that the full installed version string is displayed correctly in the About App dialog window on Windows 11.

272981-150: 272981-150: Help: About App / Tools Menu / Version string displayed correctly (Tablets)
Objective: Verify that the full installed version string is displayed correctly in the About App dialog window on tablet (iPad or Android Tablet).
"""
    
    # Append new objectives
    with open(objectives_file, 'a', encoding='utf-8') as f:
        f.write(new_objectives)
    
    print(f"✓ Successfully updated {objectives_file}")
    print(f"  Added objectives for 12 new test cases")

if __name__ == '__main__':
    update_objectives()
