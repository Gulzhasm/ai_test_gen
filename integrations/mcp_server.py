#!/usr/bin/env python3
"""
Test Generation MCP Server for GitHub Copilot.

Exposes the 3 main workflows as MCP tools:
1. generate_tests - Generate test cases and save to output folder
2. upload_tests - Generate + Upload to ADO test suite
3. check_story - Get story details from ADO

Additional tools:
- list_projects - List available project configurations

Usage:
    # CLI mode (with arguments)
    python3 mcp_server.py <story_id> [project_id]

    # MCP mode (no arguments - for VS Code/Copilot)
    python3 mcp_server.py
"""
import asyncio
import json
import sys
import os
import time
import traceback
import requests
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# MCP imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("MCP not installed. Run: pip install mcp", file=sys.stderr)

# Project imports
from projects.project_config import ProjectConfig, get_env_quickdraw_config
from core.services.test_generator import GenericTestGenerator
from infrastructure.export.csv_generator import CSVGenerator
from infrastructure.export.objective_generator import ObjectiveGenerator
from infrastructure.ado.ado_repository import ADOStoryRepository


def load_project_config(project_id: str) -> ProjectConfig:
    """Load project configuration by ID."""
    config_path = PROJECT_ROOT / f"projects/configs/{project_id}.yaml"
    if config_path.exists():
        return ProjectConfig.load_from_yaml(str(config_path))
    elif project_id == "env-quickdraw":
        return get_env_quickdraw_config()
    else:
        raise ValueError(f"Project config not found: {project_id}")


def list_available_projects() -> list:
    """List all available project configurations."""
    projects = []
    config_dir = PROJECT_ROOT / "projects/configs"
    if config_dir.exists():
        for yaml_file in config_dir.glob("*.yaml"):
            projects.append(yaml_file.stem)
    if "env-quickdraw" not in projects:
        projects.append("env-quickdraw")
    return sorted(projects)


def save_outputs(
    config: ProjectConfig,
    story_id: str,
    title: str,
    test_cases: list,
    output_dir: str = "output"
) -> dict:
    """Save generated outputs to files (CSV, objectives, JSON)."""
    output_path = PROJECT_ROOT / output_dir
    output_path.mkdir(exist_ok=True)

    # Clean title for filename
    safe_title = "".join(c if c.isalnum() or c in ' _-' else '_' for c in title)
    safe_title = safe_title.replace(' ', '_')[:50]
    suffix = "HYBRID"

    output_files = {}

    # CSV for ADO import
    csv_path = output_path / f"{story_id}_{safe_title}_{suffix}_TESTS.csv"
    csv_gen = CSVGenerator(config.ado)
    csv_gen.generate_csv(test_cases=test_cases, output_file=str(csv_path))
    output_files['csv'] = str(csv_path)

    # Objectives TXT
    obj_path = output_path / f"{story_id}_{safe_title}_{suffix}_OBJECTIVES.txt"
    obj_gen = ObjectiveGenerator(config.objective_key_term_patterns)
    obj_gen.generate_objectives_file(test_cases, str(obj_path))
    output_files['objectives'] = str(obj_path)

    # Debug JSON
    json_path = output_path / f"{story_id}_{safe_title}_{suffix}_DEBUG.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'story_id': story_id,
            'title': title,
            'project': config.project_id,
            'application': config.application.name,
            'test_cases': test_cases,
            'mode': 'hybrid'
        }, f, indent=2)
    output_files['debug_json'] = str(json_path)

    return output_files


# =============================================================================
# WORKFLOW 1: Generate Test Cases
# =============================================================================

