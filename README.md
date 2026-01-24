# Test Case Generation Framework

## Quick Start - CLI Commands

```bash
# WORKFLOW 1: Generate test cases (rule-based + LLM correction)
python3 workflows.py generate --story-id 272889

# WORKFLOW 1: Generate test cases (rule-based only, no LLM)
python3 workflows.py generate --story-id 273166 --skip-correction

# WORKFLOW 2: Generate + Upload to ADO test suite
python3 workflows.py upload --story-id 272889

# WORKFLOW 2: Preview upload without actually uploading
python3 workflows.py upload --story-id 272889 --dry-run

# WORKFLOW 3: Update objectives for existing test cases
python3 workflows.py update-objectives --csv output/exported_from_ado.csv --objectives output/272889_OBJECTIVES.txt

# WORKFLOW 3: Preview objective updates
python3 workflows.py update-objectives --csv output/exported.csv --objectives output/objectives.txt --dry-run
```

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Architecture](#architecture)
5. [Workflows](#workflows)
   - [Workflow 1: Generate](#workflow-1-generate)
   - [Workflow 2: Upload](#workflow-2-upload)
   - [Workflow 3: Update Objectives](#workflow-3-update-objectives)
6. [Output Files](#output-files)
7. [Configuration](#configuration)
8. [Quality Rules](#quality-rules)
9. [Troubleshooting](#troubleshooting)
10. [Project Structure](#project-structure)

---

## Overview

This framework automates test case generation for Azure DevOps (ADO). It:

1. **Fetches** story data from ADO (acceptance criteria, QA prep)
2. **Generates** comprehensive test cases using rule-based logic
3. **Corrects** test cases using LLM (optional, for quality enhancement)
4. **Uploads** test cases to ADO test suites with formatted objectives

### Key Features

- **Rule-based generation**: Fast, deterministic test case creation
- **LLM correction**: Optional enhancement using GPT-4o-mini
- **Strict suite matching**: Only uploads to `{story_id} : {name}` pattern
- **1:1 objective mapping**: Each test case has a formatted objective
- **ADO-ready output**: CSV format compatible with ADO import

---

## Prerequisites

- Python 3.7+
- Azure DevOps Personal Access Token (PAT)
- OpenAI API key (optional, for LLM correction)

### Required Python Packages

```bash
pip install requests beautifulsoup4 python-dotenv openai
```

---

## Installation

1. **Clone/download** the project

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   # Or manually:
   pip install requests beautifulsoup4 python-dotenv openai
   ```

3. **Create `.env` file** in project root:
   ```bash
   ADO_PAT=your_ado_personal_access_token
   OPENAI_API_KEY=your_openai_api_key  # Optional
   ```

4. **Verify setup**:
   ```bash
   python3 workflows.py --help
   ```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      workflows.py                           │
│                   (Single Entry Point)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │  Generate   │  │   Upload    │  │ Update Objectives│   │
│  │  Workflow   │  │  Workflow   │  │    Workflow      │   │
│  └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘   │
│         │                │                   │             │
├─────────┴────────────────┴───────────────────┴─────────────┤
│                    IWorkflow Interface                      │
│              (validate_inputs, execute)                     │
├─────────────────────────────────────────────────────────────┤
│                    WorkflowEngine                           │
│              (registers and orchestrates)                   │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ ADO Client  │    │ Generators  │    │   Config    │
   │ (API calls) │    │ (test logic)│    │  (settings) │
   └─────────────┘    └─────────────┘    └─────────────┘
```

### Design Principles

- **Single entry point**: All workflows through `workflows.py`
- **Interface-based**: `IWorkflow` defines contract for all workflows
- **Clean separation**: Each workflow is independent and testable
- **Fail-fast**: Validation before execution

---

## Workflows

### Workflow 1: Generate

**Purpose**: Generate test cases locally without uploading to ADO.

**Command**:
```bash
python3 workflows.py generate --story-id <STORY_ID> [--skip-correction] [--output-dir <DIR>]
```

**Options**:
| Option | Description |
|--------|-------------|
| `--story-id` | Required. ADO story ID (e.g., 272889) |
| `--skip-correction` | Skip LLM correction, use rule-based only |
| `--output-dir` | Output directory (default: `output`) |

**Examples**:
```bash
# With LLM correction (recommended)
python3 workflows.py generate --story-id 272889

# Without LLM (faster, rule-based only)
python3 workflows.py generate --story-id 272889 --skip-correction

# Custom output directory
python3 workflows.py generate --story-id 272889 --output-dir ./my_tests
```

**Output Files**:
```
output/
├── 272889_Feature_Name_HYBRID_TESTS.csv       # Test cases (ADO-ready)
├── 272889_Feature_Name_HYBRID_OBJECTIVES.txt  # Formatted objectives
└── 272889_Feature_Name_HYBRID_DEBUG.json      # Debug data
```

**Process**:
```
Story ID → Fetch from ADO → Rule-based generation → LLM correction → Save files
```

---

### Workflow 2: Upload

**Purpose**: Generate test cases AND upload to ADO test suite.

**IMPORTANT**: Only uploads to test suite matching pattern `{story_id} : {name}`

**Command**:
```bash
python3 workflows.py upload --story-id <STORY_ID> [--dry-run] [--skip-correction] [--output-dir <DIR>]
```

**Options**:
| Option | Description |
|--------|-------------|
| `--story-id` | Required. ADO story ID |
| `--dry-run` | Preview mode, no actual uploads |
| `--skip-correction` | Skip LLM correction |
| `--output-dir` | Output directory (default: `output`) |

**Examples**:
```bash
# Full upload (generate + upload)
python3 workflows.py upload --story-id 272889

# Preview what would be uploaded
python3 workflows.py upload --story-id 272889 --dry-run

# Upload without LLM correction
python3 workflows.py upload --story-id 272889 --skip-correction
```

**Test Suite Requirement**:

The workflow **requires** a test suite with name pattern:
```
{story_id} : {story_name}
```

Example: `272889 : Object Transformation Tools (Rotate & Mirror)`

If no matching suite is found, the workflow **fails** with an error.

**Process**:
```
Story ID → Find test suite → Fail if not found → Generate tests → Upload → Add to suite
```

---

### Workflow 3: Update Objectives

**Purpose**: Update Summary/Objective field for existing test cases in ADO.

**Use Case**: When test cases are already uploaded but objectives need updating.

**Command**:
```bash
python3 workflows.py update-objectives --csv <CSV_FILE> --objectives <OBJECTIVES_FILE> [--dry-run]
```

**Options**:
| Option | Description |
|--------|-------------|
| `--csv` | Required. CSV file exported from ADO (has work item IDs) |
| `--objectives` | Required. Objectives TXT file (1:1 mapped) |
| `--dry-run` | Preview mode, no actual updates |

**Examples**:
```bash
# Update objectives
python3 workflows.py update-objectives \
  --csv output/272889_exported_from_ado.csv \
  --objectives output/272889_OBJECTIVES.txt

# Preview updates
python3 workflows.py update-objectives \
  --csv output/272889_exported.csv \
  --objectives output/272889_OBJECTIVES.txt \
  --dry-run
```

**Required CSV Format** (exported from ADO after upload):
```csv
ID,Work Item Type,Title,...
278255,Test Case,272889-AC1: Feature / Area / Scenario,...
278256,Test Case,272889-005: Feature / Area / Scenario,...
```

The `ID` column must contain ADO work item IDs.

**Required Objectives Format**:
```
272889-AC1: Feature / Area / Scenario
<b>Objective:</b> Verify that ...

272889-005: Feature / Area / Scenario
<b>Objective:</b> Verify that ...
```

**Process**:
```
CSV → Extract ADO IDs → Match with objectives → Update Summary field in ADO
```

---

## Output Files

### CSV File (`*_TESTS.csv`)

ADO-ready format for test case import:

| Column | Description |
|--------|-------------|
| ID | ADO work item ID (empty for new, filled after export) |
| Work Item Type | Always "Test Case" |
| Title | Format: `{story_id}-{test_id}: {Feature} / {Area} / {Scenario}` |
| TestStep | Step number |
| Step Action | Action to perform |
| Step Expected | Expected result |
| Area Path | ADO area path |
| AssignedTo | Assigned user |
| State | Test case state (Design) |

### Objectives File (`*_OBJECTIVES.txt`)

1:1 mapped objectives with HTML formatting:

```
272889-AC1: Object Transformation Tools / Tools Menu / Feature Availability
<b>Objective:</b> Verify that <b>Rotate</b>, <b>Mirror Horizontally</b>, and <b>Mirror Vertically</b> are available in <b>Tools Menu</b>

272889-005: Object Transformation Tools / Tools Menu / Commands Availability
<b>Objective:</b> Verify that transformation commands are <b>enabled</b> when an <b>object</b> is <b>selected</b>
```

### Debug JSON (`*_DEBUG.json`)

Full data for debugging:

```json
{
  "story_id": 272889,
  "title": "Object Transformation Tools (Rotate & Mirror)",
  "test_cases": [...],
  "mode": "hybrid"
}
```

---

## Configuration

### Environment Variables (`.env`)

```bash
# Required for ADO access
ADO_PAT=your_personal_access_token

# Optional for LLM correction
OPENAI_API_KEY=your_openai_api_key
```

### Config File (`config.py`)

```python
# ADO Settings
ADO_ORG = "cdpinc"
ADO_PROJECT = "Env"
ADO_AREA_PATH = "Env\\ENV Kanda"

# Test Case Defaults
ASSIGNED_TO = "your.email@domain.com"
DEFAULT_STATE = "Design"

# LLM Settings
LLM_MODEL = "gpt-4o-mini"  # Recommended for speed/cost
LLM_TIMEOUT = 90           # Seconds
```

---

## Quality Rules

### Title Format

```
{story_id}-{test_id}: {Feature} / {Area} / {Scenario}
```

**Examples**:
- `272889-AC1: Object Transformation / Tools Menu / Feature Availability`
- `272889-005: Object Transformation / Canvas / Rotate Functionality`

### Test ID Sequence

| ID | Type |
|----|------|
| AC1 | First test (availability) |
| 005 | Second test |
| 010 | Third test |
| 015 | Fourth test |
| ... | Increment by 5 |

### Forbidden Elements

**Words** (never use):
- `or` / `OR`
- `if available`
- `if supported`
- `if applicable`

**Areas** (use specific UI surfaces instead):
- `Functionality`
- `Behavior` (alone)
- `General`
- `Validation`

**Use Instead**:
- Tools Menu, File Menu, Edit Menu
- Properties Panel, Canvas
- Dialog Window, Top Action Toolbar

### Required Structure

| Step | Requirement |
|------|-------------|
| First | PRE-REQ step (empty expected) |
| Last | Close/Exit step (empty expected) |
| Verification | Must have expected result |

---

## Troubleshooting

### "No test suite found matching pattern"

**Cause**: Test suite name doesn't match `{story_id} : {name}` pattern.

**Solution**:
1. Check ADO for test suite name
2. Ensure format is exactly: `272889 : Story Name` (space before colon)
3. Create test suite if it doesn't exist

### "OPENAI_API_KEY not configured"

**Cause**: LLM correction requires OpenAI API key.

**Solutions**:
1. Add to `.env`: `OPENAI_API_KEY=your_key`
2. Or use `--skip-correction` flag

### "LLM correction taking too long"

**Cause**: Large test cases or slow API response.

**Solutions**:
1. Use `--skip-correction` for faster generation
2. Check OpenAI API status
3. Timeout is 90 seconds by default

### "No test cases found in CSV"

**Cause**: CSV doesn't have ADO work item IDs.

**Solution**: Export CSV from ADO after uploading test cases. The `ID` column must contain work item IDs.

### "Failed to fetch story"

**Cause**: Invalid story ID or ADO connection issue.

**Solutions**:
1. Verify story ID exists in ADO
2. Check `ADO_PAT` is valid and not expired
3. Verify network connectivity

---

## Project Structure

```
test_gen/
├── workflows.py              # Main CLI entry point (3 workflows)
├── config.py                 # Configuration settings
├── correct_with_llm.py       # LLM correction logic
├── README.md                 # This file
├── .env                      # Environment variables (create this)
│
├── src/                      # Core modules
│   ├── ado_client.py         # ADO API client
│   ├── comprehensive_test_generator.py  # Rule-based generation
│   ├── csv_generator.py      # CSV output
│   ├── objective_generator.py # Objective formatting
│   └── test_suite_uploader.py # ADO upload
│
├── core/                     # Clean architecture layer
│   ├── domain/               # Domain entities
│   ├── interfaces/           # Interfaces/ports
│   └── services/             # Domain services
│
├── llm/                      # LLM provider abstraction
│   ├── factory.py            # Provider factory
│   └── openai_provider.py    # OpenAI implementation
│
└── output/                   # Generated files
    ├── *_TESTS.csv
    ├── *_OBJECTIVES.txt
    └── *_DEBUG.json
```

---

## Version

**v2.0** - Clean workflow framework with three distinct workflows.

### Changelog

- Unified CLI entry point (`workflows.py`)
- Strict test suite matching (`{story_id} : {name}`)
- Improved error handling and validation
- Dry-run support for all workflows
- Better progress indicators
