# MCP Server Documentation

## Overview

The MCP (Model Context Protocol) Server exposes test generation workflows as tools available to GitHub Copilot and other AI assistants. It enables automated test case generation for Azure DevOps user stories without leaving your development environment.

**Location:** `integrations/mcp_server.py`

## Prerequisites

- Python 3.10+
- Required packages: `mcp` and project dependencies
- Azure DevOps Personal Access Token (PAT) in `.env` file
- VS Code with Copilot enabled

## Installation

### 1. Install MCP Package

```bash
pip install mcp
```

### 2. Verify Environment Variables

Ensure your `.env` file contains:

```bash
ADO_ORG=cdpinc                                    # Azure DevOps organization
ADO_PROJECT=Env                                   # ADO project name
ADO_PAT=your_personal_access_token                # ADO Personal Access Token
ADO_AREA_PATH=Env\ENV Kanda                       # ADO area path
ASSIGNED_TO=user@example.com                      # Default test assignee
```

### 3. Configure VS Code (`.mcp.json`)

The `.mcp.json` file in the workspace root configures how VS Code launches the MCP server:

```json
{
  "mcpServers": {
    "test-gen": {
      "command": "python3",
      "args": ["/Users/gulzhasmailybayeva/Desktop/test_gen/integrations/mcp_server.py"],
      "cwd": "/Users/gulzhasmailybayeva/Desktop/test_gen",
      "env": {
        "PYTHONPATH": "/Users/gulzhasmailybayeva/Desktop/test_gen"
      }
    }
  }
}
```

**Important:** Update the absolute path to match your workspace location.

## Running the MCP Server

### Via VS Code Copilot (Recommended)

The server starts automatically when you request test generation tools from Copilot. No manual startup needed.

### Manual Testing

```bash
cd /path/to/test_gen
python3 integrations/mcp_server.py
```

The server will wait for MCP protocol messages on stdin. Press `Ctrl+C` to stop.

## Available Commands/Tools

The MCP server exposes the following tools to Copilot:

### 1. Generate Tests

**Tool:** `mcp_test-gen_generate_tests`

Generates test cases from acceptance criteria without uploading to ADO.

**Parameters:**
- `story_id` (required): Azure DevOps work item ID (e.g., "272889")
- `project` (optional): Project configuration ID (default: "env-quickdraw")

**Example:**
```
Generate tests for story 272889
```

**Output Files:**
- `{story_id}_{title}_HYBRID_TESTS.csv` - Test cases in CSV format
- `{story_id}_{title}_HYBRID_OBJECTIVES.txt` - Test objectives
- `{story_id}_{title}_HYBRID_DEBUG.json` - Debug information

### 2. Upload Tests

**Tool:** `mcp_test-gen_upload_tests`

Generates test cases AND uploads them to ADO test suite.

**Parameters:**
- `story_id` (required): Azure DevOps work item ID
- `project` (optional): Project configuration ID
- `dry_run` (optional): Preview without uploading (default: false)

**Example:**
```
Generate and upload tests for story 272889
```

### 3. Check Story Details

**Tool:** `mcp_test-gen_check_story`

Retrieves story information from ADO including acceptance criteria.

**Parameters:**
- `story_id` (required): Azure DevOps work item ID
- `project` (optional): Project configuration ID

**Example:**
```
Get details for story 272889
```

**Output:**
Story title, description, and acceptance criteria

### 4. List Projects

**Tool:** `mcp_test-gen_list_projects`

Lists all available project configurations.

**Parameters:** None

**Example:**
```
List all available projects
```

**Output:**
```
- env-quickdraw (default)
- mediapedia-us
- example-enterprise-app
- example-mobile-app
- example-web-app
```

## Generation Modes

The test generator supports two modes:

### Rule-Based (Fast)
Generates tests purely from acceptance criteria using predefined rules. Takes ~10-30 seconds.

```bash
python3 workflows.py generate --story-id 272889 --skip-correction
```

### Hybrid (Default - Slower)
Combines rule-based generation with LLM refinement for better quality. Takes 2-5 minutes depending on test count.

```bash
python3 workflows.py generate --story-id 272889
```

## Troubleshooting

### Issue: "MCP server could not be started: Process exited with code 2"

**Causes:**
1. Python path issues
2. Missing imports
3. Environment variables not loaded

**Solutions:**

a) **Verify Python path in `.mcp.json`:**
```bash
# Check the path exists
ls -la /Users/gulzhasmailybayeva/Desktop/test_gen/integrations/mcp_server.py

# Update if needed (use absolute path)
```

b) **Test server manually:**
```bash
cd /Users/gulzhasmailybayeva/Desktop/test_gen
python3 integrations/mcp_server.py
# Should not error immediately (waits for MCP input)
```

c) **Check dependencies:**
```bash
pip install -r requirements.txt
pip install mcp
```

d) **Verify environment variables:**
```bash
# Check .env file exists and has required vars
cat .env | grep -E "ADO_|ASSIGNED_TO"
```

