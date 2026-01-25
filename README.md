# AI-Driven Test Case Generation Framework

A production-ready framework for automatically generating test cases from Azure DevOps user stories. Integrates with **GitHub Copilot via MCP** (Model Context Protocol) for AI-assisted test generation.

---

## Quick Start

### 1. Setup

```bash
# Create virtual environment (Python 3.10 required for spaCy)
python3.10 -m venv venv310
source venv310/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your ADO_PAT and OPENAI_API_KEY
```

### 2. Generate Tests (CLI)

```bash
python mcp_server.py 272889
```

### 3. Use with GitHub Copilot (MCP)

1. Open [.vscode/mcp.json](.vscode/mcp.json) in VS Code
2. Click **"Start"** button to start MCP server
3. In Copilot Chat (Agent mode): `"generate tests for story 272889"`

---

## MCP Tools (GitHub Copilot)

| Tool | Description | Example |
|------|-------------|---------|
| `generate_tests` | Generate tests and save to output folder | "generate tests for story 272889" |
| `upload_tests` | Generate AND upload to ADO test suite | "upload tests for story 272889" |
| `check_story` | Get story details from ADO | "check story 272889" |
| `list_projects` | List available projects | "list projects" |

### MCP Configuration

The MCP server is configured in [.vscode/mcp.json](.vscode/mcp.json):

```json
{
  "servers": {
    "test-gen": {
      "type": "stdio",
      "command": "/path/to/venv310/bin/python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
```

---

## Workflows

### Workflow 1: Generate Tests

Generate test cases locally (saves CSV, objectives, JSON to `output/`).

```bash
# CLI
python mcp_server.py 272889

# MCP (Copilot)
"generate tests for story 272889"
```

**Output files:**
- `272889_..._HYBRID_TESTS.csv` - ADO-ready CSV
- `272889_..._HYBRID_OBJECTIVES.txt` - Objectives with HTML formatting
- `272889_..._HYBRID_DEBUG.json` - Full debug data

### Workflow 2: Upload Tests

Generate AND upload to ADO test suite (auto-creates suite if needed).

```bash
# CLI
python workflows.py upload --story-id 272889

# MCP (Copilot)
"upload tests for story 272889"
"upload tests for story 272889 with dry_run=true"  # Preview only
```

### Workflow 3: Check Story

Get story details and acceptance criteria from ADO.

```bash
# MCP (Copilot)
"check story 272889"
"what are the acceptance criteria for story 272889?"
```

---

## Multi-Project Support

### Available Projects

```bash
python setup_project.py list
```

| Project | Application |
|---------|-------------|
| `env-quickdraw` | ENV QuickDraw (default) |
| `mediapedia-us` | MediaPedia US |

### Using Different Projects

```bash
# CLI
python mcp_server.py 272889 mediapedia-us

# MCP (Copilot)
"generate tests for story 12345 in mediapedia-us project"
```

### Create New Project

```bash
python setup_project.py create
```

---

## Configuration

### Environment Variables (.env)

```bash
# Required
ADO_PAT=your_personal_access_token
ADO_ORG=your_organization
ADO_PROJECT=your_project

# Optional
OPENAI_API_KEY=sk-...  # For LLM correction
ADO_AREA_PATH=Project\\Team
ASSIGNED_TO=your.email@company.com
```

### Project Configuration

Projects are configured in `projects/configs/*.yaml`:

```yaml
project_id: my-app
application:
  name: My Application
  type: web
  prereq_template: "Pre-req: User has access to {app_name}"
  launch_step: "Navigate to {app_name}."
ado:
  organization: my-org
  project: MyProject
  area_path: "MyProject\\Team"
```

---

## Output Files

| File | Purpose |
|------|---------|
| `*_TESTS.csv` | ADO import-ready test cases |
| `*_OBJECTIVES.txt` | Formatted objectives (HTML) |
| `*_DEBUG.json` | Full data for debugging |

### CSV Format (ADO Import)

| Column | Description |
|--------|-------------|
| Title | `{story_id}-{test_id}: Feature / Area / Scenario` |
| TestStep | Step number |
| Step Action | What to do |
| Step Expected | Expected result |
| Area Path | ADO area path |

---

## Architecture

```
test_gen/
├── mcp_server.py          # MCP server + CLI entry point
├── workflows.py           # Full workflow engine
├── setup_project.py       # Project setup tool
│
├── core/                  # Domain layer
│   ├── interfaces/        # Abstractions
│   └── services/          # Test generation logic
│
├── infrastructure/        # External services
│   ├── ado/               # Azure DevOps client
│   └── export/            # CSV/Objective generators
│
├── projects/              # Multi-project support
│   └── configs/           # YAML configurations
│
├── llm/                   # LLM providers
├── output/                # Generated files
└── .vscode/
    └── mcp.json           # MCP configuration
```

---

## Troubleshooting

### MCP not working in Copilot
1. Check VS Code version is 1.102+
2. Open [.vscode/mcp.json](.vscode/mcp.json) and click "Start"
3. Use Agent mode in Copilot Chat

### "Story not found"
- Verify story ID exists in ADO
- Check `ADO_PAT` token is valid

### "MCP not installed"
```bash
source venv310/bin/activate
pip install mcp
```

---

## Version

**v4.0** - GitHub Copilot MCP integration with 3 main workflows.

### Recent Changes
- MCP server for GitHub Copilot integration
- 3 main workflows: generate, upload, check_story
- Simplified CLI: `python mcp_server.py <story_id>`
- Quality enhancement with LLM correction
- Multi-project YAML configuration
