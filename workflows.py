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
    python3 workflows.py generate --story-id 272973

    # Using specific project
    python3 workflows.py generate --story-id 12345 --project mediapedia-us

    # Initialize new project
    python3 workflows.py init-project --name "My App" --org "myorg" --project "MyProject"

    # Discover project from stories
    python3 workflows.py discover --story-id 12345 --project-name "mediapedia-us"
"""
import argparse
import glob
import json
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

    def _ensure_credentials(self, config: ProjectConfig):
        """Ensure all platform credentials are loaded from environment."""
        # ADO credentials
        if not config.ado.pat:
            config.ado.pat = os.getenv('ADO_PAT')

        # Jira credentials
        if config.jira and not config.jira.api_token:
            config.jira.api_token = os.getenv('JIRA_API_TOKEN')

        # TestRail credentials
        if config.testrail and not config.testrail.api_key:
            config.testrail.api_key = os.getenv('TESTRAIL_API_KEY')

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        import json
        from infrastructure import get_story_repository
        from infrastructure.export import CSVGenerator, ObjectiveGenerator
        from core.services import GenericTestGenerator

        story_id = kwargs['story_id']
        output_dir = kwargs.get('output_dir') or config.output_dir or 'output'
        skip_correction = kwargs.get('skip_correction', False)

        # Determine source platform
        source_platform = config.source_platform.upper()

        print(f"\nWorkflow: Generate Test Cases")
        print(f"Project: {config.project_id} ({config.application.name})")
        print(f"Source Platform: {source_platform}")
        print(f"Story ID: {story_id}")
        print(f"Mode: {'Rule-based only' if skip_correction else 'Rule-based + LLM Correction'}\n")

        # Step 1: Fetch story data using platform-appropriate repository
        print(f"[1/3] Fetching story data from {source_platform}...")
        try:
            # Ensure credentials are set from environment
            self._ensure_credentials(config)

            story_repo = get_story_repository(config)
            story = story_repo.get_story(story_id)
            if not story:
                return WorkflowResult(
                    status=WorkflowStatus.FAILED,
                    message=f"Failed to fetch story {story_id} from {source_platform}"
                )
            qa_prep = story_repo.get_qa_prep(story_id) or ''
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to fetch story from {source_platform}: {e}"
            )

        title = story.title
        acceptance_criteria = story.acceptance_criteria

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
        # Include description in story_data for proper entry point detection
        description = getattr(story, 'description', '') or ''
        test_cases = generator.generate_test_cases(
            story_data={'story_id': story_id, 'title': title, 'description': description},
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

        print(f"\nGeneration complete")
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
            from core.services.llm.corrector import LLMCorrector
            print("  Applying LLM corrections (this may take 30-60 seconds)...")
            corrector = LLMCorrector(
                api_key=api_key,
                model=config.llm_model,
                project_config=config  # Pass full project config for dynamic prompts
            )
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
        from infrastructure.export import CSVGenerator, ObjectiveGenerator
        from infrastructure.export.csv_generator import CSVConfig

        os.makedirs(output_dir, exist_ok=True)

        # Clean title for filename
        safe_title = "".join(c if c.isalnum() or c in ' _-' else '_' for c in title)
        safe_title = safe_title.replace(' ', '_')[:50]
        suffix = "HYBRID" if not skip_correction else "RULE_BASED"

        output_files = {}

        # CSV - pass config with area_path and assigned_to
        csv_config = CSVConfig(
            area_path=config.ado.area_path,
            assigned_to=config.ado.assigned_to,
            default_state=config.ado.default_state
        )
        csv_path = os.path.join(output_dir, f"{story_id}_{safe_title}_{suffix}_TESTS.csv")
        CSVGenerator(config=csv_config).generate_csv(test_cases=test_cases, output_file=csv_path)
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


class UploadWorkflow(IWorkflow):
    """
    Generate test cases and upload to target platform (ADO or TestRail).
    Supports auto-creation of test suites for projects without pre-existing ones.
    """

    @property
    def name(self) -> str:
        return "upload"

    @property
    def description(self) -> str:
        return "Generate + Upload to target platform (ADO/TestRail)"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_id = kwargs.get('story_id')
        if not story_id:
            return "story_id is required"
        if not isinstance(story_id, int) or story_id <= 0:
            return "story_id must be a positive integer"
        return None

    def _ensure_credentials(self, config: ProjectConfig):
        """Ensure all platform credentials are loaded from environment."""
        # ADO credentials
        if not config.ado.pat:
            config.ado.pat = os.getenv('ADO_PAT')

        # Jira credentials
        if config.jira and not config.jira.api_token:
            config.jira.api_token = os.getenv('JIRA_API_TOKEN')

        # TestRail credentials
        if config.testrail and not config.testrail.api_key:
            config.testrail.api_key = os.getenv('TESTRAIL_API_KEY')

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        import time
        import requests
        from infrastructure import get_story_repository, get_test_repositories
        from infrastructure.export import ObjectiveGenerator

        story_id = kwargs['story_id']
        output_dir = kwargs.get('output_dir') or config.output_dir or 'output'
        skip_correction = kwargs.get('skip_correction', False)
        dry_run = kwargs.get('dry_run', False)
        auto_create_suite = kwargs.get('auto_create_suite', True)

        # Determine platforms
        source_platform = config.source_platform.upper()
        target_platform = config.target_platform.upper()

        print(f"\nWorkflow: Generate + Upload")
        print(f"Project: {config.project_id} ({config.application.name})")
        print(f"Source Platform: {source_platform}")
        print(f"Target Platform: {target_platform}")
        print(f"Story ID: {story_id}")
        print(f"Mode: {'Dry Run' if dry_run else 'Live Upload'}")
        print(f"Auto-create suite: {'Yes' if auto_create_suite else 'No'}\n")

        # Initialize repositories using factory
        try:
            self._ensure_credentials(config)
            story_repo = get_story_repository(config)
            suite_repo, case_repo = get_test_repositories(config)
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to initialize {target_platform} client: {e}"
            )

        # Step 1: Find or create test suite/section
        print(f"[1/4] Finding test suite in {target_platform}...")
        suite_info = suite_repo.find_suite_by_story_id(story_id)

        if not suite_info:
            if auto_create_suite:
                print(f"  No suite found. Creating new test suite...")
                try:
                    # Fetch story title for suite name
                    story = story_repo.get_story(story_id)
                    story_title = story.title if story else f"Story {story_id}"
                    suite_name = f"{story_id} : {story_title}"

                    # For ADO, use TestSuiteCreator; for TestRail, use suite_repo directly
                    if target_platform == 'ADO':
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
                    else:
                        # TestRail: create section directly
                        suite_info = suite_repo.create_suite(
                            plan_id=config.testrail.suite_id if config.testrail else 0,
                            suite_name=suite_name,
                            story_id=story_id
                        )

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
            print(f"  Suite ID: {suite_info['id']}, Plan ID: {suite_info.get('plan_id', 'N/A')}")

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

        # Live upload using repository
        upload_results = self._upload_test_cases(
            config, case_repo, suite_repo, suite_info, test_cases, target_platform
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
        case_repo,
        suite_repo,
        suite_info: Dict,
        test_cases: List[Dict],
        target_platform: str
    ) -> Dict:
        """Upload test cases to target platform (ADO or TestRail)."""
        import time
        from infrastructure.export import ObjectiveGenerator

        results = {'created': [], 'failed': []}
        objective_gen = ObjectiveGenerator()

        plan_id = suite_info.get('plan_id', 0)
        suite_id = suite_info['id']

        for idx, tc in enumerate(test_cases, 1):
            tc_id = tc.get('id', '')
            title = tc.get('title', '')
            steps = tc.get('steps', [])
            objective = tc.get('objective', '')

            print(f"  [{idx}/{len(test_cases)}] {tc_id}...", end=' ')

            try:
                # Format objective for ADO if needed
                formatted_objective = objective
                if target_platform == 'ADO' and objective:
                    formatted_objective = objective_gen.format_objective_for_ado(objective)

                # Create test case using the repository
                work_item_id = case_repo.create_test_case(
                    title=title,
                    steps=steps,
                    objective=formatted_objective,
                    section_id=suite_id  # For TestRail
                )

                if work_item_id:
                    # Add to suite (for ADO; TestRail handles this automatically)
                    if suite_repo.add_test_case_to_suite(plan_id, suite_id, work_item_id):
                        results['created'].append({'id': work_item_id, 'tc_id': tc_id})
                        print(f"OK (ID: {work_item_id})")
                    else:
                        results['failed'].append({'tc_id': tc_id, 'error': 'Failed to add to suite'})
                        print("Failed to add to suite")
                else:
                    results['failed'].append({'tc_id': tc_id, 'error': 'Failed to create'})
                    print("Failed")
            except Exception as e:
                results['failed'].append({'tc_id': tc_id, 'error': str(e)})
                print(f"Failed: {e}")

            time.sleep(0.5)

        return results

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

        print(f"\nWorkflow: Initialize New Project")
        print(f"Application: {app_name}")
        print(f"Project ID: {project_id}\n")

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
        return "Discover project configuration from stories"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_ids = kwargs.get('story_ids')
        if not story_ids:
            return "At least one story_id is required"
        return None

    def _ensure_credentials(self, config: ProjectConfig):
        """Ensure all platform credentials are loaded from environment."""
        # ADO credentials
        if not config.ado.pat:
            config.ado.pat = os.getenv('ADO_PAT')

        # Jira credentials
        if config.jira and not config.jira.api_token:
            config.jira.api_token = os.getenv('JIRA_API_TOKEN')

        # TestRail credentials
        if config.testrail and not config.testrail.api_key:
            config.testrail.api_key = os.getenv('TESTRAIL_API_KEY')

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        from infrastructure import get_story_repository

        story_ids = kwargs['story_ids']
        project_name = kwargs.get('project_name', 'discovered-project')
        ado_org = kwargs.get('ado_org') or config.ado.organization
        ado_project = kwargs.get('ado_project') or config.ado.project

        source_platform = config.source_platform.upper()

        print(f"\nWorkflow: Discover Project from Stories")
        print(f"Source Platform: {source_platform}")
        print(f"Stories: {story_ids}")
        print(f"Target Project Name: {project_name}\n")

        # Fetch stories using platform-appropriate repository
        print(f"[1/3] Fetching stories from {source_platform}...")
        try:
            self._ensure_credentials(config)
            story_repo = get_story_repository(config)

            stories = []
            for story_id in story_ids:
                try:
                    story = story_repo.get_story(int(story_id))
                    if story:
                        # Convert to dict format expected by discovery
                        story_data = {
                            'title': story.title,
                            'description': story.description,
                            'acceptance_criteria': story.acceptance_criteria
                        }
                        stories.append(story_data)
                        print(f"  Fetched: {story_id} - {story.title[:50]}...")
                except Exception as e:
                    print(f"  Failed to fetch {story_id}: {e}")
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to connect to {source_platform}: {e}"
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

        print(f"\nAvailable Projects\n")

        for project_id in projects:
            proj_config = manager.get_project(project_id)
            active = " (active)" if project_id == config.project_id else ""
            print(f"  {project_id}{active}")
            print(f"    Application: {proj_config.application.name}")
            print(f"    Source: {proj_config.source_platform}")
            print(f"    Target: {proj_config.target_platform}")
            print()

        return WorkflowResult(
            status=WorkflowStatus.SUCCESS,
            message=f"Found {len(projects)} projects",
            data={'projects': projects}
        )


class UploadExistingWorkflow(IWorkflow):
    """
    Upload existing test cases from files to target platform (ADO or TestRail).
    Skips generation and uses previously generated test cases.
    """

    @property
    def name(self) -> str:
        return "upload-existing"

    @property
    def description(self) -> str:
        return "Upload existing test cases to target platform (skip generation)"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_id = kwargs.get('story_id')
        if not story_id:
            return "story_id is required"
        if not isinstance(story_id, int) or story_id <= 0:
            return "story_id must be a positive integer"
        return None

    def _find_existing_files(self, story_id: int, output_dir: str) -> Dict[str, str]:
        """Find existing test case files for a story."""
        found_files = {}

        if not os.path.exists(output_dir):
            return found_files

        patterns = {
            'json': f"{output_dir}/{story_id}_*DEBUG.json",
            'csv': f"{output_dir}/{story_id}_*TESTS.csv",
            'objectives': f"{output_dir}/{story_id}_*OBJECTIVES.txt"
        }

        for file_type, pattern in patterns.items():
            matches = glob.glob(pattern)
            if matches:
                found_files[file_type] = max(matches, key=os.path.getmtime)

        return found_files

    def _load_test_cases(self, json_file: str) -> Optional[List[Dict]]:
        """Load test cases from JSON file."""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('test_cases', [])
        except Exception as e:
            print(f"  Failed to load test cases: {e}")
            return None

    def _ensure_credentials(self, config: ProjectConfig):
        """Ensure all platform credentials are loaded from environment."""
        # ADO credentials
        if not config.ado.pat:
            config.ado.pat = os.getenv('ADO_PAT')

        # Jira credentials
        if config.jira and not config.jira.api_token:
            config.jira.api_token = os.getenv('JIRA_API_TOKEN')

        # TestRail credentials
        if config.testrail and not config.testrail.api_key:
            config.testrail.api_key = os.getenv('TESTRAIL_API_KEY')

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        from infrastructure import get_test_repositories

        story_id = kwargs['story_id']
        output_dir = kwargs.get('output_dir') or config.output_dir or 'output'
        target_platform = config.target_platform.upper()

        print(f"\nWorkflow: Upload Existing Test Cases")
        print(f"Project: {config.project_id} ({config.application.name})")
        print(f"Target Platform: {target_platform}")
        print(f"Story ID: {story_id}\n")

        # Step 1: Find existing files
        print("[1/3] Looking for existing test files...")
        existing_files = self._find_existing_files(story_id, output_dir)

        if not existing_files.get('json'):
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"No existing test files found for story {story_id} in {output_dir}"
            )

        print(f"  Found: {existing_files['json']}")

        # Step 2: Load test cases
        print("\n[2/3] Loading test cases...")
        test_cases = self._load_test_cases(existing_files['json'])

        if not test_cases:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="Failed to load test cases from file"
            )

        print(f"  Loaded {len(test_cases)} test cases")

        # Step 3: Upload using platform-appropriate repository
        print(f"\n[3/3] Uploading to {target_platform}...")

        # Ensure credentials are set
        self._ensure_credentials(config)

        try:
            suite_repo, case_repo = get_test_repositories(config)
        except Exception as e:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Failed to initialize {target_platform} client: {e}"
            )

        # Find test suite
        suite_info = suite_repo.find_suite_by_story_id(story_id)
        if not suite_info:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"No test suite found for story {story_id}. Create one first or use 'upload' workflow."
            )

        print(f"  Found suite: {suite_info['name']}")

        # Upload using UploadWorkflow's method
        upload_workflow = UploadWorkflow()
        upload_results = upload_workflow._upload_test_cases(
            config, case_repo, suite_repo, suite_info, test_cases, target_platform
        )

        print(f"\nUpload complete")
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
                'source_file': existing_files['json']
            }
        )


class UpdateFromFeedbackWorkflow(IWorkflow):
    """
    Update existing test cases in ADO based on reviewer/customer feedback.

    Takes a CSV file exported from ADO and a text file with feedback,
    then applies ONLY the specific fixes mentioned in the feedback.

    Usage:
        python3 workflows.py update-from-feedback \
            --csv "exported_tests.csv" \
            --feedback "review_feedback.txt"
    """

    @property
    def name(self) -> str:
        return "update-from-feedback"

    @property
    def description(self) -> str:
        return "Update test cases in ADO based on reviewer feedback"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        csv_file = kwargs.get('csv_file')
        feedback_file = kwargs.get('feedback_file')

        if not csv_file:
            return "csv_file is required (--csv)"
        if not feedback_file:
            return "feedback_file is required (--feedback)"
        if not os.path.exists(csv_file):
            return f"CSV file not found: {csv_file}"
        if not os.path.exists(feedback_file):
            return f"Feedback file not found: {feedback_file}"
        return None

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        import csv
        import re

        csv_file = kwargs['csv_file']
        feedback_file = kwargs['feedback_file']
        dry_run = kwargs.get('dry_run', False)
        use_llm = kwargs.get('use_llm', False)
        output_file = kwargs.get('output_file', None)
        target_platform = config.target_platform.upper()

        print(f"\nWorkflow: Update Test Cases from Reviewer Feedback")
        print(f"Project: {config.project_id}")
        print(f"Target Platform: {target_platform}")
        print(f"CSV File: {csv_file}")
        print(f"Feedback File: {feedback_file}")
        print(f"Mode: {'Dry Run' if dry_run else 'Live Update'}")
        print(f"LLM Assistance: {'Enabled' if use_llm else 'Disabled (manual parsing)'}\n")

        # Step 1: Parse test cases from CSV
        print("[1/4] Parsing test cases from CSV...")
        test_cases = self._parse_csv(csv_file)
        print(f"  Found {len(test_cases)} test cases")

        # Step 2: Parse feedback
        print("\n[2/4] Parsing reviewer feedback...")
        feedback = self._parse_feedback(feedback_file)
        print(f"  General feedback items: {len(feedback['general'])}")
        print(f"  Test-specific feedback: {list(feedback['specific'].keys())}")

        # Step 3: Generate fixes
        print("\n[3/4] Generating fixes...")
        if use_llm:
            fixes = self._generate_fixes_with_llm(test_cases, feedback)
        else:
            fixes = self._generate_fixes_manual(test_cases, feedback)

        tests_to_update = [tc_id for tc_id in fixes if fixes[tc_id].get('has_changes')]
        print(f"  Tests with changes: {len(tests_to_update)}")

        # Preview changes with full detail
        self._preview_changes(test_cases, fixes, output_file)

        if dry_run:
            print("\n[DRY RUN] No changes made to ADO.")
            return WorkflowResult(
                status=WorkflowStatus.SUCCESS,
                message=f"Dry run: Would update {len(tests_to_update)} test cases",
                data={'fixes': fixes, 'dry_run': True}
            )

        # Step 4: Update target platform
        print(f"\n[4/4] Updating {target_platform}...")

        # Currently only ADO update is supported
        if target_platform != 'ADO':
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"Update from feedback not yet supported for {target_platform}"
            )

        if not config.ado.pat:
            config.ado.pat = os.getenv('ADO_PAT')

        if not config.ado.pat:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="ADO_PAT environment variable not set"
            )

        from infrastructure.ado import ADOHttpClient
        client = ADOHttpClient(
            organization=config.ado.organization,
            project=config.ado.project,
            pat=config.ado.pat
        )

        success, failed = self._update_ado(client, test_cases, fixes)

        print(f"\nUpdate complete")
        print(f"  Success: {success}")
        print(f"  Failed: {failed}")

        status = WorkflowStatus.SUCCESS if failed == 0 else WorkflowStatus.PARTIAL
        return WorkflowResult(
            status=status,
            message=f"Updated {success}/{success + failed} test cases",
            data={'success': success, 'failed': failed, 'fixes': fixes}
        )

    def _parse_csv(self, csv_file: str) -> Dict[int, Dict]:
        """Parse test cases from ADO-exported CSV."""
        import csv

        test_cases = {}
        current_id = None

        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('ID') and row['ID'].strip():
                    current_id = int(row['ID'])
                    test_cases[current_id] = {
                        'title': row.get('Title', ''),
                        'state': row.get('State', 'Design'),
                        'area_path': row.get('Area Path', ''),
                        'assigned_to': row.get('Assigned To', ''),
                        'steps': []
                    }
                if current_id and row.get('Test Step'):
                    test_cases[current_id]['steps'].append({
                        'step_num': int(row['Test Step']),
                        'action': row.get('Step Action', ''),
                        'expected': row.get('Step Expected', '')
                    })
        return test_cases

    def _parse_feedback(self, feedback_file: str) -> Dict[str, Any]:
        """Parse reviewer feedback from text file."""
        import re

        with open(feedback_file, 'r', encoding='utf-8') as f:
            content = f.read()

        feedback = {
            'general': [],
            'specific': {},
            'raw': content
        }

        lines = content.split('\n')
        current_test_id = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check for test-specific section (e.g., "AC1:", "015:", "Test 278139:")
            test_match = re.match(
                r'^(?:Test\s*)?(?:Case\s*)?(?:#)?(\d+|AC\d+)\s*[:]\s*(.*)?',
                stripped, re.IGNORECASE
            )
            if test_match:
                current_test_id = test_match.group(1)
                feedback['specific'][current_test_id] = []
                remaining = test_match.group(2)
                if remaining and remaining.strip():
                    feedback['specific'][current_test_id].append(remaining.strip())
                continue

            # Add to appropriate section
            if current_test_id:
                feedback['specific'][current_test_id].append(stripped)
            else:
                feedback['general'].append(stripped)

        return feedback

    def _generate_fixes_manual(self, test_cases: Dict[int, Dict], feedback: Dict) -> Dict[int, Dict]:
        """
        Generate fixes by parsing feedback patterns manually.
        Applies ONLY the specific changes mentioned in feedback.
        """
        import re

        fixes = {}

        # Map test IDs in feedback to actual ADO IDs
        id_mapping = self._map_feedback_ids_to_ado_ids(test_cases, feedback)

        for tc_id, tc_data in test_cases.items():
            fix = {
                'title': tc_data['title'],  # Keep original title
                'state': 'Ready',  # Update state per feedback
                'steps': [{'action': s['action'], 'expected': s['expected']} for s in tc_data['steps']],
                'has_changes': False,
                'changes_made': []
            }

            # Check if this test has specific feedback
            feedback_id = id_mapping.get(tc_id)
            if feedback_id and feedback_id in feedback['specific']:
                specific_feedback = feedback['specific'][feedback_id]
                fix = self._apply_specific_feedback(fix, specific_feedback, tc_data)

            # Apply general feedback patterns
            fix = self._apply_general_feedback(fix, feedback['general'])

            # Check if state changed
            if tc_data['state'] != fix['state']:
                fix['has_changes'] = True
                fix['changes_made'].append(f"State: {tc_data['state']} -> {fix['state']}")

            fixes[tc_id] = fix

        return fixes

    def _map_feedback_ids_to_ado_ids(self, test_cases: Dict, feedback: Dict) -> Dict[int, str]:
        """Map ADO test case IDs to feedback identifiers (AC1, 015, etc.)."""
        import re

        mapping = {}

        for tc_id, tc_data in test_cases.items():
            title = tc_data['title']

            # Extract test ID from title (e.g., "272972-AC1:" or "272972-015:")
            match = re.search(r'-(\d{3}|AC\d+)[:\s]', title)
            if match:
                test_num = match.group(1)
                mapping[tc_id] = test_num

        return mapping

    def _apply_specific_feedback(self, fix: Dict, specific_feedback: List[str], original: Dict) -> Dict:
        """Apply test-specific feedback."""
        import re

        feedback_text = ' '.join(specific_feedback).lower()

        for line in specific_feedback:
            line_lower = line.lower()

            # Pattern: "Step X action should be expected result for step Y"
            merge_match = re.search(
                r'step\s*(\d+)\s*(?:action)?\s*should\s*be\s*(?:the\s*)?expected\s*(?:result)?\s*(?:for|of)\s*step\s*(\d+)',
                line_lower
            )
            if merge_match:
                source_step = int(merge_match.group(1)) - 1  # 0-indexed
                target_step = int(merge_match.group(2)) - 1

                if 0 <= source_step < len(fix['steps']) and 0 <= target_step < len(fix['steps']):
                    # Move source step's expected (or action content) to target step's expected
                    source_expected = fix['steps'][source_step]['expected']
                    if not source_expected:
                        # If source has no expected, use its action as the expected
                        source_expected = fix['steps'][source_step]['action']

                    fix['steps'][target_step]['expected'] = source_expected
                    fix['steps'].pop(source_step)
                    fix['has_changes'] = True
                    fix['changes_made'].append(f"Merged step {source_step + 1} into step {target_step + 1}")

            # Pattern: "Step X should be expected result of step Y" (without "action")
            merge_match2 = re.search(
                r'step\s*(\d+)\s*should\s*be\s*expected\s*(?:result)?\s*of\s*step\s*(\d+)',
                line_lower
            )
            if merge_match2 and not merge_match:
                source_step = int(merge_match2.group(1)) - 1
                target_step = int(merge_match2.group(2)) - 1

                if 0 <= source_step < len(fix['steps']) and 0 <= target_step < len(fix['steps']):
                    # Add expected result to target step based on the action pattern
                    target_action = fix['steps'][target_step]['action'].lower()

                    if 'create new drawing' in target_action or 'select create new' in target_action:
                        fix['steps'][target_step]['expected'] = 'Workspace is displayed and Home Screen is not visible.'
                    elif 'close project' in target_action:
                        fix['steps'][target_step]['expected'] = 'Home Screen is displayed.'
                    elif 'save' in target_action:
                        fix['steps'][target_step]['expected'] = 'File is saved successfully.'

                    fix['has_changes'] = True
                    fix['changes_made'].append(f"Added expected result to step {target_step + 1}")

        return fix

    def _apply_general_feedback(self, fix: Dict, general_feedback: List[str]) -> Dict:
        """Apply general feedback patterns to all tests."""
        feedback_text = ' '.join(general_feedback).lower()

        # Check for "ready state" feedback
        if 'ready state' in feedback_text or 'should be in ready' in feedback_text:
            fix['state'] = 'Ready'

        return fix

    def _generate_fixes_with_llm(self, test_cases: Dict, feedback: Dict) -> Dict:
        """Use LLM to interpret feedback and generate fixes."""
        import json
        import re

        try:
            from openai import OpenAI
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                print("  OPENAI_API_KEY not set, falling back to manual parsing")
                return self._generate_fixes_manual(test_cases, feedback)

            client = OpenAI(api_key=api_key)
        except ImportError:
            print("  OpenAI package not installed, falling back to manual parsing")
            return self._generate_fixes_manual(test_cases, feedback)

        # Build test cases for prompt
        tc_list = []
        for tc_id, tc_data in test_cases.items():
            tc_list.append({
                'id': tc_id,
                'title': tc_data['title'],
                'state': tc_data['state'],
                'steps': [{'step': i+1, 'action': s['action'], 'expected': s['expected']}
                         for i, s in enumerate(tc_data['steps'])]
            })

        prompt = f"""Apply ONLY the specific fixes from the reviewer feedback to these test cases.

