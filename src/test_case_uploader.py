"""
Test Case Uploader Module
Uploads test cases directly to ADO using REST APIs.
Handles test case creation, step formatting, and suite membership.
"""
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET
import requests
from src.ado_client import ADOClient
from src.objective_generator import ObjectiveGenerator
import config


class TestCaseUploader:
    """Uploads test cases to ADO."""
    
    def __init__(self, client: ADOClient):
        self.client = client
        self.base_url = client.base_url
        self.objective_gen = ObjectiveGenerator()
    
    def format_steps_for_ado(self, steps: List[Dict[str, str]]) -> str:
        """Format test steps as ADO XML format (Microsoft.VSTS.TCM.Steps).
        
        ADO expects steps in this XML format:
        <steps id="0" last="N">
            <step id="1" type="ActionStep">
                <parameterizedString isformatted="true">Action text</parameterizedString>
                <parameterizedString isformatted="true">Expected result text</parameterizedString>
            </step>
            ...
        </steps>
        
        Args:
            steps: List of step dictionaries with 'action' and 'expected' keys
            
        Returns:
            XML string formatted for ADO
        """
        if not steps:
            return ""
        
        # Create root steps element
        steps_elem = ET.Element('steps', id="0", last=str(len(steps)))
        
        for idx, step in enumerate(steps, start=1):
            step_elem = ET.Element('step', id=str(idx), type="ActionStep")
            
            # Action text
            action_elem = ET.SubElement(step_elem, 'parameterizedString', isformatted="true")
            action_elem.text = step.get('action', '')
            
            # Expected result text
            expected_elem = ET.SubElement(step_elem, 'parameterizedString', isformatted="true")
            expected_elem.text = step.get('expected', '')
            
            steps_elem.append(step_elem)
        
        # Convert to XML string
        xml_str = ET.tostring(steps_elem, encoding='unicode', method='xml')
        return xml_str
    
    def create_test_case(self, title: str, steps: List[Dict[str, str]], 
                        objective: Optional[str] = None, test_case_id: Optional[str] = None) -> Optional[int]:
        """Create a Test Case work item in ADO.
        
        Args:
            title: Test case title
            steps: List of step dictionaries
            objective: Optional objective text for System.Description (will be formatted for ADO)
            test_case_id: Optional test case ID (e.g., "270738-AC1") for objective formatting
            
        Returns:
            Test case work item ID if successful, None otherwise
        """
        url = f"{self.base_url}/_apis/wit/workitems/$Test Case?api-version=7.1"
        
        # Format steps as ADO XML
        steps_xml = self.format_steps_for_ado(steps)
        
        # Build patch document
        patch_doc = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": title
            },
            {
                "op": "add",
                "path": "/fields/System.AreaPath",
                "value": config.ADO_AREA_PATH
            },
            {
                "op": "add",
                "path": "/fields/System.AssignedTo",
                "value": config.ASSIGNED_TO
            },
            {
                "op": "add",
                "path": "/fields/System.State",
                "value": config.DEFAULT_STATE
            },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.TCM.Steps",
                "value": steps_xml
            }
        ]
        
        # Add objective if provided (format for ADO with ID and title)
        if objective:
            # Format: "<TESTCASE ID>: <Title>\nObjective: Verify that …"
            if test_case_id:
                formatted_objective = f"<b>{test_case_id}: {title}</b><br/><br/>"
            else:
                formatted_objective = f"<b>{title}</b><br/><br/>"
            # Add formatted objective text
            formatted_objective += self.objective_gen.format_objective_for_ado(objective)
            patch_doc.append({
                "op": "add",
                "path": "/fields/System.Description",
                "value": formatted_objective
            })
        
        headers = self.client.headers.copy()
        headers['Content-Type'] = 'application/json-patch+json'
        
        try:
            response = requests.patch(url, headers=headers, json=patch_doc)
            response.raise_for_status()
            
            work_item = response.json()
            test_case_id = work_item.get('id')
            
            print(f"    ✓ Created test case: {test_case_id} - {title}")
            return test_case_id
            
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail.get('message', e.response.text[:200])}"
                except:
                    error_msg += f" - {e.response.text[:200]}"
            print(f"    ✗ Error creating test case '{title}': {error_msg}")
            return None
    
    def add_test_case_to_suite(self, plan_id: int, suite_id: int, test_case_id: int) -> bool:
        """Add a test case to a test suite.
        
        Args:
            plan_id: Test plan ID
            suite_id: Test suite ID
            test_case_id: Test case work item ID
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/testcases/{test_case_id}?api-version=7.1-preview.3"
        
        headers = self.client.headers.copy()
        headers['Content-Type'] = 'application/json'
        
        try:
            response = requests.post(url, headers=headers, json={})
            response.raise_for_status()
            
            print(f"      ✓ Added test case {test_case_id} to suite {suite_id}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail.get('message', e.response.text[:200])}"
                except:
                    error_msg += f" - {e.response.text[:200]}"
            print(f"      ✗ Error adding test case {test_case_id} to suite: {error_msg}")
            return False
    
    def upload_objective(self, test_case_id: int, objective: str) -> bool:
        """Upload objective to test case Summary field (System.Description).
        
        Args:
            test_case_id: Test case work item ID
            objective: Objective text (will be formatted for ADO)
            
        Returns:
            True if successful, False otherwise
        """
        # Format objective for ADO Summary field
        formatted_objective = self.objective_gen.format_objective_for_ado(objective)
        return self.client.update_work_item_field(
            test_case_id, 
            'System.Description', 
            formatted_objective, 
            operation='replace'
        ) is not None
    
    def upload_test_cases(self, test_cases: List[Dict], plan_id: int, suite_id: int) -> Dict:
        """Upload multiple test cases to ADO and add them to a suite.
        
        Args:
            test_cases: List of test case dictionaries with 'title', 'steps', 'objective'
            plan_id: Test plan ID
            suite_id: Test suite ID
            
        Returns:
            Dictionary with upload results:
            {
                'total': <count>,
                'created': [<list of created IDs>],
                'failed': [<list of failed titles>],
                'suite_added': <count>,
                'suite_failed': [<list of failed IDs>]
            }
        """
        results = {
            'total': len(test_cases),
            'created': [],
            'failed': [],
            'suite_added': [],
            'suite_failed': []
        }
        
        print(f"\nUploading {len(test_cases)} test cases to ADO...")
        
        for tc in test_cases:
            title = tc.get('title', '')
            steps = tc.get('steps', [])
            objective = tc.get('objective', '')
            tc_id = tc.get('id', '')  # Test case ID (e.g., "270738-AC1")
            
            # Create test case with ID and title in objective
            test_case_id = self.create_test_case(title, steps, objective, test_case_id=tc_id)
            
            if test_case_id:
                results['created'].append(test_case_id)
                
                # Add to suite
                if self.add_test_case_to_suite(plan_id, suite_id, test_case_id):
                    results['suite_added'].append(test_case_id)
                else:
                    results['suite_failed'].append(test_case_id)
            else:
                results['failed'].append(title)
        
        return results
