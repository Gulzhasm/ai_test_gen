# QA Tester Onboarding Guide

This guide helps QA testers set up and use the Test Generation framework with GitHub Copilot.

---

## Quick Start Checklist

- [ ] 1. Open project in VS Code
- [ ] 2. Activate virtual environment
- [ ] 3. Start MCP server in VS Code
- [ ] 4. Use Copilot Chat to generate tests

---

## Setup (One-Time)

### 1. Open Project in VS Code

```bash
cd /path/to/test_gen
code .
```

### 2. Activate Virtual Environment

```bash
source venv310/bin/activate
```

### 3. Start MCP Server

1. Open `.vscode/mcp.json` in VS Code
2. Click the **"Start"** button that appears above the file
3. The MCP server is now running

---

## Daily Usage with GitHub Copilot

### Open Copilot Chat

1. Click the Copilot icon in VS Code title bar
2. Select **Agent** mode from the dropdown
3. Ask in natural language:

### Generate Tests (Workflow 1)

```
"generate tests for story 272889"
```

This saves files to `output/`:
- `272889_..._HYBRID_TESTS.csv` - ADO import-ready
- `272889_..._HYBRID_OBJECTIVES.txt` - Formatted objectives
- `272889_..._HYBRID_DEBUG.json` - Debug data

### Upload Tests to ADO (Workflow 2)

```
"upload tests for story 272889"
```

Preview first with dry run:
```
"upload tests for story 272889 with dry_run=true"
```

### Check Story Details (Workflow 3)

```
"check story 272889"
"what are the acceptance criteria for story 272889?"
```

### Other Commands

```
"list projects"
"generate tests for story 12345 in mediapedia-us project"
```

---

## CLI Alternative

If MCP isn't available, use the command line:

```bash
# Activate environment
source venv310/bin/activate

# Generate tests
python mcp_server.py 272889

# Generate for different project
python mcp_server.py 12345 mediapedia-us

# Full workflow commands
python workflows.py generate --story-id 272889
python workflows.py upload --story-id 272889 --dry-run
```

---

## MCP Tools Reference

| What You Want | What to Say in Copilot |
|---------------|------------------------|
| Generate tests (local only) | "generate tests for story 272889" |
| Generate + Upload to ADO | "upload tests for story 272889" |
| Preview before upload | "upload tests with dry_run=true" |
| Check story details | "check story 272889" |
| List available projects | "list projects" |
| Use different project | "generate tests in mediapedia-us" |

---

## Output Files

After generating tests, find files in `output/`:

| File | Purpose |
|------|---------|
| `*_TESTS.csv` | Import into ADO |
| `*_OBJECTIVES.txt` | Test objectives with HTML |
| `*_DEBUG.json` | Full data for debugging |

---

## Creating New Project Configuration

If you're working with a new application:

```bash
python setup_project.py create
```

Follow the prompts to configure:
- Application name and type
- ADO organization and project
- Area path and assignee
- Unavailable features (prevents impossible tests)

---

## Troubleshooting

### MCP tools not appearing in Copilot

1. Check VS Code version is 1.102+
2. Open `.vscode/mcp.json` and click "Start"
3. Restart VS Code
4. Use **Agent** mode in Copilot Chat

### "Story not found" error

- Verify the story ID exists in Azure DevOps
- Check `ADO_PAT` token is valid and not expired
- Ensure `ADO_ORG` and `ADO_PROJECT` are correct in `.env`

### "Module not found" error

```bash
source venv310/bin/activate
pip install -r requirements.txt
```

### "MCP not installed" error

```bash
source venv310/bin/activate
pip install mcp
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│           TEST GENERATION - COPILOT COMMANDS                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  GENERATE TESTS:                                            │
│    "generate tests for story 272889"                        │
│                                                             │
│  UPLOAD TO ADO:                                             │
│    "upload tests for story 272889"                          │
│                                                             │
│  PREVIEW (DRY RUN):                                         │
│    "upload tests for story 272889 with dry_run=true"        │
│                                                             │
│  CHECK STORY:                                               │
│    "check story 272889"                                     │
│                                                             │
│  LIST PROJECTS:                                             │
│    "list projects"                                          │
│                                                             │
│  DIFFERENT PROJECT:                                         │
│    "generate tests for story 12345 in mediapedia-us"        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Getting Help

- **Documentation**: See `README.md`
- **Issues**: Contact your tech lead
- **Logs**: Check terminal output for error details