FEEDBACK:
{feedback['raw']}

TEST CASES:
{json.dumps(tc_list, indent=2)}

RULES:
1. Keep original titles EXACTLY as they are
2. Apply ONLY the specific fixes mentioned in feedback
3. If feedback says "Step X should be expected result of step Y", merge step X into step Y's expected result
4. Change state to "Ready" if mentioned in feedback
5. Do NOT change tests that have no specific feedback

OUTPUT: JSON object where keys are test IDs (as strings), values have:
- title: SAME as original
- state: "Ready" or original
- steps: array of {{action, expected}}
- has_changes: true/false

Return ONLY valid JSON."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Output only valid JSON. Apply only specific fixes mentioned."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=16000
        )

        result = response.choices[0].message.content.strip()
        if result.startswith("```"):
            result = re.sub(r'^```(?:json)?\n?', '', result)
            result = re.sub(r'\n?```$', '', result)

        fixes = json.loads(result)
        return {int(k): v for k, v in fixes.items()}

    def _preview_changes(self, test_cases: Dict, fixes: Dict, output_file: str = None):
        """Preview the changes that will be made with full detail."""
        print("\nDETAILED CHANGES TO BE APPLIED\n")

        tests_with_changes = [(tc_id, fix) for tc_id, fix in fixes.items() if fix.get('has_changes')]

        if not tests_with_changes:
            print("\nNo changes detected.")
            return

        for tc_id, fix in tests_with_changes:
            original = test_cases[tc_id]
            print(f"\nTest Case ID: {tc_id}")
            print(f"Title: {fix['title']}")
            print(f"State: {original['state']} → {fix['state']}")
            print(f"Steps: {len(original['steps'])} → {len(fix['steps'])}")

            if fix.get('changes_made'):
                print("\nChanges Applied:")
                for change in fix['changes_made']:
                    print(f"  • {change}")

            print("\n--- UPDATED STEPS (will be sent to ADO) ---")
            for i, step in enumerate(fix['steps'], 1):
                print(f"\n  Step {i}:")
                print(f"    Action:   {step['action']}")
                print(f"    Expected: {step['expected'] or '(empty)'}")

        # Output JSON - always save to output folder
        import json

        # Determine output file path
        if output_file:
            # If user specified path, use it
            final_output_path = output_file
        else:
            # Default to output folder with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            final_output_path = os.path.join(output_dir, f"fixes_{timestamp}.json")

        output_data = {}
        for tc_id, fix in tests_with_changes:
            output_data[str(tc_id)] = {
                'title': fix['title'],
                'state': fix['state'],
                'steps': fix['steps']
            }
        with open(final_output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nFixes saved to: {final_output_path}")
        print(f"Summary: {len(tests_with_changes)} test case(s) will be updated")

    def _update_ado(self, client, test_cases: Dict, fixes: Dict) -> tuple:
        """Update test cases in ADO."""
        success = 0
        failed = 0

        for tc_id, fix in fixes.items():
            if not fix.get('has_changes'):
                continue

            print(f"  Updating {tc_id}...", end=" ")

            try:
                patch_doc = [
                    {"op": "replace", "path": "/fields/System.Title", "value": fix['title']},
                    {"op": "replace", "path": "/fields/System.State", "value": fix['state']},
                    {"op": "replace", "path": "/fields/Microsoft.VSTS.TCM.Steps",
                     "value": self._build_steps_xml(fix['steps'])}
                ]

                client.patch(f"_apis/wit/workitems/{tc_id}", data=patch_doc)
                print("OK")
                success += 1
            except Exception as e:
                print(f"FAILED - {e}")
                failed += 1

        return success, failed

    def _build_steps_xml(self, steps: List[Dict]) -> str:
        """Build XML for test steps."""
        if not steps:
            return ""

        def escape_xml(text):
            return (text.replace('&', '&amp;').replace('<', '&lt;')
                    .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;'))

        xml_parts = [f'<steps id="0" last="{len(steps)}">']
        for idx, step in enumerate(steps, start=1):
            action = escape_xml(step.get('action', ''))
            expected = escape_xml(step.get('expected', ''))
            xml_parts.append(f'  <step id="{idx}" type="ValidateStep">')
            xml_parts.append(f'    <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{action}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>')
            xml_parts.append(f'    <parameterizedString isformatted="true">&lt;DIV&gt;&lt;P&gt;{expected}&lt;/P&gt;&lt;/DIV&gt;</parameterizedString>')
            xml_parts.append('    <description/>')
            xml_parts.append('  </step>')
        xml_parts.append('</steps>')
        return '\n'.join(xml_parts)


class UpdateObjectivesWorkflow(IWorkflow):
    """
    Update only the objectives/summary field for existing test cases in ADO.

    Can fetch test case IDs directly from ADO by story ID, or from an exported CSV file.

    Usage:
        # Fetch test cases from ADO by story ID (preferred)
        python3 workflows.py update-objectives --story-id 272265
        python3 workflows.py update-objectives --story-id 272265 --dry-run

        # Or use CSV export (legacy)
        python3 workflows.py update-objectives --csv "exported.csv" --story-id 272265
    """

    @property
    def name(self) -> str:
        return "update-objectives"

    @property
    def description(self) -> str:
        return "Update objectives/summary field for existing test cases in ADO"

    def validate_inputs(self, **kwargs) -> Optional[str]:
        story_id = kwargs.get('story_id')
        csv_file = kwargs.get('csv_file')

        if not story_id:
            return "story_id is required"
        if not isinstance(story_id, int) or story_id <= 0:
            return "story_id must be a positive integer"
        # CSV is now optional - if not provided, will fetch from ADO
        if csv_file and not os.path.exists(csv_file):
            return f"CSV file not found: {csv_file}"
        return None

    def _find_existing_files(self, story_id: int, output_dir: str) -> Dict[str, str]:
        """Find existing test case files for a story."""
        found_files = {}

        if not os.path.exists(output_dir):
            return found_files

        patterns = {
            'json': f"{output_dir}/{story_id}_*DEBUG.json",
            'objectives': f"{output_dir}/{story_id}_*OBJECTIVES.txt"
        }

        for file_type, pattern in patterns.items():
            matches = glob.glob(pattern)
            if matches:
                found_files[file_type] = max(matches, key=os.path.getmtime)

        return found_files

    def _load_test_cases(self, json_file: str) -> Optional[List[Dict]]:
        """Load test cases from JSON file."""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('test_cases', [])
        except Exception as e:
            print(f"  Failed to load test cases: {e}")
            return None

    def _build_objectives_map(self, test_cases: List[Dict]) -> Dict[str, str]:
        """Build a map of test case ID pattern to formatted objective."""
        from infrastructure.export import ObjectiveGenerator

        obj_gen = ObjectiveGenerator()
        objectives_map = {}

        for tc in test_cases:
            tc_id = tc.get('id', '')  # e.g., "272265-AC1" or "272265-005"
            objective = tc.get('objective', '')

            if tc_id and objective:
                # Format objective for ADO
                formatted = obj_gen.format_objective_for_ado(objective)
                objectives_map[tc_id] = formatted
            elif tc_id:
                # Generate objective from title if not present
                title = tc.get('title', '')
                if title:
                    generated_obj = obj_gen.create_objective_from_title(title)
                    formatted = obj_gen.format_objective_for_ado(generated_obj)
                    objectives_map[tc_id] = formatted

        return objectives_map

    def _parse_ado_csv(self, csv_file: str) -> List[Dict]:
        """
        Parse ADO-exported CSV to extract work item IDs and titles.

        Returns list of dicts with 'ado_id' and 'title' keys.
        """
        import csv

        test_cases = []

        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only process rows with an ID (test case header rows)
                if row.get('ID') and row['ID'].strip():
                    test_cases.append({
                        'ado_id': int(row['ID']),
                        'title': row.get('Title', '')
                    })

        return test_cases

    def _fetch_test_cases_from_ado(self, config: ProjectConfig, story_id: int) -> List[Dict]:
        """
        Fetch test cases from ADO by finding the test suite for the story.

        Returns list of dicts with 'ado_id' and 'title' keys.
        """
        from infrastructure import get_test_repositories

        self._ensure_credentials(config)

        try:
            suite_repo, _ = get_test_repositories(config)

            # Find the test suite for this story
            suite_info = suite_repo.find_suite_by_story_id(story_id)
            if not suite_info:
                print(f"  No test suite found for story {story_id}")
                return []

            print(f"  Found suite: {suite_info['name']}")
            print(f"  Suite ID: {suite_info['id']}, Plan ID: {suite_info['plan_id']}")

            # Get test cases from the suite
            test_cases = suite_repo.get_test_cases_in_suite(
                suite_info['plan_id'],
                suite_info['id']
            )

            return test_cases
        except Exception as e:
            print(f"  Error fetching test cases from ADO: {e}")
            return []

    def _extract_test_id_from_title(self, title: str) -> Optional[str]:
        """Extract test ID (e.g., '272265-AC1' or '272265-005') from title."""
        import re
        match = re.match(r'^(\d+-(?:AC\d+|\d+))', title)
        if match:
            return match.group(1)
        return None

    def _ensure_credentials(self, config: ProjectConfig):
        """Ensure ADO credentials are loaded from environment."""
        if not config.ado.pat:
            config.ado.pat = os.getenv('ADO_PAT')

    def execute(self, config: ProjectConfig, **kwargs) -> WorkflowResult:
        story_id = kwargs['story_id']
        csv_file = kwargs.get('csv_file')
        output_dir = kwargs.get('output_dir') or config.output_dir or 'output'
        dry_run = kwargs.get('dry_run', False)

        print(f"\nWorkflow: Update Objectives in ADO")
        print(f"Project: {config.project_id} ({config.application.name})")
        print(f"Story ID: {story_id}")
        print(f"Source: {'CSV File' if csv_file else 'ADO (fetch by story ID)'}")
        if csv_file:
            print(f"CSV File: {csv_file}")
        print(f"Mode: {'Dry Run' if dry_run else 'Live Update'}\n")

        # Step 1: Get ADO test cases (from CSV or directly from ADO)
        if csv_file:
            print("[1/4] Parsing ADO CSV file...")
            ado_test_cases = self._parse_ado_csv(csv_file)
            source_desc = f"CSV file: {csv_file}"
        else:
            print("[1/4] Fetching test cases from ADO...")
            ado_test_cases = self._fetch_test_cases_from_ado(config, story_id)
            source_desc = f"ADO test suite for story {story_id}"

        if not ado_test_cases:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"No test cases found in {source_desc}"
            )

        print(f"  Found {len(ado_test_cases)} test cases")
        for tc in ado_test_cases:
            tc_id = self._extract_test_id_from_title(tc['title'])
            print(f"    [{tc['ado_id']}] {tc_id or tc['title'][:40]}")

        # Step 2: Find and load local objectives
        print("\n[2/4] Loading objectives from local files...")
        existing_files = self._find_existing_files(story_id, output_dir)

        if not existing_files.get('json'):
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message=f"No local test files found for story {story_id} in {output_dir}. Run 'generate' first."
            )

        print(f"  Found: {existing_files['json']}")

        test_cases = self._load_test_cases(existing_files['json'])
        if not test_cases:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="Failed to load test cases from local file"
            )

        objectives_map = self._build_objectives_map(test_cases)
        print(f"  Loaded {len(objectives_map)} objectives")

        # Step 3: Match ADO IDs with objectives
        print("\n[3/4] Matching test cases with objectives...")
        matches = []
        for tc in ado_test_cases:
            tc_id = self._extract_test_id_from_title(tc['title'])
            if tc_id and tc_id in objectives_map:
                matches.append({
                    'ado_id': tc['ado_id'],
                    'tc_id': tc_id,
                    'objective': objectives_map[tc_id]
                })
                print(f"    [{tc['ado_id']}] {tc_id} -> Matched")
            else:
                print(f"    [{tc['ado_id']}] {tc_id or 'Unknown'} -> No match")

        if not matches:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="No matching objectives found for test cases"
            )

        print(f"  Matched {len(matches)}/{len(ado_test_cases)} test cases")

        # Step 4: Update objectives in ADO
        print(f"\n[4/4] Updating objectives in ADO...")

        if dry_run:
            print("\n[DRY RUN - No changes made]\n")
            for m in matches:
                preview = m['objective'][:80] + "..." if len(m['objective']) > 80 else m['objective']
                print(f"  [{m['ado_id']}] {m['tc_id']}")
                print(f"    Would update to: {preview}\n")

            return WorkflowResult(
                status=WorkflowStatus.SUCCESS,
                message=f"Dry run: Would update {len(matches)} objectives",
                data={'dry_run': True, 'matches': len(matches)}
            )

        # Live update
        self._ensure_credentials(config)

        if not config.ado.pat:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                message="ADO_PAT environment variable not set"
            )

        from infrastructure.ado import ADOHttpClient
        client = ADOHttpClient(
            organization=config.ado.organization,
            project=config.ado.project,
            pat=config.ado.pat
        )

        success = 0
        failed = 0

        for m in matches:
            print(f"  [{m['ado_id']}] {m['tc_id']}...", end=" ")

            try:
                patch_doc = [
                    {
                        "op": "replace",
                        "path": "/fields/System.Description",
                        "value": m['objective']
                    }
                ]

                client.patch(f"_apis/wit/workitems/{m['ado_id']}?api-version=7.1", data=patch_doc)
                print("OK")
                success += 1
            except Exception as e:
                print(f"FAILED - {e}")
                failed += 1

        print(f"\nUpdate complete")
        print(f"  Success: {success}")
        print(f"  Failed: {failed}")

        status = WorkflowStatus.SUCCESS if failed == 0 else WorkflowStatus.PARTIAL
        return WorkflowResult(
            status=status,
            message=f"Updated {success}/{len(matches)} objectives",
            data={'success': success, 'failed': failed}
        )


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
            UploadExistingWorkflow(),
            InitProjectWorkflow(),
            DiscoverWorkflow(),
            ListProjectsWorkflow(),
            UpdateFromFeedbackWorkflow(),
            UpdateObjectivesWorkflow(),
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


