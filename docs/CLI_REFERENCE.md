# CLI Reference

Complete command-line interface documentation for the Test Generation Framework.

---

## Global Options

These options work with all commands:

| Option | Short | Description |
|--------|-------|-------------|
| `--project` | `-p` | Project configuration to use (default: from `.env` or `env-quickdraw`) |
| `--help` | `-h` | Show help message |

**Example:**
```bash
python workflows.py generate --story-id 272889 --project mediapedia-us
python workflows.py -p my-project generate --story-id 123456
```

---

## Commands

### 1. `list-projects`

List all available project configurations.

```bash
python workflows.py list-projects
```

**Output:**
```
============================================================
Available Projects
============================================================

  env-quickdraw (active)
    Application: ENV QuickDraw
    ADO: cdpinc/Env

  mediapedia-us
    Application: MediaPedia US
    ADO: myorg/MediaPedia
```

---

### 2. `generate`

Generate test cases for a user story and save to `output/` folder.

```bash
python workflows.py generate --story-id <STORY_ID> [OPTIONS]
```

**Required:**
| Argument | Description |
|----------|-------------|
| `--story-id` | Azure DevOps Story ID (e.g., 272889) |

**Optional:**
| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir` | Directory to save output files | `output/` |
| `--skip-correction` | Skip LLM correction step (faster, lower quality) | False |

**Examples:**
```bash
# Basic generation
python workflows.py generate --story-id 272889

# Skip LLM correction (faster)
python workflows.py generate --story-id 272889 --skip-correction

# Custom output directory
python workflows.py generate --story-id 272889 --output-dir ./my_tests

# Use specific project
python workflows.py generate --story-id 272889 --project mediapedia-us
```

**Output files created:**
- `output/{story_id}_*_TESTS.csv` - ADO-compatible test cases
- `output/{story_id}_*_OBJECTIVES.txt` - Test objectives with HTML formatting
- `output/{story_id}_*_DEBUG.json` - Full generation data for debugging

---

### 3. `upload`

Generate test cases AND upload directly to Azure DevOps.

```bash
python workflows.py upload --story-id <STORY_ID> [OPTIONS]
```

**Required:**
| Argument | Description |
|----------|-------------|
| `--story-id` | Azure DevOps Story ID |

**Optional:**
| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir` | Directory to save output files | `output/` |
| `--skip-correction` | Skip LLM correction step | False |
| `--dry-run` | Preview without uploading | False |
| `--auto-create-suite` | Auto-create test suite if not found | True |
| `--no-auto-create-suite` | Fail if test suite not found | False |

**Examples:**
```bash
# Generate and upload
python workflows.py upload --story-id 272889

# Preview without uploading
python workflows.py upload --story-id 272889 --dry-run

# Upload without LLM correction
python workflows.py upload --story-id 272889 --skip-correction

# Don't auto-create test suite
python workflows.py upload --story-id 272889 --no-auto-create-suite
```

---

### 4. `upload-existing`

Upload previously generated test cases to Azure DevOps (skip generation).

Use this when you already have generated files in `output/` and want to upload them.

```bash
python workflows.py upload-existing --story-id <STORY_ID> [OPTIONS]
```

**Required:**
| Argument | Description |
|----------|-------------|
| `--story-id` | Azure DevOps Story ID |

**Optional:**
| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir` | Directory to search for existing files | `output/` |

**How it works:**
1. Searches `output/` for files matching the story ID pattern
2. Finds: `{story_id}_*_TESTS.csv`, `{story_id}_*_DEBUG.json`
3. Uploads test cases to ADO without regenerating

**Examples:**
```bash
# Upload existing tests for story 272889
python workflows.py upload-existing --story-id 272889

# Search in custom directory
python workflows.py upload-existing --story-id 272889 --output-dir ./my_tests
```

**When to use:**
- You generated tests earlier and want to upload them now
- You manually edited the CSV and want to upload the changes
- Generation succeeded but upload failed (retry without regenerating)

---

### 5. `init-project`

Initialize a new project configuration.

```bash
python workflows.py init-project --name <NAME> [OPTIONS]
```

**Required:**
| Argument | Description |
|----------|-------------|
| `--name` | Application name (e.g., "MyApp") |

**Optional:**
| Option | Description |
|--------|-------------|
| `--org` | Azure DevOps organization |
| `--ado-project` | Azure DevOps project name |

**Example:**
```bash
python workflows.py init-project --name "MediaPedia" --org myorg --ado-project MediaPedia
```

**Creates:** `projects/configs/mediapedia.yaml` with template configuration.

---

### 6. `discover`

Auto-discover project configuration from existing user stories.

```bash
python workflows.py discover --story-ids <ID1> <ID2> ... [OPTIONS]
```

**Required:**
| Argument | Description |
|----------|-------------|
| `--story-ids` | One or more story IDs to analyze |

**Optional:**
| Option | Description |
|--------|-------------|
| `--project-name` | Name for the new project |

**Example:**
```bash
python workflows.py discover --story-ids 12345 12346 12347 --project-name my-app
```

**What it does:**
1. Reads multiple stories from ADO
2. Analyzes UI surfaces, entry points, platforms mentioned
3. Generates a suggested YAML configuration

---

## Workflow Examples

### First-Time Setup

```bash
# 1. See what projects are available
python workflows.py list-projects

# 2. Generate tests for a story
python workflows.py generate --story-id 272889

# 3. Review output files in output/
ls output/

# 4. When satisfied, upload to ADO
python workflows.py upload --story-id 272889
```

### Daily Usage

```bash
# Quick generation and upload
python workflows.py upload --story-id 273566

# Generate without upload (for review first)
python workflows.py generate --story-id 273566
# ... review files ...
python workflows.py upload-existing --story-id 273566
```

### Fast Mode (Skip LLM)

```bash
# Generate quickly without AI correction
python workflows.py generate --story-id 272889 --skip-correction

# Upload quickly
python workflows.py upload --story-id 272889 --skip-correction
```

### Working with Multiple Projects

```bash
# List all projects
python workflows.py list-projects

# Generate for specific project
python workflows.py generate --story-id 12345 --project mediapedia-us

# Upload to different project
python workflows.py upload --story-id 67890 -p example-web-app
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (story not found, upload failed, etc.) |

---

## Environment Variables

These override defaults:

| Variable | Description |
|----------|-------------|
| `DEFAULT_PROJECT` | Default project ID to use |
| `OUTPUT_DIR` | Default output directory |
| `ADO_PAT` | Azure DevOps Personal Access Token |
| `OPENAI_API_KEY` | OpenAI API key for LLM correction |

---

## Troubleshooting

### Command not found
```bash
# Ensure virtual environment is activated
source venv310/bin/activate

# Verify workflows.py exists
ls -la workflows.py
```

### Story not found
```bash
# Check story ID is correct
# Verify ADO_PAT has read permissions
# Ensure project config points to correct ADO org/project
```

### Upload fails
```bash
# Use dry-run to preview
python workflows.py upload --story-id 272889 --dry-run

# Check ADO_PAT has write permissions
# Verify area_path exists in ADO
```

### Existing files not found
```bash
# Check output directory
ls output/*272889*

# Use correct output-dir if files are elsewhere
python workflows.py upload-existing --story-id 272889 --output-dir ./custom_dir
```