async def generate_tests_for_story(
    story_id: str,
    project_id: str = "env-quickdraw"
) -> dict:
    """
    WORKFLOW 1: Generate test cases for a story and save to output folder.

    Args:
        story_id: ADO work item ID
        project_id: Project configuration ID

    Returns:
        Dict with generated test cases and output file paths
    """
    try:
        config = load_project_config(project_id)
        story_repo = ADOStoryRepository(config.ado)
        story = story_repo.get_story(int(story_id))

        if not story:
            return {"error": f"Story {story_id} not found"}

        criteria = story.acceptance_criteria
        if not criteria:
            return {"error": "No acceptance criteria found in story"}

        # Generate test cases
        generator = GenericTestGenerator(config)
        story_data = {
            'story_id': story_id,
            'title': story.title,
            'description': story.description or ""
        }
        test_cases = generator.generate_test_cases(story_data, criteria)

        # Save outputs to files
        output_files = save_outputs(
            config=config,
            story_id=story_id,
            title=story.title,
            test_cases=test_cases,
            output_dir=config.output_dir or "output"
        )

        # Generate preview strings
        csv_gen = CSVGenerator(config.ado)
        csv_content = csv_gen.generate_csv_string(test_cases)
        obj_gen = ObjectiveGenerator(config.objective_key_term_patterns)
        objectives = obj_gen.generate_objectives_string(test_cases)

        return {
            "success": True,
            "workflow": "generate",
            "story_id": story_id,
            "story_title": story.title,
            "project": project_id,
            "test_count": len(test_cases),
            "acceptance_criteria_count": len(criteria),
            "output_files": output_files,
            "test_cases": [
                {"id": tc["id"], "title": tc["title"], "step_count": len(tc.get("steps", []))}
                for tc in test_cases
            ],
            "csv_preview": csv_content[:2000] + "..." if len(csv_content) > 2000 else csv_content,
            "objectives_preview": objectives[:1000] + "..." if len(objectives) > 1000 else objectives
        }

    except Exception as e:
        return {"error": str(e), "details": traceback.format_exc()}


# =============================================================================
# WORKFLOW 2: Generate + Upload to ADO
# =============================================================================

async def upload_tests_for_story(
    story_id: str,
    project_id: str = "env-quickdraw",
    dry_run: bool = False
) -> dict:
    """
    WORKFLOW 2: Generate test cases and upload to ADO test suite.

    Args:
        story_id: ADO work item ID
        project_id: Project configuration ID
        dry_run: If True, preview without uploading

    Returns:
        Dict with upload results
    """
    try:
        from infrastructure.ado.ado_repository import ADOTestSuiteRepository
        from infrastructure.ado.http_client import ADOHttpClient
        from projects.test_suite_creator import TestSuiteCreator

        config = load_project_config(project_id)

        # Initialize ADO clients
        ado_http_client = ADOHttpClient(
            organization=config.ado.organization,
            project=config.ado.project,
            pat=config.ado.pat or os.getenv('ADO_PAT')
        )
        suite_repo = ADOTestSuiteRepository(config.ado)
        story_repo = ADOStoryRepository(config.ado)

        # Step 1: Find or create test suite
        suite_info = suite_repo.find_suite_by_story_id(int(story_id))

        if not suite_info:
            # Auto-create test suite
            story = story_repo.get_story(int(story_id))
            story_title = story.title if story else f"Story {story_id}"

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

        # Step 2: Generate test cases
        gen_result = await generate_tests_for_story(story_id, project_id)
        if "error" in gen_result:
            return gen_result

        test_cases_data = gen_result.get('test_cases', [])

        # Load full test cases from debug JSON
        debug_json_path = gen_result['output_files']['debug_json']
        with open(debug_json_path, 'r') as f:
            debug_data = json.load(f)
        test_cases = debug_data['test_cases']

        if dry_run:
            return {
                "success": True,
                "workflow": "upload",
                "mode": "dry_run",
                "story_id": story_id,
                "project": project_id,
                "suite_info": suite_info,
                "test_count": len(test_cases),
                "output_files": gen_result['output_files'],
                "would_create": [tc['id'] for tc in test_cases]
            }

        # Step 3: Upload test cases
        obj_gen = ObjectiveGenerator(config.objective_key_term_patterns)
        created = []
        failed = []

        for tc in test_cases:
            tc_id = tc.get('id', '')
            title = tc.get('title', '')
            steps = tc.get('steps', [])
            objective = tc.get('objective', '')

            # Create test case work item
            work_item_id = _create_test_case(
                config, ado_http_client, title, steps, objective, tc_id, obj_gen
            )

            if work_item_id:
                # Add to suite
                if _add_to_suite(ado_http_client, suite_info['plan_id'], suite_info['id'], work_item_id):
                    created.append({'id': work_item_id, 'tc_id': tc_id})
                else:
                    failed.append({'tc_id': tc_id, 'error': 'Failed to add to suite'})
            else:
                failed.append({'tc_id': tc_id, 'error': 'Failed to create'})

            time.sleep(0.3)  # Rate limiting

        return {
            "success": True,
            "workflow": "upload",
            "mode": "live",
            "story_id": story_id,
            "project": project_id,
            "suite_info": suite_info,
            "created_count": len(created),
            "failed_count": len(failed),
            "created": created,
            "failed": failed,
            "output_files": gen_result['output_files']
        }

    except Exception as e:
        return {"error": str(e), "details": traceback.format_exc()}


