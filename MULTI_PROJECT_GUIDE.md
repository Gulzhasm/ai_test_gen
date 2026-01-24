# Multi-Project Support Guide

This guide explains how to use the AI Test Generation framework with multiple projects.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Project Configuration](#project-configuration)
4. [Creating a New Project](#creating-a-new-project)
5. [Project Discovery](#project-discovery)
6. [Using Projects](#using-projects)
7. [Auto Test Suite Creation](#auto-test-suite-creation)
8. [MCP Integration](#mcp-integration)
9. [Migration from Single Project](#migration-from-single-project)

---

## Overview

The framework now supports multiple projects, allowing you to:

- Generate test cases for different applications (MediaPedia, ENV QuickDraw, etc.)
- Configure application-specific step templates and UI surfaces
- Support projects with or without QA Prep tasks
- Auto-create test suites when they don't exist
- Integrate with AI assistants via MCP (Model Context Protocol)

---

## Quick Start

### Using Default Project (ENV QuickDraw)

```bash
# Works exactly like before - uses env-quickdraw config
python3 workflows_generic.py generate --story-id 272889
python3 workflows_generic.py upload --story-id 272889
```

### Using a Different Project

```bash
# Specify project with --project flag
python3 workflows_generic.py generate --story-id 12345 --project mediapedia-us
python3 workflows_generic.py upload --story-id 12345 --project mediapedia-us
```

### List Available Projects

```bash
python3 workflows_generic.py list-projects
```

---

## Project Configuration

Projects are configured using YAML files stored in `projects/configs/`.

### Configuration Structure

```yaml
project_id: mediapedia-us

application:
  name: MediaPedia
  description: Media management platform
  type: web  # desktop, web, mobile, hybrid

  # Step templates - customize for your app
  prereq_template: "Pre-req: User has a valid {app_name} account"
  launch_step: "Navigate to the {app_name} URL and log in."
  launch_expected: "Dashboard is displayed."
  close_step: "Log out and close the browser."

  # UI surfaces in your application
  ui_surfaces:
    - Dashboard
    - Media Library
    - Settings Menu

  # Map feature keywords to entry points
  entry_point_mappings:
    upload: Upload Panel
    media: Media Library
    setting: Settings Menu

  # Supported platforms
  platforms:
    - Chrome
    - Safari
    - iPad

ado:
  organization: your-org
  project: MediaPedia
  area_path: "MediaPedia\\US Team"
  assigned_to: user@example.com
  default_state: Design
  test_suite_pattern: "{story_id} : {story_name}"
  qa_prep_pattern: null  # Set to null if no QA Prep tasks

rules:
  forbidden_words:
    - "or / OR"
    - "if available"
  allowed_areas:
    - Dashboard
    - Media Library
  first_test_id: AC1
  test_id_increment: 5

output_dir: output/mediapedia
llm_enabled: true
```

### Key Configuration Options

| Option | Description |
|--------|-------------|
| `project_id` | Unique identifier for the project |
| `application.name` | Application name used in test steps |
| `application.type` | desktop, web, mobile, or hybrid |
| `application.prereq_template` | Template for prerequisite step |
| `application.launch_step` | Template for launch step |
| `application.close_step` | Template for close step |
| `ado.qa_prep_pattern` | Pattern for QA Prep tasks (null if none) |

---

## Creating a New Project

### Method 1: Interactive CLI

```bash
python3 workflows_generic.py init-project --name "My App" --interactive
```

This will ask you questions about:
- Application type (desktop, web, mobile)
- Supported platforms
- Main UI surfaces
- Launch behavior

### Method 2: Command Line Parameters

```bash
python3 workflows_generic.py init-project \
  --name "MediaPedia" \
  --id mediapedia-us \
  --org myorg \
  --ado-project MediaPedia \
  --area-path "MediaPedia\\US Team"
```

### Method 3: Copy and Edit YAML

1. Copy `projects/configs/env-quickdraw.yaml` to a new file
2. Edit the configuration for your application
3. Save as `projects/configs/your-project.yaml`

---

## Project Discovery

For existing ADO projects, you can auto-discover configuration from stories:

```bash
python3 workflows_generic.py discover \
  --story-ids 12345 12346 12347 \
  --project-name mediapedia-us
```

This will:
1. Fetch the specified stories from ADO
2. Analyze story content to detect:
   - Application type (web/desktop/mobile)
   - UI surfaces mentioned
   - Platforms referenced
   - Object interaction patterns
3. Generate a project configuration file
4. Report confidence level

**Tip**: Provide 3-5 diverse stories for best results.

---

## Using Projects

### Generate Test Cases

```bash
# Using default project
python3 workflows_generic.py generate --story-id 272889

# Using specific project
python3 workflows_generic.py generate --story-id 12345 --project mediapedia-us

# Skip LLM correction
python3 workflows_generic.py generate --story-id 12345 --project mediapedia-us --skip-correction
```

### Upload Test Cases

```bash
# Upload with auto test suite creation (default)
python3 workflows_generic.py upload --story-id 12345 --project mediapedia-us

# Preview without uploading
python3 workflows_generic.py upload --story-id 12345 --project mediapedia-us --dry-run

# Fail if no test suite exists (no auto-create)
python3 workflows_generic.py upload --story-id 12345 --project mediapedia-us --no-auto-create-suite
```

---

## Auto Test Suite Creation

For projects without pre-existing test suites (like MediaPedia), the framework can automatically create them.

### How It Works

1. When you run `upload`, the framework searches for a test suite matching `{story_id} : ...`
2. If not found and `--auto-create-suite` is enabled (default):
   - Creates a test plan named `{App Name} Test Plan`
   - Creates a test suite named `{story_id} : {story_title}`
   - Adds test cases to the new suite
3. Subsequent uploads to the same story use the existing suite

### Projects Without QA Prep

Set `qa_prep_pattern: null` in your config:

```yaml
ado:
  qa_prep_pattern: null  # Disables QA Prep lookup
```

When QA Prep is disabled:
- The framework generates testing guidance from the story content
- Edge cases are inferred from acceptance criteria
- Platform tests are based on project configuration

---

## MCP Integration

The framework includes an MCP (Model Context Protocol) server for AI assistant integration.

### Available Tools

| Tool | Description |
|------|-------------|
| `list_projects` | List all available projects |
| `get_project_config` | Get project configuration details |
| `create_project` | Create a new project configuration |
| `discover_project` | Discover config from ADO stories |
| `generate_test_cases` | Generate test cases for a story |
| `upload_test_cases` | Generate and upload to ADO |
| `analyze_story` | Analyze story test requirements |

### Starting the MCP Server

```bash
python -m mcp.server
```

### Claude Desktop Integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ai-test-gen": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "/path/to/test_gen",
      "env": {
        "ADO_PAT": "your_pat_here",
        "OPENAI_API_KEY": "your_key_here"
      }
    }
  }
}
```

---

## Migration from Single Project

If you were using the original `workflows.py` for ENV QuickDraw:

### Option 1: Keep Using Original

The original `workflows.py` still works and uses the ENV QuickDraw configuration.

```bash
# This still works
python3 workflows.py generate --story-id 272889
```

### Option 2: Use Generic Workflows

The new `workflows_generic.py` defaults to ENV QuickDraw when no project is specified:

```bash
# Same result as original
python3 workflows_generic.py generate --story-id 272889
```

### Option 3: Explicit Project Selection

Be explicit about which project you're using:

```bash
python3 workflows_generic.py generate --story-id 272889 --project env-quickdraw
```

---

## Project Directory Structure

```
projects/
├── __init__.py              # Package exports
├── project_config.py        # Configuration dataclasses
├── project_manager.py       # Project loading/switching
├── discovery.py             # Application discovery
├── test_suite_creator.py    # Auto test suite creation
└── configs/
    ├── env-quickdraw.yaml   # ENV QuickDraw (original)
    └── mediapedia-us.yaml   # MediaPedia US (example)
```

---

## Environment Variables

These environment variables can be used as defaults:

| Variable | Description |
|----------|-------------|
| `ADO_ORG` | Azure DevOps organization |
| `ADO_PROJECT` | Azure DevOps project name |
| `ADO_PAT` | Personal Access Token |
| `ADO_AREA_PATH` | Default area path |
| `ASSIGNED_TO` | Default assignee email |
| `OPENAI_API_KEY` | OpenAI API key for LLM |
| `APP_NAME` | Default application name |

---

## Best Practices

1. **Use descriptive project IDs**: `mediapedia-us`, `env-quickdraw-v2`, `myapp-staging`

2. **Keep configs in version control**: Track `projects/configs/*.yaml` files

3. **Use discovery for new projects**: Let the tool analyze stories first, then refine

4. **Test with dry-run**: Always preview uploads with `--dry-run` first

5. **Document entry points**: Keep `entry_point_mappings` comprehensive for accurate test generation
