"""
MCP Tools for AI Test Generation.

Defines the tools available to MCP clients for test generation operations.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects import ProjectConfig, ProjectManager, ApplicationDiscovery, get_project_manager
from projects.project_config import create_new_project_config
from projects.test_suite_creator import TestSuiteCreator, QAPrepGenerator


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None


class TestGenTools:
    """
    Collection of tools for AI test generation.
    Each method represents a tool that can be called by MCP clients.
    """

    def __init__(self):
        self.project_manager = get_project_manager()
        self.project_manager.load_from_directory()

    # =========================================================================
    # Project Management Tools
    # =========================================================================

    def list_projects(self) -> ToolResult:
        """
        List all available project configurations.

        Returns:
            ToolResult with list of project IDs and their details.
        """
        projects = []
        for project_id in self.project_manager.list_projects():
            config = self.project_manager.get_project(project_id)
            projects.append({
                'project_id': project_id,
                'application_name': config.application.name,
                'app_type': config.application.app_type,
                'ado_organization': config.ado.organization,
                'ado_project': config.ado.project,
            })

        return ToolResult(
            success=True,
            message=f"Found {len(projects)} projects",
            data={'projects': projects}
        )

    def get_project_config(self, project_id: str) -> ToolResult:
        """
        Get detailed configuration for a specific project.

        Args:
            project_id: The project identifier.

        Returns:
            ToolResult with full project configuration.
        """
        config = self.project_manager.get_project(project_id)
        if not config:
            return ToolResult(
                success=False,
                message=f"Project not found: {project_id}",
                error="PROJECT_NOT_FOUND"
            )

        return ToolResult(
            success=True,
            message=f"Configuration for project: {project_id}",
            data={
                'project_id': config.project_id,
                'application': {
                    'name': config.application.name,
                    'description': config.application.description,
                    'type': config.application.app_type,
                    'platforms': config.application.supported_platforms,
                    'ui_surfaces': config.application.main_ui_surfaces,
                },
                'ado': {
                    'organization': config.ado.organization,
                    'project': config.ado.project,
                    'area_path': config.ado.area_path,
                    'test_suite_pattern': config.ado.test_suite_pattern,
                    'has_qa_prep': config.ado.qa_prep_pattern is not None,
                },
                'rules': {
                    'forbidden_words': config.rules.forbidden_words,
                    'allowed_areas': config.rules.allowed_areas,
                }
            }
        )

    def create_project(
        self,
        project_id: str,
        app_name: str,
        app_type: str = "desktop",
        ado_org: str = None,
        ado_project: str = None,
        area_path: str = None,
        platforms: List[str] = None,
        ui_surfaces: List[str] = None,
        has_qa_prep: bool = False
    ) -> ToolResult:
        """
        Create a new project configuration.

        Args:
            project_id: Unique identifier for the project.
            app_name: Name of the application under test.
            app_type: Type of application (desktop, web, mobile, hybrid).
            ado_org: Azure DevOps organization.
            ado_project: Azure DevOps project name.
            area_path: ADO area path.
            platforms: List of supported platforms.
            ui_surfaces: List of main UI surfaces.
            has_qa_prep: Whether the project uses QA Prep tasks.

        Returns:
            ToolResult with created project info and config path.
        """
        # Use environment variables as defaults
        ado_org = ado_org or os.getenv('ADO_ORG', '')
        ado_project = ado_project or os.getenv('ADO_PROJECT', '')
        area_path = area_path or os.getenv('ADO_AREA_PATH', '')

        if not ado_org or not ado_project:
            return ToolResult(
                success=False,
                message="ADO organization and project are required",
                error="MISSING_ADO_CONFIG"
            )

        try:
            config = create_new_project_config(
                project_id=project_id,
                app_name=app_name,
                ado_org=ado_org,
                ado_project=ado_project,
                area_path=area_path,
                app_type=app_type,
                platforms=platforms or ['Windows 11'],
                ui_surfaces=ui_surfaces or [],
                qa_prep_pattern="Story {story_id}: QA Prep" if has_qa_prep else None,
            )

            config_path = config.save()
            self.project_manager.register_project(config)

            return ToolResult(
                success=True,
                message=f"Created project: {project_id}",
                data={
                    'project_id': project_id,
                    'config_path': config_path,
                    'application_name': app_name
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Failed to create project: {e}",
                error="CREATE_FAILED"
            )

    def discover_project(
        self,
        project_id: str,
        story_ids: List[int],
        ado_org: str = None,
        ado_project: str = None
    ) -> ToolResult:
        """
        Discover project configuration from existing ADO stories.

        Args:
            project_id: ID for the new project.
            story_ids: List of story IDs to analyze.
            ado_org: Azure DevOps organization.
            ado_project: Azure DevOps project name.

        Returns:
            ToolResult with discovered configuration.
        """
        from src.ado_client import ADOClient

        ado_org = ado_org or os.getenv('ADO_ORG', '')
        ado_project = ado_project or os.getenv('ADO_PROJECT', '')

        try:
            ado_client = ADOClient(
                org=ado_org,
                project=ado_project,
                pat=os.getenv('ADO_PAT')
            )

            # Fetch stories
            stories = []
            for story_id in story_ids:
                try:
                    story_data = ado_client.fetch_story_comprehensive(story_id)
                    stories.append(story_data)
                except Exception:
                    pass

            if not stories:
                return ToolResult(
                    success=False,
                    message="No stories could be fetched",
                    error="NO_STORIES"
                )

            # Discover
            discovery = ApplicationDiscovery()
            discovered = discovery.discover_from_stories(stories)

            # Create config
            config = discovery.create_project_config(
                discovery=discovered,
                project_id=project_id,
                ado_org=ado_org,
                ado_project=ado_project,
                area_path=os.getenv('ADO_AREA_PATH', ''),
            )

            config_path = config.save()
            self.project_manager.register_project(config)

            return ToolResult(
                success=True,
                message=f"Discovered project from {len(stories)} stories",
                data={
                    'project_id': project_id,
                    'config_path': config_path,
                    'discovered': {
                        'app_name': discovered.name,
                        'app_type': discovered.app_type,
                        'platforms': discovered.supported_platforms,
                        'ui_surfaces': discovered.main_ui_surfaces,
                        'confidence': discovered.confidence_score
                    }
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Discovery failed: {e}",
                error="DISCOVERY_FAILED"
            )

    # =========================================================================
    # Test Generation Tools
    # =========================================================================

    def generate_test_cases(
        self,
        story_id: int,
        project_id: str = None,
        skip_llm: bool = False
    ) -> ToolResult:
        """
        Generate test cases for a story.

        Args:
            story_id: ADO story ID.
            project_id: Project configuration to use (default: env-quickdraw).
            skip_llm: Skip LLM correction if True.

        Returns:
            ToolResult with generated test cases and output files.
        """
        from src.ado_client import ADOClient
        from src.generic_test_generator import GenericTestGenerator
        from src.csv_generator import CSVGenerator
        from src.objective_generator import ObjectiveGenerator
        import json

        # Get project config
        if project_id:
            config = self.project_manager.get_project(project_id)
            if not config:
                return ToolResult(
                    success=False,
                    message=f"Project not found: {project_id}",
                    error="PROJECT_NOT_FOUND"
                )
        else:
            config = self.project_manager.get_or_create_default()

        try:
            # Fetch story
            ado_client = ADOClient(
                org=config.ado.organization,
                project=config.ado.project,
                pat=config.ado.pat or os.getenv('ADO_PAT')
            )
            story_data = ado_client.fetch_story_comprehensive(story_id)

            title = story_data['title']
            acceptance_criteria = story_data['acceptance_criteria']
            qa_prep = story_data.get('qa_prep', '')

            if not acceptance_criteria:
                return ToolResult(
                    success=False,
                    message="No acceptance criteria found",
                    error="NO_AC"
                )

            # Generate
            generator = GenericTestGenerator(config)
            test_cases = generator.generate_test_cases(
                story_data={'story_id': story_id, 'title': title},
                criteria=acceptance_criteria,
                qa_prep_content=qa_prep
            )

            # Apply LLM correction if enabled
            if not skip_llm and config.llm_enabled:
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key and api_key != "your-api-key-here":
                    try:
                        from correct_with_llm import LLMCorrector
                        corrector = LLMCorrector(api_key=api_key, model=config.llm_model)
                        test_cases = corrector.correct_test_cases(
                            test_cases=test_cases,
                            story_id=str(story_id),
                            feature_name=title,
                            acceptance_criteria=acceptance_criteria,
                            qa_prep=qa_prep
                        )
                    except Exception:
                        pass  # Fall back to rule-based

            # Save outputs
            output_dir = config.output_dir
            os.makedirs(output_dir, exist_ok=True)

            safe_title = "".join(c if c.isalnum() or c in ' _-' else '_' for c in title)
            safe_title = safe_title.replace(' ', '_')[:50]

            csv_path = os.path.join(output_dir, f"{story_id}_{safe_title}_TESTS.csv")
            CSVGenerator().generate_csv(test_cases=test_cases, output_file=csv_path)

            obj_path = os.path.join(output_dir, f"{story_id}_{safe_title}_OBJECTIVES.txt")
            ObjectiveGenerator().generate_objectives_file(test_cases, obj_path)

            return ToolResult(
                success=True,
                message=f"Generated {len(test_cases)} test cases",
                data={
                    'story_id': story_id,
                    'title': title,
                    'test_count': len(test_cases),
                    'test_cases': test_cases,
                    'output_files': {
                        'csv': csv_path,
                        'objectives': obj_path
                    }
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Generation failed: {e}",
                error="GENERATION_FAILED"
            )

    def upload_test_cases(
        self,
        story_id: int,
        project_id: str = None,
        auto_create_suite: bool = True
    ) -> ToolResult:
        """
        Generate and upload test cases to ADO.

        Args:
            story_id: ADO story ID.
            project_id: Project configuration to use.
            auto_create_suite: Create test suite if not found.

        Returns:
            ToolResult with upload results.
        """
        from src.ado_client import ADOClient
        from src.test_suite_uploader import TestSuiteUploader

        # Get project config
        if project_id:
            config = self.project_manager.get_project(project_id)
            if not config:
                return ToolResult(
                    success=False,
                    message=f"Project not found: {project_id}",
                    error="PROJECT_NOT_FOUND"
                )
        else:
            config = self.project_manager.get_or_create_default()

        try:
            # Initialize clients
            ado_client = ADOClient(
                org=config.ado.organization,
                project=config.ado.project,
                pat=config.ado.pat or os.getenv('ADO_PAT')
            )
            suite_uploader = TestSuiteUploader(ado_client)

            # Find or create suite
            suite_info = suite_uploader.find_test_suite_by_story_id(story_id)

            if not suite_info:
                if auto_create_suite:
                    story_data = ado_client.fetch_story_comprehensive(story_id)
                    suite_creator = TestSuiteCreator(config)
                    plan_info, suite_obj = suite_creator.create_test_organization(
                        story_id=str(story_id),
                        story_name=story_data['title']
                    )
                    suite_info = {
                        'id': suite_obj.id,
                        'name': suite_obj.name,
                        'plan_id': plan_info.id
                    }
                else:
                    return ToolResult(
                        success=False,
                        message="No test suite found",
                        error="NO_SUITE"
                    )

            # Generate test cases
            gen_result = self.generate_test_cases(story_id, project_id)
            if not gen_result.success:
                return gen_result

            test_cases = gen_result.data['test_cases']

            # Upload
            created = []
            failed = []

            from src.objective_generator import ObjectiveGenerator
            import time
            import requests

            objective_gen = ObjectiveGenerator()
            plan_id = suite_info['plan_id']
            suite_id = suite_info['id']

            for tc in test_cases:
                try:
                    # Create test case (simplified)
                    url = f"{ado_client.base_url}/_apis/wit/workitems/$Test Case?api-version=7.1"

                    steps_xml = self._build_steps_xml(tc.get('steps', []))
                    formatted_obj = objective_gen.format_objective_for_ado(tc.get('objective', ''))

                    patch_doc = [
                        {"op": "add", "path": "/fields/System.Title", "value": tc['title']},
                        {"op": "add", "path": "/fields/System.AssignedTo", "value": config.ado.assigned_to},
                        {"op": "add", "path": "/fields/System.State", "value": config.ado.default_state},
                        {"op": "add", "path": "/fields/System.AreaPath", "value": config.ado.area_path},
                        {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": steps_xml}
                    ]
                    if formatted_obj:
                        patch_doc.append({"op": "add", "path": "/fields/System.Description", "value": formatted_obj})

                    headers = ado_client.headers.copy()
                    headers['Content-Type'] = 'application/json-patch+json'

                    response = requests.patch(url, headers=headers, json=patch_doc)
                    response.raise_for_status()
                    work_item_id = response.json().get('id')

                    # Add to suite
                    suite_url = f"{ado_client.base_url}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase?api-version=7.1"
                    requests.post(suite_url, headers=ado_client.headers, json=[{'workItem': {'id': work_item_id}}])

                    created.append({'id': work_item_id, 'tc_id': tc['id']})
                    time.sleep(0.5)
                except Exception as e:
                    failed.append({'tc_id': tc.get('id', ''), 'error': str(e)})

            return ToolResult(
                success=len(failed) == 0,
                message=f"Uploaded {len(created)}/{len(test_cases)} test cases",
                data={
                    'created': created,
                    'failed': failed,
                    'suite_info': suite_info
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Upload failed: {e}",
                error="UPLOAD_FAILED"
            )

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

    # =========================================================================
    # Analysis Tools
    # =========================================================================

    def analyze_story(self, story_id: int, project_id: str = None) -> ToolResult:
        """
        Analyze a story without generating test cases.

        Args:
            story_id: ADO story ID.
            project_id: Project configuration to use.

        Returns:
            ToolResult with story analysis.
        """
        from src.ado_client import ADOClient

        if project_id:
            config = self.project_manager.get_project(project_id)
            if not config:
                return ToolResult(
                    success=False,
                    message=f"Project not found: {project_id}",
                    error="PROJECT_NOT_FOUND"
                )
        else:
            config = self.project_manager.get_or_create_default()

        try:
            ado_client = ADOClient(
                org=config.ado.organization,
                project=config.ado.project,
                pat=config.ado.pat or os.getenv('ADO_PAT')
            )
            story_data = ado_client.fetch_story_comprehensive(story_id)

            # Analyze AC
            ac_analysis = []
            for i, ac in enumerate(story_data['acceptance_criteria'], 1):
                ac_lower = ac.lower()
                ac_type = 'functional'
                if 'accessibility' in ac_lower or 'wcag' in ac_lower:
                    ac_type = 'accessibility'
                elif 'undo' in ac_lower or 'redo' in ac_lower:
                    ac_type = 'undo_redo'
                elif 'visibility' in ac_lower or 'show' in ac_lower:
                    ac_type = 'visibility'

                requires_object = config.application.requires_object_interaction(ac)

                ac_analysis.append({
                    'index': i,
                    'text': ac[:100] + '...' if len(ac) > 100 else ac,
                    'type': ac_type,
                    'requires_object_setup': requires_object
                })

            # Estimate test count
            base_count = len(story_data['acceptance_criteria'])
            platform_count = len(config.application.supported_platforms)
            estimated_tests = base_count + platform_count + 2  # +2 for edge cases

            return ToolResult(
                success=True,
                message=f"Analyzed story {story_id}",
                data={
                    'story_id': story_id,
                    'title': story_data['title'],
                    'acceptance_criteria_count': len(story_data['acceptance_criteria']),
                    'has_qa_prep': bool(story_data.get('qa_prep')),
                    'ac_analysis': ac_analysis,
                    'estimated_test_count': estimated_tests,
                    'suggested_platforms': config.application.supported_platforms
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Analysis failed: {e}",
                error="ANALYSIS_FAILED"
            )


# Tool definitions for MCP protocol
MCP_TOOL_DEFINITIONS = [
    {
        "name": "list_projects",
        "description": "List all available project configurations for test generation",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_project_config",
        "description": "Get detailed configuration for a specific project",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The project identifier"
                }
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "create_project",
        "description": "Create a new project configuration for test generation",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Unique identifier for the project"
                },
                "app_name": {
                    "type": "string",
                    "description": "Name of the application under test"
                },
                "app_type": {
                    "type": "string",
                    "enum": ["desktop", "web", "mobile", "hybrid"],
                    "description": "Type of application"
                },
                "ado_org": {
                    "type": "string",
                    "description": "Azure DevOps organization"
                },
                "ado_project": {
                    "type": "string",
                    "description": "Azure DevOps project name"
                },
                "platforms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of supported platforms"
                }
            },
            "required": ["project_id", "app_name"]
        }
    },
    {
        "name": "discover_project",
        "description": "Discover project configuration from existing ADO stories",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID for the new project"
                },
                "story_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of story IDs to analyze"
                }
            },
            "required": ["project_id", "story_ids"]
        }
    },
    {
        "name": "generate_test_cases",
        "description": "Generate test cases for an ADO story",
        "input_schema": {
            "type": "object",
            "properties": {
                "story_id": {
                    "type": "integer",
                    "description": "ADO story ID"
                },
                "project_id": {
                    "type": "string",
                    "description": "Project configuration to use"
                },
                "skip_llm": {
                    "type": "boolean",
                    "description": "Skip LLM correction if true"
                }
            },
            "required": ["story_id"]
        }
    },
    {
        "name": "upload_test_cases",
        "description": "Generate and upload test cases to ADO test suite",
        "input_schema": {
            "type": "object",
            "properties": {
                "story_id": {
                    "type": "integer",
                    "description": "ADO story ID"
                },
                "project_id": {
                    "type": "string",
                    "description": "Project configuration to use"
                },
                "auto_create_suite": {
                    "type": "boolean",
                    "description": "Create test suite if not found"
                }
            },
            "required": ["story_id"]
        }
    },
    {
        "name": "analyze_story",
        "description": "Analyze a story to understand its test requirements",
        "input_schema": {
            "type": "object",
            "properties": {
                "story_id": {
                    "type": "integer",
                    "description": "ADO story ID"
                },
                "project_id": {
                    "type": "string",
                    "description": "Project configuration to use"
                }
            },
            "required": ["story_id"]
        }
    }
]