def main():
    parser = argparse.ArgumentParser(
        description="Generic Test Case Workflows - Multi-Project Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflows:
  generate              Generate test cases for a story
  upload                Generate + Upload to ADO test suite
  upload-existing       Upload existing test cases to ADO (skip generation)
  update-objectives     Update objectives/summary field for existing test cases in ADO
  update-from-feedback  Update test cases based on reviewer feedback
  init-project          Initialize a new project configuration
  discover              Discover project config from ADO stories
  list-projects         List all available project configurations

Examples:
  # Using default project (env-quickdraw)
  python3 workflows.py generate --story-id 272889

  # Using specific project
  python3 workflows.py generate --story-id 12345 --project mediapedia-us

  # Upload existing tests (skip generation)
  python3 workflows.py upload-existing --story-id 273566

  # Generate and upload
  python3 workflows.py upload --story-id 273566

  # Update objectives in ADO (fetches test cases directly from ADO)
  python3 workflows.py update-objectives --story-id 272265
  python3 workflows.py update-objectives --story-id 272265 --dry-run

  # Update objectives in ADO (from CSV export - legacy)
  python3 workflows.py update-objectives --csv "exported.csv" --story-id 272265

  # Update tests based on reviewer feedback
  python3 workflows.py update-from-feedback --csv "tests.csv" --feedback "feedback.txt"
  python3 workflows.py update-from-feedback --csv "tests.csv" --feedback "feedback.txt" --dry-run
  python3 workflows.py update-from-feedback --csv "tests.csv" --feedback "feedback.txt" --use-llm

  # Initialize new project
  python3 workflows.py init-project --name "MediaPedia" --org myorg --ado-project MediaPedia

  # Discover from stories
  python3 workflows.py discover --story-ids 12345 12346 --project-name my-app

  # List projects
  python3 workflows.py list-projects
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

    # Upload existing workflow
    upload_existing_parser = subparsers.add_parser('upload-existing', help='Upload existing test cases to ADO')
    upload_existing_parser.add_argument('--story-id', type=int, required=True, help='ADO Story ID')
    upload_existing_parser.add_argument('--output-dir', default=None, help='Output directory to search for files')

    # List projects workflow
    subparsers.add_parser('list-projects', help='List all projects')

    # Update from feedback workflow
    feedback_parser = subparsers.add_parser('update-from-feedback',
                                            help='Update test cases based on reviewer feedback')
    feedback_parser.add_argument('--csv', dest='csv_file', required=True,
                                 help='CSV file exported from ADO with existing test cases')
    feedback_parser.add_argument('--feedback', dest='feedback_file', required=True,
                                 help='Text file with reviewer/customer feedback')
    feedback_parser.add_argument('--dry-run', action='store_true',
                                 help='Preview changes without updating ADO')
    feedback_parser.add_argument('--use-llm', action='store_true',
                                 help='Use LLM to interpret feedback (requires OPENAI_API_KEY)')
    feedback_parser.add_argument('--output', dest='output_file',
                                 help='Save fixes to JSON file for review before applying')

    # Update objectives workflow
    objectives_parser = subparsers.add_parser('update-objectives',
                                              help='Update objectives/summary field for existing test cases in ADO')
    objectives_parser.add_argument('--csv', dest='csv_file', required=False, default=None,
                                   help='CSV file exported from ADO (optional - if not provided, fetches from ADO)')
    objectives_parser.add_argument('--story-id', type=int, required=True,
                                   help='Story ID to find local objective files and test suite in ADO')
    objectives_parser.add_argument('--output-dir', default=None,
                                   help='Directory containing local test files')
    objectives_parser.add_argument('--dry-run', action='store_true',
                                   help='Preview changes without updating ADO')

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
