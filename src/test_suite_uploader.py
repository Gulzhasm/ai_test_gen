"""
Test Suite Uploader
Uploads generated tests directly to ADO test suites
"""

from typing import List, Dict, Optional
import requests
import time
import re


class TestSuiteUploader:
    """Uploads test cases to ADO test suites."""

    def __init__(self, ado_client):
        self.client = ado_client
        self.base_url = ado_client.base_url
        self.headers = ado_client.headers
        self.project = "Env"

    def find_test_suite_by_story_id(self, story_id: int) -> Optional[Dict]:
        """Find test suite by story ID.

        Searches for suite name starting with: {story_id}:
        Example: "269496: Model Space and Canvas" or "269496 : Model Space and Canvas"

        Args:
            story_id: Story ID to search for

        Returns:
            Test suite info or None if not found
        """
        prefix = f"{story_id} :"  # Space before colon

        # Get all test plans for project
        url = f"{self.base_url}/_apis/testplan/plans?api-version=7.1"

        try:
            print(f"  Searching test plans in project '{self.project}'...")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            plans = response.json().get('value', [])
            print(f"  Found {len(plans)} test plan(s)")

            # Search suites in each plan
            for plan in plans:
                plan_id = plan['id']
                plan_name = plan.get('name', 'Unknown')

                print(f"    Checking plan: {plan_name} (ID: {plan_id})")

                # Get root suite and child suites
                suite = self._search_suites_recursive(plan_id, prefix)

                if suite:
                    return suite

            print(f"  ✗ No test suite found with prefix '{prefix}'")
            return None

        except Exception as e:
            print(f"  ✗ Error finding test suite: {e}")
            return None

    def _search_suites_recursive(self, plan_id: int, prefix: str) -> Optional[Dict]:
        """Recursively search suites in a test plan.

        Args:
            plan_id: Test plan ID
            prefix: Suite name prefix (e.g., "269496:")

        Returns:
            Suite info or None
        """
        try:
            # Get test plan with suites
            url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}?api-version=7.1"
            response = requests.get(url, headers=self.headers)

            if response.status_code != 200:
                return None

            plan_data = response.json()

            # Get root suite
            root_suite_id = plan_data.get('rootSuite', {}).get('id')

            if not root_suite_id:
                return None

            # Search from root suite
            return self._search_suite_tree(plan_id, root_suite_id, prefix)

        except Exception:
            return None

    def _search_suite_tree(self, plan_id: int, suite_id: int, prefix: str) -> Optional[Dict]:
        """Search suite and its children for matching name.

        Args:
            plan_id: Test plan ID
            suite_id: Suite ID to search
            prefix: Name prefix

        Returns:
            Suite info or None
        """
        try:
            # Get suite details
            url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}?api-version=7.1"
            response = requests.get(url, headers=self.headers)

            if response.status_code != 200:
                return None

            suite = response.json()
            suite_name = suite.get('name', '')
            has_children = suite.get('hasChildren', False)

            # Check if this suite matches
            if suite_name.startswith(prefix):
                print(f"      ✓ Found matching suite: {suite_name}")
                return {
                    'id': suite['id'],
                    'name': suite_name,
                    'plan_id': plan_id
                }

            # Check children - Try newer Test Plans API
            if has_children:
                # Try Test Plans API (v7.1) for getting suites
                suites_url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}/suites?api-version=7.1"
                suites_response = requests.get(suites_url, headers=self.headers)

                if suites_response.status_code == 200:
                    all_suites = suites_response.json().get('value', [])

                    # Filter for child suites (not root)
                    for suite_item in all_suites:
                        s_id = suite_item.get('id')
                        s_name = suite_item.get('name', '')

                        if s_id != suite_id and s_name.startswith(prefix):
                            print(f"      ✓ Found matching suite: {s_name}")
                            return {
                                'id': s_id,
                                'name': s_name,
                                'plan_id': plan_id
                            }

            return None

        except Exception:
            return None

    def upload_tests_to_suite(self, suite_info: Dict, test_cases: List[Dict]) -> List[int]:
        """Upload test cases to test suite.

        Args:
            suite_info: Test suite info with id, name, plan_id
            test_cases: List of test case dictionaries

        Returns:
            List of created test case IDs
        """
        created_ids = []
        suite_id = suite_info['id']
        plan_id = suite_info['plan_id']

        for idx, test_case in enumerate(test_cases, 1):
            print(f"  [{idx}/{len(test_cases)}] Creating {test_case['id']}...", end=' ')

            test_case_id = self._create_test_case(test_case)

            if test_case_id:
                # Add test case to suite
                added = self._add_test_to_suite(plan_id, suite_id, test_case_id)

                if added:
                    created_ids.append(test_case_id)
                    print(f"✓ (ID: {test_case_id})")
                else:
                    print(f"✗ Failed to add to suite")
            else:
                print(f"✗ Failed to create")

            # Rate limiting
            time.sleep(0.5)

        return created_ids

    def _create_test_case(self, test_case: Dict) -> Optional[int]:
        """Create a test case work item.

        Args:
            test_case: Test case dictionary with id, title, steps

        Returns:
            Created test case ID or None
        """
        url = f"{self.base_url}/_apis/wit/workitems/$Test Case?api-version=7.1"

        # Build patch document
        patch_doc = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": test_case['title']
            },
            {
                "op": "add",
                "path": "/fields/System.AssignedTo",
                "value": "gulzhas.mailybayeva@kandasoft.com"
            },
            {
                "op": "add",
                "path": "/fields/System.State",
                "value": "Design"
            },
            {
                "op": "add",
                "path": "/fields/System.AreaPath",
                "value": "Env\\ENV Kanda"
            }
        ]

        # Add test steps
        steps_xml = self._build_steps_xml(test_case['steps'])
        patch_doc.append({
            "op": "add",
            "path": "/fields/Microsoft.VSTS.TCM.Steps",
            "value": steps_xml
        })

        headers = self.headers.copy()
        headers['Content-Type'] = 'application/json-patch+json'

        try:
            response = requests.post(url, headers=headers, json=patch_doc)
            response.raise_for_status()

            data = response.json()
            return data.get('id')

        except Exception as e:
            return None

    def _build_steps_xml(self, steps: List[Dict]) -> str:
        """Build XML for test steps.

        Args:
            steps: List of step dictionaries with action and expected

        Returns:
            XML string for ADO
        """
        xml_parts = ['<steps id="0" last="{}">'.format(len(steps) - 1)]

        for idx, step in enumerate(steps, start=1):
            action = step.get('action', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            expected = step.get('expected', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            xml_parts.append(f'  <step id="{idx}" type="ValidateStep">')
            xml_parts.append(f'    <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{action}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>')
            xml_parts.append(f'    <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{expected}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>')
            xml_parts.append(f'    <description/>')
            xml_parts.append(f'  </step>')

        xml_parts.append('</steps>')

        return '\n'.join(xml_parts)

    def _add_test_to_suite(self, plan_id: int, suite_id: int, test_case_id: int) -> bool:
        """Add test case to test suite.

        Args:
            plan_id: Test plan ID
            suite_id: Test suite ID
            test_case_id: Test case work item ID

        Returns:
            True if successful
        """
        url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase?api-version=7.1"

        # Request body with test case reference
        body = [{
            'workItem': {
                'id': test_case_id
            }
        }]

        try:
            response = requests.post(url, headers=self.headers, json=body)
            return response.status_code == 200

        except Exception:
            return False

    def update_test_objectives(self, test_case_ids: List[int], test_cases: List[Dict]) -> int:
        """Update Summary field (objectives) for test cases.

        Args:
            test_case_ids: List of created test case IDs
            test_cases: Original test case data with objectives

        Returns:
            Number of successfully updated test cases
        """
        # Create mapping of test ID prefix to objective
        objective_map = {}
        for tc in test_cases:
            tc_id = tc['id']
            objective = tc.get('objective', '')
            objective_map[tc_id] = objective

        updated_count = 0

        from src.objective_generator import ObjectiveGenerator
        obj_gen = ObjectiveGenerator()

        for ado_id in test_case_ids:
            # Get test case to find its title
            try:
                url = f"{self.base_url}/_apis/wit/workitems/{ado_id}?api-version=7.1"
                response = requests.get(url, headers=self.headers)

                if response.status_code == 200:
                    data = response.json()
                    title = data.get('fields', {}).get('System.Title', '')

                    # Extract test ID from title (e.g., "272888-AC1")
                    test_id_match = title.split(':')[0].strip() if ':' in title else None

                    if test_id_match and test_id_match in objective_map:
                        objective_text = objective_map[test_id_match]
                        formatted_objective = obj_gen.format_objective_for_ado(objective_text)

                        # Update Summary field
                        result = self.client.update_work_item_field(
                            ado_id,
                            'System.Description',
                            formatted_objective
                        )

                        if result:
                            updated_count += 1

            except Exception:
                continue

            time.sleep(0.3)

        return updated_count