def _create_test_case(config, ado_client, title, steps, objective, tc_id, obj_gen) -> Optional[int]:
    """Create a test case work item in ADO."""
    url = f"{ado_client.base_url}/_apis/wit/workitems/$Test Case?api-version=7.1"

    # Build steps XML
    steps_xml = _build_steps_xml(steps)

    # Format objective
    formatted_objective = obj_gen.format_objective_for_ado(objective) if objective else ""

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


def _build_steps_xml(steps: List[Dict]) -> str:
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


def _add_to_suite(ado_client, plan_id: int, suite_id: int, test_case_id: int) -> bool:
    """Add test case to test suite."""
    url = f"{ado_client.base_url}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase?api-version=7.1"
    body = [{'workItem': {'id': test_case_id}}]

    try:
        response = requests.post(url, headers=ado_client.headers, json=body)
        return response.status_code == 200
    except Exception:
        return False


# =============================================================================
# WORKFLOW 3: Check Story Details
# =============================================================================

async def get_story_details(story_id: str, project_id: str = "env-quickdraw") -> dict:
    """
    WORKFLOW 3: Get story details from ADO including acceptance criteria.

    Args:
        story_id: ADO work item ID
        project_id: Project configuration ID

    Returns:
        Dict with story details
    """
    try:
        config = load_project_config(project_id)
        story_repo = ADOStoryRepository(config.ado)
        story = story_repo.get_story(int(story_id))

        if not story:
            return {"error": f"Story {story_id} not found"}

        return {
            "success": True,
            "story_id": story_id,
            "title": story.title,
            "description": story.description[:500] + "..." if story.description and len(story.description) > 500 else story.description,
            "acceptance_criteria": story.acceptance_criteria,
            "ac_count": len(story.acceptance_criteria)
        }

    except Exception as e:
        return {"error": str(e), "details": traceback.format_exc()}


# =============================================================================
# CLI Mode
# =============================================================================

def run_cli():
    """Run in CLI mode (when arguments provided).

    Supports both styles:
        python3 mcp_server.py <story_id> [project_id]
        python3 mcp_server.py generate --story-id <id> --project <project>
    """
    import argparse

    # Check for command-style invocation
    if len(sys.argv) > 1 and sys.argv[1] in ('generate', 'upload', 'check', 'list'):
        command = sys.argv[1]
        parser = argparse.ArgumentParser(description='Test Generation MCP Server - CLI Mode')
        parser.add_argument('command', help='Command to run')
        parser.add_argument('--story-id', '--story', dest='story_id', help='ADO Story ID')
        parser.add_argument('--project', default='env-quickdraw', help='Project config ID')
        parser.add_argument('--dry-run', action='store_true', help='Preview without uploading')

        args = parser.parse_args()

        if command == 'list':
            projects = list_available_projects()
            print(f"\nAvailable projects:")
            for p in projects:
                print(f"  - {p}")
            return True

        if not args.story_id:
            print("Error: --story-id is required for generate/upload/check commands")
            return False

        story_id = args.story_id
        project = args.project

    elif len(sys.argv) > 1:
        # Positional style: mcp_server.py <story_id> [project_id]
        story_id = sys.argv[1]
        project = sys.argv[2] if len(sys.argv) > 2 else "env-quickdraw"
        command = 'generate'
    else:
        return False

    print(f"\n{'='*60}")
    print(f"MCP Test Generator - CLI Mode")
    print(f"Command: {command}")
    print(f"Story ID: {story_id}")
    print(f"Project: {project}")
    print(f"{'='*60}\n")

    if command == 'generate':
        result = asyncio.run(generate_tests_for_story(story_id, project))
    elif command == 'upload':
        dry_run = '--dry-run' in sys.argv
        result = asyncio.run(upload_tests_for_story(story_id, project, dry_run=dry_run))
    elif command == 'check':
        result = asyncio.run(get_story_details(story_id, project))
    else:
        print(f"Unknown command: {command}")
        return False

    if result.get("success"):
        print(f"\nOPERATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Test cases: {result.get('test_count', 'N/A')}")
        if 'output_files' in result:
            print(f"  Output files:")
            for key, path in result.get('output_files', {}).items():
                print(f"    {key}: {path}")
        print(f"{'='*60}\n")

    print(json.dumps(result, indent=2))
    return True