### Issue: "Story not found"

**Causes:**
1. Story ID doesn't exist in ADO
2. Story has no acceptance criteria
3. Wrong project selected

**Solutions:**

a) **Verify story exists:**
```bash
# Check in ADO directly
# URL: https://dev.azure.com/{ORG}/{PROJECT}/_workitems/edit/{STORY_ID}
```

b) **Check story has acceptance criteria:**
```bash
# Story must have at least one acceptance criterion
# Or error: "Story must have acceptance criteria"
```

c) **Try with explicit project:**
```bash
python3 workflows.py --project env-quickdraw generate --story-id 272889
```

### Issue: Command hangs or times out

**Causes:**
1. LLM API call timeout (network issue)
2. ADO API connectivity
3. Large number of acceptance criteria

**Solutions:**

a) **Skip LLM correction (faster):**
```bash
python3 workflows.py generate --story-id 272889 --skip-correction
```

b) **Check network connectivity:**
```bash
# Test ADO access
curl -I https://dev.azure.com/

# Test OpenAI API (if using gpt-4o-mini)
curl -I https://api.openai.com/
```

c) **Check LLM configuration in `.env`:**
```bash
# Verify LLM provider credentials
grep -E "OPENAI_API_KEY|ANTHROPIC_API_KEY" .env
```

### Issue: "organization" or "project" attribute error

**Cause:** Project configuration incomplete or using placeholder values

**Solution:**

a) **Check project config YAML:**
```bash
cat projects/configs/env-quickdraw.yaml
# Look for "ado:" section with organization and project
```

b) **Ensure env vars are set:**
```bash
export ADO_ORG=cdpinc
export ADO_PROJECT=Env
export ADO_PAT=your_token
```

c) **Reload environment:**
```bash
# In same shell session where you'll run the script
source .env
python3 workflows.py generate --story-id 272889
```

### Issue: Output files not created

**Cause:** Generation failed silently or incomplete

**Solutions:**

a) **Check output directory exists:**
```bash
mkdir -p output
ls -la output/
```

b) **Run with verbose output:**
```bash
python3 workflows.py generate --story-id 272889 2>&1 | tee generation.log
# Review generation.log for errors
```

c) **Check for partial files:**
```bash
ls -la output/ | grep 272889
# Look for partial generation files
```

## Configuration Files

### Project Configuration (`projects/configs/*.yaml`)

Each project has a YAML configuration defining:
- Application name and type
- UI surfaces and entry points
- Supported platforms
- ADO organization/project
- Test generation rules

**Example:**
```yaml
project_id: env-quickdraw
application:
  name: ENV QuickDraw
  type: desktop
  platforms:
    - Windows 11
    - macOS
    - iPad
ado:
  organization: cdpinc
  project: Env
  area_path: Env\ENV Kanda
```

### Environment Variables (`.env`)

```bash
# Azure DevOps
ADO_ORG=cdpinc
ADO_PROJECT=Env
ADO_PAT=personal_access_token
ADO_AREA_PATH=Env\ENV Kanda
ASSIGNED_TO=user@example.com

# LLM (Optional)
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
```

## Examples

### Generate Tests via Copilot

In VS Code, open Copilot chat and type:
```
@mcp generate tests for story 272889
```

Copilot will call the MCP tool and show results.

### Generate Tests via Command Line

```bash
# Generate for default project (env-quickdraw)
python3 workflows.py generate --story-id 272889

# Generate for specific project
python3 workflows.py --project mediapedia-us generate --story-id 12345

# Skip LLM correction (faster)
python3 workflows.py generate --story-id 272889 --skip-correction
```

### Upload to ADO

```bash
# Generate and upload
python3 workflows.py upload --story-id 272889

# Preview upload without committing
python3 workflows.py upload --story-id 272889 --dry-run
```

## Performance Tips

1. **Use rule-based mode for quick testing:**
   ```bash
   python3 workflows.py generate --story-id 272889 --skip-correction
   ```

2. **Batch generate multiple stories:**
   ```bash
   for story in 272889 272779 272780; do
     python3 workflows.py generate --story-id $story &
   done
   wait
   ```

3. **Monitor LLM costs:**
   - Check OpenAI/Anthropic usage after large batches
   - Consider setting LLM_ENABLED=false in .env for cost control

## Additional Resources

- **MCP Protocol:** https://modelcontextprotocol.io/
- **Azure DevOps API:** https://learn.microsoft.com/en-us/rest/api/azure/devops/
- **Project Documentation:** See `docs/` folder for guides and masters thesis

## Support

For issues not covered in troubleshooting:

1. Check `output/` directory for generated files (they may have been created despite errors)
2. Review error logs in terminal output
3. Check `.env` file is properly configured
4. Verify Python environment: `python3 --version` (should be 3.10+)
5. Run test suite: `pytest tests/` to validate core functionality
