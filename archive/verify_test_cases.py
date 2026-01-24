#!/usr/bin/env python3
"""
Generic script to retrieve and verify test cases for a user story in Azure DevOps.

Usage:
    python verify_test_cases.py <story_id>
    
Example:
    python verify_test_cases.py 272981
"""

import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ado_client import ADOClient
import config


def main():
    """Main function to verify test cases."""
    if len(sys.argv) < 2:
        print("Usage: python verify_test_cases.py <story_id>")
        print("Example: python verify_test_cases.py 272981")
        sys.exit(1)
    
    try:
        story_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid story ID")
        sys.exit(1)
    
    if not config.ADO_PAT:
        print("ERROR: ADO_PAT environment variable is required")
        sys.exit(1)
    
    print("=" * 80)
    print("VERIFYING TEST CASES IN AZURE DEVOPS")
    print("=" * 80)
    print(f"Story ID: {story_id}")
    print(f"Organization: {config.ADO_ORG}")
    print(f"Project: {config.ADO_PROJECT}")
    print("=" * 80)
    
    try:
        # Initialize ADO client
        client = ADOClient()
        
        # Retrieve and verify test cases
        print(f"\n1. Retrieving test cases for story {story_id}...")
        result = client.verify_test_cases_exist(story_id)
        
        print(f"\n2. Test Cases Found: {result['total_found']}")
        print("-" * 80)
        
        if result['total_found'] == 0:
            print("   ✗ No test cases found for this story")
            print("\n   Possible reasons:")
            print("   - Test cases have not been uploaded yet")
            print("   - Test case titles do not contain the story ID")
            print("   - Test cases exist but are in a different project/area")
            sys.exit(1)
        
        # Display test cases
        for i, tc in enumerate(result['test_cases'], 1):
            status_icon = "✓" if tc['work_item_type'] == 'Test Case' else "✗"
            print(f"   {status_icon} [{tc['id']}] {tc['title'][:70]}...")
            print(f"      State: {tc['state']}, Type: {tc['work_item_type']}")
            if i < len(result['test_cases']):
                print()
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Story ID: {story_id}")
        print(f"Total test cases found: {result['total_found']}")
        print(f"Test case IDs: {', '.join(map(str, result['verified_ids']))}")
        
        if result['missing_ids']:
            print(f"\n⚠ Missing expected test case IDs: {', '.join(map(str, result['missing_ids']))}")
            print(f"   All exist: {result['all_exist']}")
        else:
            print(f"\n✓ All test cases exist in ADO")
        
        print("\n" + "=" * 80)
        print("VERIFICATION COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
