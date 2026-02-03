# AI-Powered Test Case Generation Framework

Generate high-quality test cases from Azure DevOps user stories automatically using AI.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start (5 minutes)](#quick-start-5-minutes)
3. [Docker Setup (Recommended)](#docker-setup-recommended)
4. [CLI Commands](#cli-commands)
5. [Adding Your Project](#adding-your-project)
6. [Configuration Reference](#configuration-reference)
7. [Output Files](#output-files)
8. [MCP Integration (GitHub Copilot)](#mcp-integration-github-copilot)
9. [Architecture](#architecture)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This framework automatically generates comprehensive test cases by:

1. **Reading** user stories and acceptance criteria from Azure DevOps
2. **Understanding** your application context from project configuration (YAML)
3. **Generating** test cases using AI (acts as an expert QA engineer with 10+ years experience)
4. **Correcting** test quality with LLM enhancement
5. **Exporting** to ADO-compatible CSV format or uploading directly

### Key Features

- **Project-agnostic**: Works with any application (desktop, web, mobile, hybrid)
- **AI-powered**: Uses GPT-4 to generate human-quality test cases
- **Context-aware**: Generates relevant tests based on feature type (no input tests for menus!)
- **Multi-platform**: Generates accessibility tests for all supported platforms
- **ADO Integration**: Direct upload to Azure DevOps test suites

---

## Quick Start (5 minutes)

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd test_gen

# Create virtual environment (Python 3.10 required)
python3.10 -m venv venv310
source venv310/bin/activate  # On Windows: venv310\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
```

**Required environment variables:**

```bash
# Azure DevOps (Required)
ADO_PAT=your_personal_access_token_here

# OpenAI API (Required for LLM correction)
OPENAI_API_KEY=sk-your-api-key-here
```

### Step 3: Generate Your First Tests

```bash
# List available projects
python workflows.py list-projects

# Generate tests for a story
python workflows.py generate --story-id 272889
```

**Output:** Test cases saved to `output/` folder as CSV, JSON, and objectives files.

---

## Docker Setup (Recommended)

Docker provides a consistent environment across all team members - no Python version conflicts or dependency issues.

### Prerequisites

1. Install [Docker Desktop](https://docs.docker.com/desktop/)
2. Get the `.env` file (contains ADO/OpenAI credentials)

### Quick Start with Docker

```bash
# 1. Build the image (first time only, ~3 min)
docker build -t test-gen:v1 .

# 2. Verify it works
docker run test-gen:v1 --help

# 3. Run with credentials and output volume
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 generate --story-id 272889
```

### Common Docker Commands

```bash
# Generate test cases
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 generate --story-id 272889

# Generate + Upload to ADO (dry run)
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 upload --story-id 272889 --dry-run

# Generate + Upload to ADO (live)
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 upload --story-id 272889

# List projects
docker run test-gen:v1 list-projects

# Update objectives
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 update-objectives --story-id 272889
```

### Shell Alias (Optional)

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias testgen='docker run --env-file .env -v $(pwd)/output:/app/output test-gen:v1'

# Then simply run:
# testgen generate --story-id 272889
# testgen upload --story-id 272889 --dry-run
```

### Docker vs Local Python

| Aspect | Docker | Local Python |
|--------|--------|--------------|
| Setup time | ~3 min (one command) | ~10 min (venv, pip, spacy model) |
| Works on | Any machine with Docker | Requires Python 3.10 |
| Dependencies | Isolated in container | May conflict with other projects |
| Team consistency | Identical for everyone | "Works on my machine" issues |

### Rebuilding After Code Changes

```bash
# If you modify the code, rebuild the image
docker build -t test-gen:v1 .

# Docker caches layers, so rebuilds are fast if only code changed
```

---

## CLI Commands

All commands use: `python workflows.py <command> [options]`

For detailed CLI documentation, see [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md).

### Quick Reference

| Command | Description | Example |
|---------|-------------|---------|
| `list-projects` | Show all configured projects | `python workflows.py list-projects` |
| `generate` | Generate test cases locally | `python workflows.py generate --story-id 272889` |
| `upload` | Generate AND upload to ADO | `python workflows.py upload --story-id 272889` |
| `upload-existing` | Upload existing tests to ADO | `python workflows.py upload-existing --story-id 272889` |
| `init-project` | Create new project config | `python workflows.py init-project --name "MyApp"` |
| `discover` | Auto-discover project settings | `python workflows.py discover --story-ids 123 456` |

### Common Examples

```bash
# 1. List available projects
python workflows.py list-projects

# 2. Generate tests (saves to output/ folder)
python workflows.py generate --story-id 272889

# 3. Generate tests for specific project
python workflows.py generate --story-id 272889 --project mediapedia-us

# 4. Generate tests WITHOUT LLM correction (faster)
python workflows.py generate --story-id 272889 --skip-correction

# 5. Generate AND upload to Azure DevOps
python workflows.py upload --story-id 272889

# 6. Preview upload without actually uploading (dry run)
python workflows.py upload --story-id 272889 --dry-run

# 7. Upload EXISTING tests (skip generation, use files in output/)
python workflows.py upload-existing --story-id 272889

# 8. Initialize a new project
python workflows.py init-project --name "MyApp" --org myorg --ado-project MyProject
```

---

## Adding Your Project

### Step 1: Copy Example Configuration

```bash
cp projects/configs/example-web-app.yaml projects/configs/my-project.yaml
```

### Step 2: Edit Configuration

Open `projects/configs/my-project.yaml` and customize:

```yaml
project_id: my-project  # Unique identifier

application:
  name: My Application
  description: Description of your app
  type: web  # Options: desktop, web, mobile, hybrid

  # Test step templates (use {app_name} as placeholder)
  prereq_template: "Pre-req: User is logged into {app_name}"
  launch_step: "Navigate to {app_name} homepage."
  launch_expected: "Homepage loads with navigation menu visible."
  close_step: "Log out from {app_name}"

  # UI areas in your application (used for test titles)
  ui_surfaces:
    - Dashboard
    - Navigation Menu
    - Settings Page
    - User Profile
    - Modal Dialog

  # How users access features (keyword -> UI location)
  entry_point_mappings:
    search: Navigation Menu
    settings: User Profile
    export: Dashboard
    import: Dashboard

  # Platforms your app supports (generates accessibility tests)
  platforms:
    - Windows 11
    - Chrome (macOS)
    - Safari (iOS)

  # IMPORTANT: Features your app does NOT support
  # Prevents generating impossible test scenarios
  unavailable_features:
    - offline mode
    - multi-select
    - bulk delete

# Azure DevOps settings
ado:
  organization: your-org
  project: YourProject
  area_path: "YourProject\\QA Team"
  assigned_to: qa-engineer@company.com
  default_state: Design

# Test generation rules
rules:
  forbidden_words:
    - "or / OR"
    - "if available"
    - "if supported"

  allowed_areas:
    - Dashboard
    - Navigation Menu
    - Settings Page

# LLM settings
llm_enabled: true
llm_model: gpt-4o-mini
```

### Step 3: Set as Default (Optional)

In `.env`, set your project as default:

```bash
DEFAULT_PROJECT=my-project
```

### Step 4: Test Configuration

```bash
# Verify project loads correctly
python workflows.py list-projects

# Test with a story
python workflows.py generate --story-id 123456 --project my-project
```

---

## Configuration Reference

### Application Types

| Type | Description | Example |
|------|-------------|---------|
| `desktop` | Native desktop apps (Windows, macOS) | CAD software, IDEs |
| `web` | Browser-based applications | SaaS platforms, dashboards |
| `mobile` | iOS/Android apps | Mobile banking, social apps |
| `hybrid` | Cross-platform/enterprise apps | CRM systems, enterprise tools |

### Platform Support

The framework generates platform-specific accessibility tests:

| Platform | Accessibility Tool | Test Type |
|----------|-------------------|-----------|
| Windows 11 | Accessibility Insights | Keyboard navigation |
| macOS | VoiceOver | Keyboard + screen reader |
| iPad/iOS | VoiceOver | Swipe gestures |
| Android | Accessibility Scanner | Touch + TalkBack |
| Chrome/Web | Screen reader (NVDA/JAWS) | ARIA, keyboard |

### Feature Type Detection

The framework automatically detects feature types and generates appropriate tests:

| Feature Type | Generates | Does NOT Generate |
|--------------|-----------|-------------------|
| Navigation (menus) | Visibility, keyboard access | Input validation, boundaries |
| Input (forms) | Validation, boundaries, errors | N/A |
| Display (viewers) | Content display, formatting | Input tests |
| Object manipulation | Undo/redo, state changes | Multi-select (if unavailable) |

---

## Output Files

After running `generate`, files are saved to `output/`:

| File | Description | Use Case |
|------|-------------|----------|
| `*_HYBRID_TESTS.csv` | ADO-compatible test cases | Import to Azure DevOps |
| `*_HYBRID_OBJECTIVES.txt` | Test objectives with HTML | Copy to test case objectives |
| `*_HYBRID_DEBUG.json` | Full generation data | Debugging, review |

### CSV Format

The CSV follows Azure DevOps import format:

| Column | Description |
|--------|-------------|
| ID | Leave empty (ADO assigns) |
| Work Item Type | Always "Test Case" |
| Title | `{StoryID}-{TestID}: Feature / Area / Scenario` |
| TestStep | Step number (1, 2, 3...) |
| Step Action | What to do |
| Step Expected | Expected result |
| Area Path | ADO area path |
| AssignedTo | QA engineer email |
| State | Default: "Design" |

---

## MCP Integration (GitHub Copilot)

Use the framework directly from GitHub Copilot Chat.

### Setup

1. Open `.vscode/mcp.json` in VS Code
2. Click **"Start"** button to launch MCP server
3. In Copilot Chat, use **Agent mode** (@workspace)

### Commands

```
"generate tests for story 272889"
"upload tests for story 272889"
"check story 272889"
"list projects"
```

### MCP Configuration

Edit `.vscode/mcp.json`:

```json
{
  "servers": {
    "test-gen": {
      "type": "stdio",
      "command": "/path/to/venv310/bin/python",
      "args": ["/path/to/integrations/mcp_server.py"]
    }
  }
}
```

---

## Architecture

The project follows **Clean Architecture** principles with all business logic centralized in `core/`.

```
test_gen/
├── workflows.py              # Main CLI entry point
├── requirements.txt          # Python dependencies
├── .env                      # Environment configuration
│
├── projects/                 # Multi-project support
│   ├── configs/              # YAML project configurations
│   │   ├── env-quickdraw.yaml
│   │   ├── example-web-app.yaml
│   │   └── my-project.yaml
│   ├── project_config.py     # Configuration loader
│   └── project_manager.py    # Project management
│
├── core/                     # ALL business logic (Clean Architecture)
│   ├── config/               # App configuration
│   │   └── environment.py    # Environment variables
│   ├── domain/               # Domain models
│   │   └── models.py         # UserStory, TestCase, etc.
│   └── services/             # ALL services centralized here
│       ├── test_generator.py # Main test generation
│       ├── objective_service.py  # Objective generation
│       ├── summary_service.py    # QA summary generation
│       ├── nlp/              # NLP parsing (spaCy)
│       │   ├── spacy_parser.py
│       │   └── hybrid_parser.py
│       ├── quality/          # Quality analysis
│       │   ├── quality_analyzer.py
│       │   └── test_corrector.py
│       ├── linting/          # Evidence-based linting
│       │   ├── summary_linter.py
│       │   └── objective_linter.py
│       └── llm/              # LLM providers & prompts
│           ├── corrector.py      # Test case correction
│           ├── prompt_builder.py # Dynamic prompt generation
│           ├── openai_provider.py
│           └── anthropic_provider.py
│
├── infrastructure/           # External services (adapters)
│   ├── ado/                  # Azure DevOps client
│   │   └── ado_repository.py # ADO API wrapper
│   └── export/               # Export generators
│       ├── csv_generator.py
│       └── objective_generator.py
│
├── integrations/             # External tool integrations
│   └── mcp_server.py         # GitHub Copilot MCP server
│
├── scripts/                  # Utility scripts
│   └── setup_project.py      # Project setup tool
│
├── tests/                    # Unit tests
│
└── output/                   # Generated files
    └── *.csv, *.json, *.txt
```

---

## Troubleshooting

### "Story not found"

- Verify story ID exists in Azure DevOps
- Check `ADO_PAT` token has read permissions
- Ensure ADO organization/project in config matches story location

### "OPENAI_API_KEY not configured"

- Add `OPENAI_API_KEY=sk-...` to `.env` file
- Ensure key is valid and has credits

### "Project not found"

- Run `python workflows.py list-projects` to see available projects
- Check YAML file exists in `projects/configs/`
- Verify `project_id` in YAML matches what you're using

### LLM correction takes too long

- Use `--skip-correction` flag for faster generation (lower quality)
- Consider using `gpt-4o-mini` instead of `gpt-4o` in config

### MCP not working in Copilot

1. Ensure VS Code version is 1.102+
2. Open `.vscode/mcp.json` and click "Start"
3. Use **Agent mode** in Copilot Chat
4. Try: `@workspace generate tests for story 272889`

### Python version issues

```bash
# Check Python version (3.10 required for spaCy)
python --version

# If wrong version, create venv with specific Python
python3.10 -m venv venv310
```

### Import errors

```bash
# Ensure venv is activated
source venv310/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Docker Issues

**"Cannot connect to Docker daemon"**
- Ensure Docker Desktop is running (check system tray/menu bar)

**"No such file: .env"**
- Copy `.env` file to project root: `cp /path/to/.env .`
- Never commit `.env` to git

**"Permission denied" on output folder**
```bash
sudo chown -R $(whoami) output/
```

**Need to debug inside container?**
```bash
docker run -it --entrypoint /bin/bash test-gen:v1
# Now you're inside the container
```

**Container runs but can't connect to ADO**
- Verify `.env` has correct `ADO_PAT` value
- Check `--env-file .env` flag is included in command

---

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review example configurations in `projects/configs/`
3. Check existing test output in `output/` for reference

---

## Version

**v5.1** - Docker support + Multi-project AI test generation

### Recent Changes
- **Docker support** for consistent team environments
- Project-agnostic framework with YAML configuration
- Enhanced LLM prompts (expert QA engineer persona)
- `update-objectives` workflow now fetches directly from ADO (no CSV required)
- Reorganized codebase structure
- Comprehensive documentation