# =============================================================================
# MCP Server Setup
# =============================================================================

if MCP_AVAILABLE:
    server = Server("test-gen")

    @server.list_tools()
    async def list_tools():
        """List available MCP tools."""
        return [
            Tool(
                name="generate_tests",
                description="WORKFLOW 1: Generate test cases for a user story. Saves CSV, objectives, and JSON files to output folder. Does NOT upload to ADO.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "story_id": {
                            "type": "string",
                            "description": "The Azure DevOps work item ID (e.g., '272889')"
                        },
                        "project": {
                            "type": "string",
                            "description": "Project configuration ID (default: 'env-quickdraw')",
                            "default": "env-quickdraw"
                        }
                    },
                    "required": ["story_id"]
                }
            ),
            Tool(
                name="upload_tests",
                description="WORKFLOW 2: Generate test cases AND upload to ADO test suite. Creates test suite if it doesn't exist. Use dry_run=true to preview without uploading.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "story_id": {
                            "type": "string",
                            "description": "The Azure DevOps work item ID (e.g., '272889')"
                        },
                        "project": {
                            "type": "string",
                            "description": "Project configuration ID (default: 'env-quickdraw')",
                            "default": "env-quickdraw"
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "If true, preview without uploading (default: false)",
                            "default": False
                        }
                    },
                    "required": ["story_id"]
                }
            ),
            Tool(
                name="check_story",
                description="WORKFLOW 3: Get details about a user story from Azure DevOps, including acceptance criteria.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "story_id": {
                            "type": "string",
                            "description": "The Azure DevOps work item ID"
                        },
                        "project": {
                            "type": "string",
                            "description": "Project configuration ID",
                            "default": "env-quickdraw"
                        }
                    },
                    "required": ["story_id"]
                }
            ),
            Tool(
                name="list_projects",
                description="List all available project configurations for test generation.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        """Handle tool calls."""
        if name == "generate_tests":
            result = await generate_tests_for_story(
                story_id=arguments["story_id"],
                project_id=arguments.get("project", "env-quickdraw")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "upload_tests":
            result = await upload_tests_for_story(
                story_id=arguments["story_id"],
                project_id=arguments.get("project", "env-quickdraw"),
                dry_run=arguments.get("dry_run", False)
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "check_story":
            result = await get_story_details(
                story_id=arguments["story_id"],
                project_id=arguments.get("project", "env-quickdraw")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_projects":
            projects = list_available_projects()
            return [TextContent(
                type="text",
                text=json.dumps({
                    "available_projects": projects,
                    "default": "env-quickdraw"
                }, indent=2)
            )]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def main():
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    elif MCP_AVAILABLE:
        asyncio.run(main())
    else:
        print("MCP not available. Install with: pip install mcp")
        print("\nUsage: python3 mcp_server.py <story_id> [project_id]")
        print("\nAvailable projects:")
        for p in list_available_projects():
            print(f"  - {p}")
