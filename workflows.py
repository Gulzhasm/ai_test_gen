#!/usr/bin/env python3
"""
Test Case Workflows - Clean, Generic, Extendable Framework

Three workflows:
1. generate    - Generate test cases (rule-based + optional LLM correction)
2. upload      - Generate + Upload to ADO test suite (strict {story_id} : {name} pattern)
3. update-objectives - Update objectives for existing test cases from CSV mapping

Usage:
    python3 workflows.py generate --story-id 272889
    python3 workflows.py upload --story-id 272889
    python3 workflows.py update-objectives --csv <file> --objectives <file>

Architecture:
    - WorkflowEngine: Orchestrates workflow execution
    - IWorkflow: Interface for all workflows
    - Each workflow is a separate class implementing IWorkflow
"""
import argparse
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


# =============================================================================
# DOMAIN: Workflow Result
# =============================================================================

class WorkflowStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class WorkflowResult:
    """Result of workflow execution."""
    status: WorkflowStatus
    message: str
    data: Dict[str, Any] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


# =============================================================================
# INTERFACE: IWorkflow
# =============================================================================

class IWorkflow(ABC):
    """Interface for all workflows."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Workflow name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Workflow description."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> WorkflowResult:
        """Execute the workflow."""
        pass

    @abstractmethod
    def validate_inputs(self, **kwargs) -> Optional[str]:
        """Validate inputs. Returns error message or None if valid."""
        pass


# =============================================================================
# WORKFLOW 1: Generate Test Cases
# =============================================================================

class GenerateWorkflow(IWorkflow):
    """
    Generate test cases using rule-based generator + optional LLM correction.

    Outputs:
    - CSV file (ADO-ready format)
    - Objectives TXT file (1:1 mapped)
    - Debug JSON file
    """

    @property
    def name(self) -> str:
        return "generate"

    @property
    def description(self) -> str:
        return "Generate test cases (rule-based + optional LLM correction)"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_id = kwargs.get('story_id')
        if not story_id:
            return "story_id is required"
        if not isinstance(story_id, int) or story_id <= 0:
            return "story_id must be a positive integer"
        return None

    def execute(self, **kwargs) -> WorkflowResult:
        import os
        import json
        from src.ado_client import ADOClient
        from src.comprehensive_test_generator import ComprehensiveTestGenerator
        from src.csv_generator import CSVGenerator
        from src.objective_generator import ObjectiveGenerator
        import config

        story_id = kwargs['story_id']
        output_dir = kwargs.get('output_dir', 'output')
        skip_correction = kwargs.get('skip_correction', False)

        print(f"\n{'='*60}")
        print(f"WORKFLOW: Generate Test Cases")
        print(f"Story ID: {story_id}")
        print(f"Mode: {'Rule-based only' if skip_correction else 'Rule-based + LLM Correction'}")
        print(f"{'='*60}\n")

        # Step 1: Fetch story data
        print("[1/3] Fetching story data from ADO...")
        try:
            ado_client = ADOClient()
            story_data = ado_client.fetch_story_comprehensive(story_id)
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to fetch story: {e}"
            )

        title = story_data['title']
        acceptance_criteria = story_data['acceptance_criteria']
        qa_prep = story_data['qa_prep']

        print(f"  Title: {title}")
        print(f"  Acceptance Criteria: {len(acceptance_criteria)} items")

        if not acceptance_criteria:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="No acceptance criteria found"
            )

        # Step 2: Generate test cases
        print("\n[2/3] Generating test cases...")
        generator = ComprehensiveTestGenerator()
        test_cases = generator.generate_test_cases(
            story_data={'story_id': story_id, 'title': title},
            criteria=acceptance_criteria,
            qa_prep_content=qa_prep
        )
        print(f"  Generated {len(test_cases)} test cases")

        # Optional LLM correction
        if not skip_correction:
            test_cases = self._apply_llm_correction(
                test_cases, story_id, title, acceptance_criteria, qa_prep
            )

        # Step 3: Save outputs
        print("\n[3/3] Saving outputs...")
        output_files = self._save_outputs(
            story_id, title, test_cases, output_dir, skip_correction
        )

        print(f"\n{'='*60}")
        print("GENERATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Test cases: {len(test_cases)}")
        for key, path in output_files.items():
            print(f"  {key}: {path}")

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            message=f"Generated {len(test_cases)} test cases",
            data={
                'test_cases': test_cases,
                'output_files': output_files,
                'story_id': story_id,
                'title': title
            }
        )

    def _apply_llm_correction(
        self,
        test_cases: List[Dict],
        story_id: int,
        title: str,
        acceptance_criteria: List[str],
        qa_prep: str
    ) -> List[Dict]:
        """Apply LLM correction to generated test cases."""
        import os
        import config

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your-api-key-here":
            print("  OPENAI_API_KEY not configured, skipping LLM correction")
            return test_cases

        try:
            from correct_with_llm import LLMCorrector
            print("  Applying LLM corrections (this may take 30-60 seconds)...")
            corrector = LLMCorrector(api_key=api_key, model=config.LLM_MODEL)
            corrected = corrector.correct_test_cases(
                test_cases=test_cases,
                story_id=str(story_id),
                feature_name=title,
                acceptance_criteria=acceptance_criteria,
                qa_prep=qa_prep
            )
            print(f"  LLM correction complete: {len(corrected)} test cases")
            return corrected
        except Exception as e:
            print(f"  LLM correction failed: {e}, using rule-based output")
            return test_cases

    def _save_outputs(
        self,
        story_id: int,
        title: str,
        test_cases: List[Dict],
        output_dir: str,
        skip_correction: bool
    ) -> Dict[str, str]:
        """Save generated outputs to files."""
        import os
        import json
        from src.csv_generator import CSVGenerator
        from src.objective_generator import ObjectiveGenerator

        os.makedirs(output_dir, exist_ok=True)

        # Clean title for filename
        safe_title = "".join(c if c.isalnum() or c in ' _-' else '_' for c in title)
        safe_title = safe_title.replace(' ', '_')[:50]
        suffix = "HYBRID" if not skip_correction else "RULE_BASED"

        output_files = {}

        # CSV
        csv_path = os.path.join(output_dir, f"{story_id}_{safe_title}_{suffix}_TESTS.csv")
        CSVGenerator().generate_csv(test_cases=test_cases, output_file=csv_path)
        output_files['csv'] = csv_path
        print(f"  CSV: {csv_path}")

        # Objectives
        obj_path = os.path.join(output_dir, f"{story_id}_{safe_title}_{suffix}_OBJECTIVES.txt")
        ObjectiveGenerator().generate_objectives_file(test_cases, obj_path)
        output_files['objectives'] = obj_path
        print(f"  Objectives: {obj_path}")

        # Debug JSON
        json_path = os.path.join(output_dir, f"{story_id}_{safe_title}_{suffix}_DEBUG.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'story_id': story_id,
                'title': title,
                'test_cases': test_cases,
                'mode': 'hybrid' if not skip_correction else 'rule_based'
            }, f, indent=2)
        output_files['debug_json'] = json_path
        print(f"  Debug JSON: {json_path}")

        return output_files


# =============================================================================
# WORKFLOW 2: Generate + Upload
# =============================================================================

class UploadWorkflow(IWorkflow):
    """
    Generate test cases and upload to ADO test suite.

    STRICT: Only uploads to test suite matching pattern "{story_id} : {name}"

    Steps:
    1. Find matching test suite (fail fast if not found)
    2. Generate test cases
    3. Upload to ADO with Summary field populated
    """

    @property
    def name(self) -> str:
        return "upload"

    @property
    def description(self) -> str:
        return "Generate + Upload to ADO test suite (strict {story_id} : {name} pattern)"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_id = kwargs.get('story_id')
        if not story_id:
            return "story_id is required"
        if not isinstance(story_id, int) or story_id <= 0:
            return "story_id must be a positive integer"
        return None

    def execute(self, **kwargs) -> WorkflowResult:
        import time
        from src.ado_client import ADOClient
        from src.test_suite_uploader import TestSuiteUploader
        from src.objective_generator import ObjectiveGenerator
        import config

        story_id = kwargs['story_id']
        output_dir = kwargs.get('output_dir', 'output')
        skip_correction = kwargs.get('skip_correction', False)
        dry_run = kwargs.get('dry_run', False)

        print(f"\n{'='*60}")
        print(f"WORKFLOW: Generate + Upload")
        print(f"Story ID: {story_id}")
        print(f"Mode: {'Dry Run' if dry_run else 'Live Upload'}")
        print(f"{'='*60}\n")

        # Initialize clients
        try:
            ado_client = ADOClient()
            suite_uploader = TestSuiteUploader(ado_client)
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to initialize ADO client: {e}"
            )

        # Step 1: Find matching test suite (fail fast)
        print("[1/4] Finding test suite...")
        suite_info = suite_uploader.find_test_suite_by_story_id(story_id)

        if not suite_info:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"No test suite found matching pattern '{story_id} : ...'\n"
                        f"Please create a test suite with name format: '{story_id} : {{story_name}}'"
            )

        print(f"  Found: {suite_info['name']}")
        print(f"  Suite ID: {suite_info['id']}, Plan ID: {suite_info['plan_id']}")

        # Step 2: Generate test cases (reuse GenerateWorkflow)
        print("\n[2/4] Generating test cases...")
        generate_workflow = GenerateWorkflow()
        gen_result = generate_workflow.execute(
            story_id=story_id,
            output_dir=output_dir,
            skip_correction=skip_correction
        )

        if gen_result.status == WorkflowStatus.FAILED:
            return gen_result

        test_cases = gen_result.data['test_cases']

        # Step 3: Upload to ADO
        print(f"\n[3/4] Uploading {len(test_cases)} test cases...")

        if dry_run:
            print("\n[DRY RUN - No actual uploads]\n")
            for idx, tc in enumerate(test_cases, 1):
                print(f"  [{idx}] Would create: {tc['id']}")

            return WorkflowResult(
                status=WorkflowStatus.SUCCESS,
                message=f"Dry run: Would upload {len(test_cases)} test cases",
                data={
                    'test_cases': test_cases,
                    'suite_info': suite_info,
                    'dry_run': True
                }
            )

        # Live upload
        upload_results = self._upload_test_cases(
            ado_client, suite_info, test_cases
        )

        # Step 4: Summary
        print(f"\n[4/4] Upload complete")
        print(f"  Created: {len(upload_results['created'])}")
        print(f"  Failed: {len(upload_results['failed'])}")

        status = WorkflowStatus.SUCCESS if not upload_results['failed'] else WorkflowStatus.PARTIAL

        return WorkflowResult(
            status=status,
            message=f"Uploaded {len(upload_results['created'])}/{len(test_cases)} test cases",
            data={
                'created': upload_results['created'],
                'failed': upload_results['failed'],
                'suite_info': suite_info,
                'output_files': gen_result.data.get('output_files', {})
            }
        )

    def _upload_test_cases(
        self,
        ado_client,
        suite_info: Dict,
        test_cases: List[Dict]
    ) -> Dict:
        """Upload test cases to ADO test suite."""
        import time
        import requests
        from src.objective_generator import ObjectiveGenerator
        import config

        results = {'created': [], 'failed': []}
        objective_gen = ObjectiveGenerator()

        plan_id = suite_info['plan_id']
        suite_id = suite_info['id']

        for idx, tc in enumerate(test_cases, 1):
            tc_id = tc.get('id', '')
            title = tc.get('title', '')
            steps = tc.get('steps', [])
            objective = tc.get('objective', '')

            print(f"  [{idx}/{len(test_cases)}] {tc_id}...", end=' ')

            # Create test case
            work_item_id = self._create_test_case(
                ado_client, title, steps, objective, tc_id, objective_gen
            )

            if work_item_id:
                # Add to suite
                if self._add_to_suite(ado_client, plan_id, suite_id, work_item_id):
                    results['created'].append({'id': work_item_id, 'tc_id': tc_id})
                    print(f"OK (ID: {work_item_id})")
                else:
                    results['failed'].append({'tc_id': tc_id, 'error': 'Failed to add to suite'})
                    print("Failed to add to suite")
            else:
                results['failed'].append({'tc_id': tc_id, 'error': 'Failed to create'})
                print("Failed")

            time.sleep(0.5)

        return results

    def _create_test_case(
        self,
        ado_client,
        title: str,
        steps: List[Dict],
        objective: str,
        tc_id: str,
        objective_gen
    ) -> Optional[int]:
        """Create a test case work item."""
        import requests
        import config

        url = f"{ado_client.base_url}/_apis/wit/workitems/$Test Case?api-version=7.1"

        # Build steps XML
        steps_xml = self._build_steps_xml(steps)

        # Format objective - starts directly with "Objective: Verify that..."
        formatted_objective = ""
        if objective:
            formatted_objective = objective_gen.format_objective_for_ado(objective)

        patch_doc = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.AssignedTo", "value": config.ASSIGNED_TO},
            {"op": "add", "path": "/fields/System.State", "value": config.DEFAULT_STATE},
            {"op": "add", "path": "/fields/System.AreaPath", "value": config.ADO_AREA_PATH},
            {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": steps_xml}
        ]

        if formatted_objective:
            patch_doc.append({
                "op": "add",
                "path": "/fields/System.Description",
                "value": formatted_objective
            })

        headers = ado_client.headers.copy()
        headers['Content-Type'] = 'application/json-patch+json'

        try:
            response = requests.patch(url, headers=headers, json=patch_doc)
            response.raise_for_status()
            return response.json().get('id')
        except Exception:
            return None

    def _build_steps_xml(self, steps: List[Dict]) -> str:
        """Build XML for test steps."""
        if not steps:
            return ""

        xml_parts = [f'<steps id="0" last="{len(steps)}">']

        for idx, step in enumerate(steps, start=1):
            action = step.get('action', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            expected = step.get('expected', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            xml_parts.append(f'  <step id="{idx}" type="ValidateStep">')
            xml_parts.append(f'    <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{action}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>')
            xml_parts.append(f'    <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{expected}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>')
            xml_parts.append('    <description/>')
            xml_parts.append('  </step>')

        xml_parts.append('</steps>')
        return '\n'.join(xml_parts)

    def _add_to_suite(self, ado_client, plan_id: int, suite_id: int, test_case_id: int) -> bool:
        """Add test case to test suite."""
        import requests

        url = f"{ado_client.base_url}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase?api-version=7.1"
        body = [{'workItem': {'id': test_case_id}}]

        try:
            response = requests.post(url, headers=ado_client.headers, json=body)
            return response.status_code == 200
        except Exception:
            return False


# =============================================================================
# WORKFLOW 3: Update Objectives
# =============================================================================

class UpdateObjectivesWorkflow(IWorkflow):
    """
    Update objectives for existing test cases from CSV mapping.

    Requires:
    - CSV file with ADO work item IDs (exported after upload)
    - Objectives TXT file (1:1 mapped by test case ID)
    """

    @property
    def name(self) -> str:
        return "update-objectives"

    @property
    def description(self) -> str:
        return "Update objectives for existing test cases from CSV mapping"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        csv_file = kwargs.get('csv_file')
        objectives_file = kwargs.get('objectives_file')

        if not csv_file:
            return "csv_file is required"
        if not objectives_file:
            return "objectives_file is required"

        import os
        if not os.path.exists(csv_file):
            return f"CSV file not found: {csv_file}"
        if not os.path.exists(objectives_file):
            return f"Objectives file not found: {objectives_file}"

        return None

    def execute(self, **kwargs) -> WorkflowResult:
        import re
        import csv
        import time
        from src.ado_client import ADOClient
        import config

        csv_file = kwargs['csv_file']
        objectives_file = kwargs['objectives_file']
        dry_run = kwargs.get('dry_run', False)

        print(f"\n{'='*60}")
        print(f"WORKFLOW: Update Objectives")
        print(f"CSV: {csv_file}")
        print(f"Objectives: {objectives_file}")
        print(f"Mode: {'Dry Run' if dry_run else 'Live Update'}")
        print(f"{'='*60}\n")

        # Step 1: Parse CSV for ADO IDs
        print("[1/3] Parsing CSV for ADO work item IDs...")
        ado_id_map = self._parse_csv_for_ado_ids(csv_file)
        print(f"  Found {len(ado_id_map)} test cases")

        if not ado_id_map:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="No test cases with ADO IDs found in CSV"
            )

        # Step 2: Parse objectives file
        print("\n[2/3] Parsing objectives file...")
        objectives_map = self._parse_objectives_file(objectives_file)
        print(f"  Found {len(objectives_map)} objectives")

        if not objectives_map:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="No objectives found in objectives file"
            )

        # Step 3: Update ADO
        print("\n[3/3] Updating ADO test cases...")

        if dry_run:
            print("\n[DRY RUN - No actual updates]\n")
            for tc_id, ado_id in sorted(ado_id_map.items()):
                if tc_id in objectives_map:
                    print(f"  [{tc_id}] Would update ADO ID {ado_id}")

            return WorkflowResult(
                status=WorkflowStatus.SUCCESS,
                message=f"Dry run: Would update {len(ado_id_map)} test cases",
                data={'dry_run': True}
            )

        # Live update
        client = ADOClient()
        results = {'updated': 0, 'failed': 0, 'skipped': 0}

        for tc_id, ado_id in sorted(ado_id_map.items()):
            if tc_id not in objectives_map:
                print(f"  [{tc_id}] No objective found, skipping")
                results['skipped'] += 1
                continue

            objective_html = objectives_map[tc_id]
            success = self._update_summary(client, ado_id, objective_html)

            if success:
                print(f"  [{tc_id}] Updated ADO ID {ado_id}")
                results['updated'] += 1
            else:
                print(f"  [{tc_id}] Failed to update ADO ID {ado_id}")
                results['failed'] += 1

            time.sleep(0.3)

        print(f"\n{'='*60}")
        print("UPDATE COMPLETE")
        print(f"{'='*60}")
        print(f"  Updated: {results['updated']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Skipped: {results['skipped']}")

        status = WorkflowStatus.SUCCESS if results['failed'] == 0 else WorkflowStatus.PARTIAL

        return WorkflowResult(
            status=status,
            message=f"Updated {results['updated']}/{len(ado_id_map)} test cases",
            data=results
        )

    def _parse_csv_for_ado_ids(self, csv_file: str) -> Dict[str, str]:
        """Parse CSV to extract test_case_id -> ADO work_item_id mapping."""
        import csv
        import re

        ado_id_map = {}

        with open(csv_file, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = [h.strip() for h in next(reader)]

            for row in reader:
                row_dict = dict(zip(header, row))

                work_item_id = row_dict.get('ID', '').strip().strip('"')
                work_item_type = row_dict.get('Work Item Type', '').strip().strip('"')
                title = row_dict.get('Title', '').strip().strip('"')

                if work_item_id and work_item_type == 'Test Case' and title:
                    match = re.match(r'(\d+-(AC1|\d{3})):', title)
                    if match:
                        ado_id_map[match.group(1)] = work_item_id

        return ado_id_map

    def _parse_objectives_file(self, objectives_file: str) -> Dict[str, str]:
        """Parse objectives file to extract test_case_id -> objective HTML mapping."""
        import re

        objectives_map = {}

        with open(objectives_file, 'r', encoding='utf-8') as f:
            content = f.read()

        blocks = content.strip().split('\n\n')

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 2:
                match = re.match(r'(\d+-(AC1|\d{3})):', lines[0])
                if match:
                    tc_id = match.group(1)
                    objective_html = lines[1].strip()
                    # Clean duplicate "Verify that"
                    objective_html = re.sub(
                        r'(<b>Objective:</b>\s+Verify that\s+)Verify that\s+',
                        r'\1',
                        objective_html,
                        flags=re.IGNORECASE
                    )
                    objectives_map[tc_id] = objective_html

        return objectives_map

    def _update_summary(self, client, work_item_id: str, objective_html: str) -> bool:
        """Update test case Summary field in ADO."""
        try:
            result = client.update_work_item_field(
                int(work_item_id),
                'System.Description',
                objective_html,
                operation='replace'
            )
            return result is not None
        except Exception:
            return False


# =============================================================================
# WORKFLOW ENGINE
# =============================================================================

class WorkflowEngine:
    """Orchestrates workflow execution."""

    def __init__(self):
        self._workflows: Dict[str, IWorkflow] = {}
        self._register_workflows()

    def _register_workflows(self):
        """Register all available workflows."""
        workflows = [
            GenerateWorkflow(),
            UploadWorkflow(),
            UpdateObjectivesWorkflow()
        ]
        for workflow in workflows:
            self._workflows[workflow.name] = workflow

    def get_workflow(self, name: str) -> Optional[IWorkflow]:
        """Get workflow by name."""
        return self._workflows.get(name)

    def list_workflows(self) -> List[str]:
        """List all available workflow names."""
        return list(self._workflows.keys())

    def execute(self, workflow_name: str, **kwargs) -> WorkflowResult:
        """Execute a workflow by name."""
        workflow = self.get_workflow(workflow_name)

        if not workflow:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Unknown workflow: {workflow_name}. Available: {self.list_workflows()}"
            )

        # Validate inputs
        error = workflow.validate_inputs(**kwargs)
        if error:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Validation error: {error}"
            )

        # Execute
        return workflow.execute(**kwargs)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Test Case Workflows - Generate, Upload, Update",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflows:
  generate           Generate test cases (rule-based + optional LLM correction)
  upload             Generate + Upload to ADO test suite
  update-objectives  Update objectives for existing test cases from CSV

Examples:
  python3 workflows.py generate --story-id 272889
  python3 workflows.py generate --story-id 272889 --skip-correction

  python3 workflows.py upload --story-id 272889
  python3 workflows.py upload --story-id 272889 --dry-run

  python3 workflows.py update-objectives --csv output/272889_tests.csv --objectives output/272889_objectives.txt
  python3 workflows.py update-objectives --csv output/272889_tests.csv --objectives output/272889_objectives.txt --dry-run
        """
    )

    subparsers = parser.add_subparsers(dest='workflow', help='Workflow to execute')

    # Generate workflow
    gen_parser = subparsers.add_parser('generate', help='Generate test cases')
    gen_parser.add_argument('--story-id', type=int, required=True, help='ADO Story ID')
    gen_parser.add_argument('--output-dir', default='output', help='Output directory')
    gen_parser.add_argument('--skip-correction', action='store_true', help='Skip LLM correction')

    # Upload workflow
    upload_parser = subparsers.add_parser('upload', help='Generate + Upload to ADO')
    upload_parser.add_argument('--story-id', type=int, required=True, help='ADO Story ID')
    upload_parser.add_argument('--output-dir', default='output', help='Output directory')
    upload_parser.add_argument('--skip-correction', action='store_true', help='Skip LLM correction')
    upload_parser.add_argument('--dry-run', action='store_true', help='Preview without uploading')

    # Update objectives workflow
    update_parser = subparsers.add_parser('update-objectives', help='Update objectives from CSV')
    update_parser.add_argument('--csv', dest='csv_file', required=True, help='CSV file with ADO IDs')
    update_parser.add_argument('--objectives', dest='objectives_file', required=True, help='Objectives TXT file')
    update_parser.add_argument('--dry-run', action='store_true', help='Preview without updating')

    args = parser.parse_args()

    if not args.workflow:
        parser.print_help()
        sys.exit(1)

    # Convert args to kwargs
    kwargs = vars(args).copy()
    workflow_name = kwargs.pop('workflow')

    # Execute workflow
    engine = WorkflowEngine()
    result = engine.execute(workflow_name, **kwargs)

    # Exit code
    if result.status == WorkflowStatus.FAILED:
        print(f"\nERROR: {result.message}")
        sys.exit(1)
    elif result.status == WorkflowStatus.PARTIAL:
        print(f"\nWARNING: {result.message}")
        sys.exit(0)
    else:
        print(f"\nSUCCESS: {result.message}")
        sys.exit(0)


if __name__ == '__main__':
    main()
