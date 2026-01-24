#!/usr/bin/env python3
"""
Generic Test Case Workflows - Multi-Project Support

Enhanced workflow engine supporting:
1. Multiple project configurations (YAML-based)
2. Application discovery for new projects
3. Auto test suite creation (for projects without QA Prep)
4. Backward compatibility with existing ENV QuickDraw usage

Usage:
    # Using default project (env-quickdraw)
    python3 workflows_generic.py generate --story-id 272889

    # Using specific project
    python3 workflows_generic.py generate --story-id 12345 --project mediapedia-us

    # Initialize new project
    python3 workflows_generic.py init-project --name "My App" --org "myorg" --project "MyProject"

    # Discover project from stories
    python3 workflows_generic.py discover --story-id 12345 --project-name "mediapedia-us"
"""
import argparse
import sys
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from projects import ProjectConfig, ProjectManager, ApplicationDiscovery, get_project_manager
from projects.project_config import create_new_project_config, get_env_quickdraw_config
from projects.test_suite_creator import TestSuiteCreator, QAPrepGenerator


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
    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        """Execute the workflow with project configuration."""
        pass

    @abstractmethod
    def validate_inputs(self, **kwargs) -> Optional[str]:
        """Validate inputs. Returns error message or None if valid."""
        pass


# =============================================================================
# WORKFLOW 1: Generate Test Cases (Generic)
# =============================================================================

class GenerateWorkflow(IWorkflow):
    """
    Generate test cases using project configuration.
    Uses GenericTestGenerator for project-agnostic generation.
    """

    @property
    def name(self) -> str:
        return "generate"

    @property
    def description(self) -> str:
        return "Generate test cases using project configuration"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_id = kwargs.get('story_id')
        if not story_id:
            return "story_id is required"
        if not isinstance(story_id, int) or story_id <= 0:
            return "story_id must be a positive integer"
        return None

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        import json
        from src.ado_client import ADOClient
        from src.generic_test_generator import GenericTestGenerator
        from src.csv_generator import CSVGenerator
        from src.objective_generator import ObjectiveGenerator

        story_id = kwargs['story_id']
        output_dir = kwargs.get('output_dir', config.output_dir)
        skip_correction = kwargs.get('skip_correction', False)

        print(f"\n{'='*60}")
        print(f"WORKFLOW: Generate Test Cases")
        print(f"Project: {config.project_id} ({config.application.name})")
        print(f"Story ID: {story_id}")
        print(f"Mode: {'Rule-based only' if skip_correction else 'Rule-based + LLM Correction'}")
        print(f"{'='*60}\n")

        # Step 1: Fetch story data
        print("[1/3] Fetching story data from ADO...")
        try:
            ado_client = ADOClient(
                org=config.ado.organization,
                project=config.ado.project,
                pat=config.ado.pat or os.getenv('ADO_PAT')
            )
            story_data = ado_client.fetch_story_comprehensive(story_id)
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to fetch story: {e}"
            )

        title = story_data['title']
        acceptance_criteria = story_data['acceptance_criteria']
        qa_prep = story_data.get('qa_prep', '')

        print(f"  Title: {title}")
        print(f"  Acceptance Criteria: {len(acceptance_criteria)} items")
        print(f"  QA Prep: {'Found' if qa_prep else 'Not found (will auto-generate)'}")

        if not acceptance_criteria:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="No acceptance criteria found"
            )

        # Step 2: Generate test cases using GenericTestGenerator
        print("\n[2/3] Generating test cases...")
        generator = GenericTestGenerator(config)
        test_cases = generator.generate_test_cases(
            story_data={'story_id': story_id, 'title': title},
            criteria=acceptance_criteria,
            qa_prep_content=qa_prep
        )
        print(f"  Generated {len(test_cases)} test cases")

        # Optional LLM correction
        if not skip_correction and config.llm_enabled:
            test_cases = self._apply_llm_correction(
                config, test_cases, story_id, title, acceptance_criteria, qa_prep
            )

        # Step 3: Save outputs
        print("\n[3/3] Saving outputs...")
        output_files = self._save_outputs(
            config, story_id, title, test_cases, output_dir, skip_correction
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
        config: ProjectConfig,
        test_cases: List[Dict],
        story_id: int,
        title: str,
        acceptance_criteria: List[str],
        qa_prep: str
    ) -> List[Dict]:
        """Apply LLM correction to generated test cases."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your-api-key-here":
            print("  OPENAI_API_KEY not configured, skipping LLM correction")
            return test_cases

        try:
            from correct_with_llm import LLMCorrector
            print("  Applying LLM corrections (this may take 30-60 seconds)...")
            corrector = LLMCorrector(api_key=api_key, model=config.llm_model)
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
        config: ProjectConfig,
        story_id: int,
        title: str,
        test_cases: List[Dict],
        output_dir: str,
        skip_correction: bool
    ) -> Dict[str, str]:
        """Save generated outputs to files."""
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
                'project': config.project_id,
                'application': config.application.name,
                'test_cases': test_cases,
                'mode': 'hybrid' if not skip_correction else 'rule_based'
            }, f, indent=2)
        output_files['debug_json'] = json_path
        print(f"  Debug JSON: {json_path}")

        return output_files


# =============================================================================
# WORKFLOW 2: Generate + Upload (with Auto Suite Creation)
# =============================================================================

class UploadWorkflow(IWorkflow):
    """
    Generate test cases and upload to ADO test suite.
    Supports auto-creation of test suites for projects without pre-existing ones.
    """

    @property
    def name(self) -> str:
        return "upload"

    @property
    def description(self) -> str:
        return "Generate + Upload to ADO (with optional auto suite creation)"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_id = kwargs.get('story_id')
        if not story_id:
            return "story_id is required"
        if not isinstance(story_id, int) or story_id <= 0:
            return "story_id must be a positive integer"
        return None

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        import time
        import requests
        from src.ado_client import ADOClient
        from src.test_suite_uploader import TestSuiteUploader
        from src.objective_generator import ObjectiveGenerator

        story_id = kwargs['story_id']
        output_dir = kwargs.get('output_dir', config.output_dir)
        skip_correction = kwargs.get('skip_correction', False)
        dry_run = kwargs.get('dry_run', False)
        auto_create_suite = kwargs.get('auto_create_suite', True)

        print(f"\n{'='*60}")
        print(f"WORKFLOW: Generate + Upload")
        print(f"Project: {config.project_id} ({config.application.name})")
        print(f"Story ID: {story_id}")
        print(f"Mode: {'Dry Run' if dry_run else 'Live Upload'}")
        print(f"Auto-create suite: {'Yes' if auto_create_suite else 'No'}")
        print(f"{'='*60}\n")

        # Initialize clients
        try:
            ado_client = ADOClient(
                org=config.ado.organization,
                project=config.ado.project,
                pat=config.ado.pat or os.getenv('ADO_PAT')
            )
            suite_uploader = TestSuiteUploader(ado_client)
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to initialize ADO client: {e}"
            )

        # Step 1: Find or create test suite
        print("[1/4] Finding test suite...")
        suite_info = suite_uploader.find_test_suite_by_story_id(story_id)

        if not suite_info:
            if auto_create_suite:
                print(f"  No suite found. Creating new test suite...")
                try:
                    # Fetch story title for suite name
                    story_data = ado_client.fetch_story_comprehensive(story_id)
                    story_title = story_data['title']

                    suite_creator = TestSuiteCreator(config)
                    plan_info, suite_info_obj = suite_creator.create_test_organization(
                        story_id=str(story_id),
                        story_name=story_title
                    )
                    suite_info = {
                        'id': suite_info_obj.id,
                        'name': suite_info_obj.name,
                        'plan_id': plan_info.id
                    }
                    print(f"  Created: {suite_info['name']}")
                except Exception as e:
                    return WorkflowResult(
                        status=WorkflowStatus.FAILED,
                        message=f"Failed to create test suite: {e}"
                    )
            else:
                return WorkflowResult(
                    status=WorkflowStatus.FAILED,
                    message=f"No test suite found matching pattern '{story_id} : ...'\n"
                            f"Use --auto-create-suite to create one automatically."
                )
        else:
            print(f"  Found: {suite_info['name']}")
            print(f"  Suite ID: {suite_info['id']}, Plan ID: {suite_info['plan_id']}")

        # Step 2: Generate test cases
        print("\n[2/4] Generating test cases...")
        generate_workflow = GenerateWorkflow()
        gen_result = generate_workflow.execute(
            config,
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
            config, ado_client, suite_info, test_cases
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
        config: ProjectConfig,
        ado_client,
        suite_info: Dict,
        test_cases: List[Dict]
    ) -> Dict:
        """Upload test cases to ADO test suite."""
        import time
        import requests
        from src.objective_generator import ObjectiveGenerator

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
                config, ado_client, title, steps, objective, tc_id, objective_gen
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
        config: ProjectConfig,
        ado_client,
        title: str,
        steps: List[Dict],
        objective: str,
        tc_id: str,
        objective_gen
    ) -> Optional[int]:
        """Create a test case work item."""
        import requests

        url = f"{ado_client.base_url}/_apis/wit/workitems/$Test Case?api-version=7.1"

        # Build steps XML
        steps_xml = self._build_steps_xml(steps)

        # Format objective
        formatted_objective = ""
        if objective:
            formatted_objective = objective_gen.format_objective_for_ado(objective)

        patch_doc = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.AssignedTo", "value": config.ado.assigned_to},
            {"op": "add", "path": "/fields/System.State", "value": config.ado.default_state},
            {"op": "add", "path": "/fields/System.AreaPath", "value": config.ado.area_path},
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
# WORKFLOW 3: Initialize New Project
# =============================================================================

class InitProjectWorkflow(IWorkflow):
    """
    Initialize a new project configuration.
    Creates YAML config file for the project.
    """

    @property
    def name(self) -> str:
        return "init-project"

    @property
    def description(self) -> str:
        return "Initialize a new project configuration"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        app_name = kwargs.get('app_name')
        if not app_name:
            return "app_name is required"
        return None

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        app_name = kwargs['app_name']
        project_id = kwargs.get('project_id') or app_name.lower().replace(' ', '-')
        ado_org = kwargs.get('ado_org') or os.getenv('ADO_ORG', '')
        ado_project = kwargs.get('ado_project') or os.getenv('ADO_PROJECT', '')
        area_path = kwargs.get('area_path') or os.getenv('ADO_AREA_PATH', '')
        interactive = kwargs.get('interactive', False)

        print(f"\n{'='*60}")
        print(f"WORKFLOW: Initialize New Project")
        print(f"Application: {app_name}")
        print(f"Project ID: {project_id}")
        print(f"{'='*60}\n")

        # Create discovery for interactive mode
        discovery = ApplicationDiscovery()

        if interactive:
            print("Interactive mode - answer the following questions:\n")
            responses = {}

            for question in discovery.get_discovery_questions():
                q_text = question['question']
                hint = question.get('hint', '')

                if hint:
                    print(f"{q_text}")
                    print(f"  Hint: {hint}")
                else:
                    print(f"{q_text}")

                if question.get('type') == 'multi':
                    response = input("  > ").strip()
                elif 'options' in question:
                    for i, opt in enumerate(question['options'], 1):
                        print(f"  {i}. {opt}")
                    choice = input("  > ").strip()
                    try:
                        response = question['options'][int(choice) - 1]
                    except (ValueError, IndexError):
                        response = question['options'][0]
                else:
                    response = input("  > ").strip()

                responses[question['id']] = response
                print()

            discovered = discovery.discover_interactive(app_name, responses)
        else:
            # Minimal discovery
            discovered = discovery._get_minimal_discovery(app_name)

        # Create project config
        new_config = discovery.create_project_config(
            discovery=discovered,
            project_id=project_id,
            ado_org=ado_org,
            ado_project=ado_project,
            area_path=area_path,
            assigned_to=kwargs.get('assigned_to', os.getenv('ASSIGNED_TO', '')),
            qa_prep_pattern=kwargs.get('qa_prep_pattern'),  # None for no QA Prep
        )

        # Save to file
        config_path = new_config.save()
        print(f"Configuration saved to: {config_path}")

        # Register with project manager
        manager = get_project_manager()
        manager.register_project(new_config)

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            message=f"Project '{project_id}' initialized successfully",
            data={
                'project_id': project_id,
                'config_path': config_path,
                'application_name': app_name
            }
        )


# =============================================================================
# WORKFLOW 4: Discover Project from Stories
# =============================================================================

class DiscoverWorkflow(IWorkflow):
    """
    Discover application characteristics from existing ADO stories.
    Uses story content to infer application configuration.
    """

    @property
    def name(self) -> str:
        return "discover"

    @property
    def description(self) -> str:
        return "Discover project configuration from ADO stories"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_ids = kwargs.get('story_ids')
        if not story_ids:
            return "At least one story_id is required"
        return None

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        from src.ado_client import ADOClient

        story_ids = kwargs['story_ids']
        project_name = kwargs.get('project_name', 'discovered-project')
        ado_org = kwargs.get('ado_org') or config.ado.organization
        ado_project = kwargs.get('ado_project') or config.ado.project

        print(f"\n{'='*60}")
        print(f"WORKFLOW: Discover Project from Stories")
        print(f"Stories: {story_ids}")
        print(f"Target Project Name: {project_name}")
        print(f"{'='*60}\n")

        # Fetch stories
        print("[1/3] Fetching stories from ADO...")
        try:
            ado_client = ADOClient(
                org=ado_org,
                project=ado_project,
                pat=os.getenv('ADO_PAT')
            )

            stories = []
            for story_id in story_ids:
                try:
                    story_data = ado_client.fetch_story_comprehensive(int(story_id))
                    stories.append(story_data)
                    print(f"  Fetched: {story_id} - {story_data['title'][:50]}...")
                except Exception as e:
                    print(f"  Failed to fetch {story_id}: {e}")
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to connect to ADO: {e}"
            )

        if not stories:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="No stories could be fetched"
            )

        # Discover application
        print("\n[2/3] Analyzing stories...")
        discovery = ApplicationDiscovery()
        discovered = discovery.discover_from_stories(stories)

        print(f"  Application Type: {discovered.app_type}")
        print(f"  UI Surfaces: {', '.join(discovered.main_ui_surfaces[:5])}...")
        print(f"  Platforms: {', '.join(discovered.supported_platforms)}")
        print(f"  Confidence: {discovered.confidence_score:.0%}")

        # Create and save config
        print("\n[3/3] Creating project configuration...")
        new_config = discovery.create_project_config(
            discovery=discovered,
            project_id=project_name,
            ado_org=ado_org,
            ado_project=ado_project,
            area_path=config.ado.area_path,
        )

        config_path = new_config.save()
        print(f"  Saved to: {config_path}")

        # Register
        manager = get_project_manager()
        manager.register_project(new_config)

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            message=f"Discovered and created project '{project_name}'",
            data={
                'project_id': project_name,
                'config_path': config_path,
                'discovered': {
                    'app_type': discovered.app_type,
                    'ui_surfaces': discovered.main_ui_surfaces,
                    'platforms': discovered.supported_platforms,
                    'confidence': discovered.confidence_score
                }
            }
        )


# =============================================================================
# WORKFLOW 5: List Projects
# =============================================================================

class ListProjectsWorkflow(IWorkflow):
    """List all available project configurations."""

    @property
    def name(self) -> str:
        return "list-projects"

    @property
    def description(self) -> str:
        return "List all available project configurations"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        return None

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        manager = get_project_manager()
        manager.load_from_directory()

        projects = manager.list_projects()

        print(f"\n{'='*60}")
        print("Available Projects")
        print(f"{'='*60}\n")

        for project_id in projects:
            proj_config = manager.get_project(project_id)
            active = " (active)" if project_id == config.project_id else ""
            print(f"  {project_id}{active}")
            print(f"    Application: {proj_config.application.name}")
            print(f"    ADO: {proj_config.ado.organization}/{proj_config.ado.project}")
            print()

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            message=f"Found {len(projects)} projects",
            data={'projects': projects}
        )


# =============================================================================
# WORKFLOW ENGINE
# =============================================================================

class WorkflowEngine:
    """Orchestrates workflow execution with project configuration."""

    def __init__(self):
        self._workflows: Dict[str, IWorkflow] = {}
        self._project_manager = get_project_manager()
        self._register_workflows()

    def _register_workflows(self):
        """Register all available workflows."""
        workflows = [
            GenerateWorkflow(),
            UploadWorkflow(),
            InitProjectWorkflow(),
            DiscoverWorkflow(),
            ListProjectsWorkflow(),
        ]
        for workflow in workflows:
            self._workflows[workflow.name] = workflow

    def get_workflow(self, name: str) -> Optional[IWorkflow]:
        """Get workflow by name."""
        return self._workflows.get(name)

    def list_workflows(self) -> List[str]:
        """List all available workflow names."""
        return list(self._workflows.keys())

    def execute(self, workflow_name: str, project_id: str = None, **kwargs) -> WorkflowResult:
        """Execute a workflow by name with project configuration."""
        workflow = self.get_workflow(workflow_name)

        if not workflow:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Unknown workflow: {workflow_name}. Available: {self.list_workflows()}"
            )

        # Load project configs
        self._project_manager.load_from_directory()

        # Get project configuration
        if project_id:
            config = self._project_manager.get_project(project_id)
            if not config:
                return WorkflowResult(
                    status=WorkflowStatus.FAILED,
                    message=f"Project not found: {project_id}. Run 'list-projects' to see available projects."
                )
            self._project_manager.set_active_project(project_id)
        else:
            config = self._project_manager.get_or_create_default()

        # Validate inputs
        error = workflow.validate_inputs(**kwargs)
        if error:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Validation error: {error}"
            )

        # Execute with config
        return workflow.execute(config, **kwargs)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generic Test Case Workflows - Multi-Project Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflows:
  generate        Generate test cases for a story
  upload          Generate + Upload to ADO test suite
  init-project    Initialize a new project configuration
  discover        Discover project config from ADO stories
  list-projects   List all available project configurations

Examples:
  # Using default project (env-quickdraw)
  python3 workflows_generic.py generate --story-id 272889

  # Using specific project
  python3 workflows_generic.py generate --story-id 12345 --project mediapedia-us

  # Initialize new project
  python3 workflows_generic.py init-project --name "MediaPedia" --org myorg --ado-project MediaPedia

  # Discover from stories
  python3 workflows_generic.py discover --story-ids 12345 12346 --project-name my-app

  # List projects
  python3 workflows_generic.py list-projects
        """
    )

    # Global arguments
    parser.add_argument('--project', '-p', dest='project_id', help='Project configuration to use')

    subparsers = parser.add_subparsers(dest='workflow', help='Workflow to execute')

    # Generate workflow
    gen_parser = subparsers.add_parser('generate', help='Generate test cases')
    gen_parser.add_argument('--story-id', type=int, required=True, help='ADO Story ID')
    gen_parser.add_argument('--output-dir', default=None, help='Output directory')
    gen_parser.add_argument('--skip-correction', action='store_true', help='Skip LLM correction')

    # Upload workflow
    upload_parser = subparsers.add_parser('upload', help='Generate + Upload to ADO')
    upload_parser.add_argument('--story-id', type=int, required=True, help='ADO Story ID')
    upload_parser.add_argument('--output-dir', default=None, help='Output directory')
    upload_parser.add_argument('--skip-correction', action='store_true', help='Skip LLM correction')
    upload_parser.add_argument('--dry-run', action='store_true', help='Preview without uploading')
    upload_parser.add_argument('--auto-create-suite', action='store_true', default=True,
                               help='Auto-create test suite if not found')
    upload_parser.add_argument('--no-auto-create-suite', action='store_false', dest='auto_create_suite',
                               help='Fail if test suite not found')

    # Init project workflow
    init_parser = subparsers.add_parser('init-project', help='Initialize new project')
    init_parser.add_argument('--name', dest='app_name', required=True, help='Application name')
    init_parser.add_argument('--id', dest='project_id', help='Project ID (defaults to app name)')
    init_parser.add_argument('--org', dest='ado_org', help='ADO organization')
    init_parser.add_argument('--ado-project', help='ADO project name')
    init_parser.add_argument('--area-path', help='ADO area path')
    init_parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')

    # Discover workflow
    discover_parser = subparsers.add_parser('discover', help='Discover from stories')
    discover_parser.add_argument('--story-ids', nargs='+', required=True, help='Story IDs to analyze')
    discover_parser.add_argument('--project-name', required=True, help='Name for discovered project')
    discover_parser.add_argument('--org', dest='ado_org', help='ADO organization')
    discover_parser.add_argument('--ado-project', help='ADO project name')

    # List projects workflow
    subparsers.add_parser('list-projects', help='List all projects')

    args = parser.parse_args()

    if not args.workflow:
        parser.print_help()
        sys.exit(1)

    # Convert args to kwargs
    kwargs = vars(args).copy()
    workflow_name = kwargs.pop('workflow')
    project_id = kwargs.pop('project_id', None)

    # Execute workflow
    engine = WorkflowEngine()
    result = engine.execute(workflow_name, project_id=project_id, **kwargs)

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
