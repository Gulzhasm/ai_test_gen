# Test-Gen: Multi-Agent LLM Orchestration for Structured Test Generation

A **multi-agent LLM orchestration system** that reads structured requirements from project management platforms, generates validated structured outputs through a hybrid rule-engine + LLM pipeline, enforces coverage via automated feedback loops, and self-corrects using RAG-powered semantic matching.

Built with **Clean Architecture**, multi-provider LLM support (OpenAI, Gemini, Anthropic, Ollama), ChromaDB vector search, and a Model Context Protocol (MCP) server for IDE integration.

---

## Table of Contents

1. [AI Engineering Overview](#ai-engineering-overview)
2. [System Architecture](#system-architecture)
3. [Technical Highlights](#technical-highlights)
4. [Quick Start (5 minutes)](#quick-start-5-minutes)
5. [Docker Setup (Recommended)](#docker-setup-recommended)
6. [CLI Commands](#cli-commands)
7. [Adding Your Project](#adding-your-project)
8. [Configuration Reference](#configuration-reference)
9. [Output Files](#output-files)
10. [Bug Creation](#bug-creation)
11. [Board Story Report](#board-story-report)
12. [AC Coverage Validation](#ac-coverage-validation)
13. [ChromaDB Semantic Matching](#chromadb-semantic-matching)
14. [MCP Integration (GitHub Copilot)](#mcp-integration-github-copilot)
15. [Architecture](#architecture)
16. [Troubleshooting](#troubleshooting)

---

## AI Engineering Overview

This system solves a real-world problem — generating comprehensive, validated test cases from natural-language requirements — using a **multi-stage AI pipeline** rather than a single LLM call.

### The Problem

Manually writing test cases from user stories is slow, inconsistent, and prone to coverage gaps. A single LLM prompt produces hallucinated steps, inconsistent wording, and misses edge cases.

### The Solution: Hybrid AI Pipeline

Instead of relying on a single LLM call, the system orchestrates **multiple specialized stages** — each with its own responsibility — combining deterministic rule engines with LLM intelligence:

```
Structured Input (ADO/Jira)
        │
        ▼
┌─────────────────────────────┐
│   1. INGESTION & PARSING    │  Platform adapters (ADO, Jira) → domain models
│      NLP analysis (spaCy)   │  Story type classification, feature detection
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  2. DETERMINISTIC GENERATION│  Rule engine: 70+ QA rules, scenario expansion,
│     (No LLM — pure logic)   │  edge case generation, platform-specific tests
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  3. RAG: SEMANTIC MATCHING  │  ChromaDB vector search (all-MiniLM-L6-v2)
│     Reference step retrieval│  Retrieve similar steps → enforce consistency
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  4. LLM CORRECTION          │  Multi-provider (OpenAI/Gemini/Anthropic/Ollama)
│     Structured JSON output  │  Dynamic prompt construction, JSON schema enforcement
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  5. VALIDATION & FEEDBACK   │  AC coverage gap detection → targeted re-generation
│     Self-correction loop    │  Quality gates, forbidden language, structural fixes
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  6. MULTI-FORMAT EXPORT     │  CSV (ADO), Playwright scripts, JSON, QA summaries
│     Platform upload         │  ADO test suites, TestRail, MCP server
└─────────────────────────────┘
```

### Why This Architecture?

| Decision | Rationale |
|----------|-----------|
| **Hybrid (rules + LLM)** instead of pure LLM | Rule engine handles 70% deterministically — LLM refines the remaining 30%. Reduces hallucination, cuts token cost, ensures structural correctness |
| **RAG for consistency** instead of stateless prompts | ChromaDB stores previously generated steps. New generations retrieve similar steps as few-shot context, producing consistent wording across runs |
| **Coverage validation loop** instead of single-pass | After generation, the system extracts keywords from each acceptance criterion and checks coverage. Uncovered ACs trigger a targeted LLM call to fill gaps |
| **Multi-provider factory** instead of hardcoded provider | Factory pattern + YAML config = swap between OpenAI, Gemini, Anthropic, or local Ollama without code changes |
| **Structured output enforcement** instead of free-text | JSON schema in prompts, `response_mime_type` for Gemini, truncated JSON repair for robustness |

---

## System Architecture

```
                        ┌──────────────────────────┐
                        │    CLI / MCP Server       │  Entry points
                        │   (workflows.py)          │  (Typer CLI + MCP)
                        └────────────┬─────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │  Generate    │ │   Upload     │ │  Bug Report  │  Workflow
           │  Workflow    │ │   Workflow   │ │  Workflow    │  Layer
           └──────┬───────┘ └──────┬───────┘ └──────────────┘
                  │                │
                  ▼                ▼
    ┌─────────────────────────────────────────────┐
    │              CORE SERVICES                   │
    │                                              │
    │  ┌─────────────┐  ┌──────────────────────┐  │
    │  │ Test        │  │ LLM Orchestration    │  │
    │  │ Generator   │  │                      │  │
    │  │ (rules +    │  │  PromptBuilder       │  │
    │  │  NLP +      │──│  LLMCorrector        │  │
    │  │  scenarios) │  │  Provider Factory     │  │
    │  └─────────────┘  │  ┌────┬────┬────┐   │  │
    │                    │  │GPT │Gem │Anth│   │  │
    │  ┌─────────────┐  │  │    │ini │ropi│   │  │
    │  │ Embeddings  │  │  │    │    │c   │   │  │
    │  │ (ChromaDB   │──│  └────┴────┴────┘   │  │
    │  │  RAG)       │  └──────────────────────┘  │
    │  └─────────────┘                             │
    │                    ┌──────────────────────┐  │
    │  ┌─────────────┐  │ Quality Gates        │  │
    │  │ AC Coverage │──│  Validator           │  │
    │  │ Validator   │  │  Linters             │  │
    │  └─────────────┘  └──────────────────────┘  │
    └─────────────────────────────────────────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐
    │ ADO        │ │ Jira       │ │ TestRail   │  Infrastructure
    │ Adapter    │ │ Adapter    │ │ Adapter    │  Layer
    └────────────┘ └────────────┘ └────────────┘
```

---

## Technical Highlights

**LLM Orchestration**
- Multi-provider factory pattern: OpenAI, Google Gemini, Anthropic, Ollama — swappable via YAML config
- Dynamic prompt construction: context-aware prompts built from project config, feature type, and RAG results
- Structured JSON output with schema enforcement and truncated JSON repair
- Response caching (`MemoryCache`, `FileCache`) to minimize redundant API calls
- Cost tracking via `MetricsCollector` and `CostCalculator`

**RAG Pipeline (ChromaDB)**
- Sentence embeddings via `all-MiniLM-L6-v2` (384-dim) for semantic step matching
- Persistent vector store with distance-based similarity threshold (< 1.5)
- Retrieved reference steps injected as few-shot context into LLM correction prompts
- Feedback loop: each generation embeds new steps → future queries return richer context

**Self-Correction & Validation**
- AC coverage validation: keyword extraction from acceptance criteria → coverage check → targeted gap-filling LLM call for uncovered ACs
- Quality gates: 70+ rules (forbidden language, structural integrity, ID sequencing, accessibility compliance)
- Iterative correction: rule-based pre-pass → LLM refinement → post-validation

**NLP & Feature Intelligence**
- spaCy-based semantic parsing for acceptance criteria analysis
- Multi-label feature type classification (input, navigation, display, object manipulation, calculation)
- Story type classification (Tool, Dialog, Menu, File Operations) for context-aware generation
- Entry point auto-detection: maps features to correct UI locations

**Software Engineering**
- Clean Architecture: interfaces (`core/interfaces/`), domain models, use cases, infrastructure adapters
- Repository pattern with platform-agnostic factories (ADO, Jira, TestRail)
- Dependency injection via project configuration (YAML → dataclasses)
- MCP server exposing all workflows to GitHub Copilot / Claude Code
- Docker support for reproducible environments
- Playwright test script generation (LLM-based with deterministic fallback)

---

## Domain Context

> *The sections below describe the QA domain this system operates in — how it's used, configured, and integrated with Azure DevOps.*

This framework automatically generates comprehensive test cases by:

1. **Reading** user stories and acceptance criteria from Azure DevOps (or Jira)
2. **Understanding** your application context from project configuration (YAML)
3. **Generating** test cases using a hybrid rule-engine + LLM pipeline
4. **Matching** against previously generated steps via ChromaDB for consistent wording
5. **Correcting** test quality with LLM enhancement (structural fixes, forbidden language, accessibility)
6. **Validating** AC coverage — auto-detects gaps and generates missing tests
7. **Exporting** to ADO-compatible CSV format or uploading directly

### Key Features

- **Project-agnostic**: Works with any application (desktop, web, mobile, hybrid)
- **Multi-provider AI**: Supports OpenAI, Gemini, Anthropic, and Ollama for test generation
- **Context-aware**: Generates relevant tests based on feature type (no input tests for menus!)
- **ChromaDB semantic matching**: Reference steps from previous generations ensure consistent wording
- **AC coverage validation**: Automatically detects missing acceptance criteria coverage and generates gap-filling tests
- **Multi-platform**: Generates accessibility tests for all supported platforms (Windows 11, iPad, Android Tablet)
- **ADO Integration**: Direct upload to Azure DevOps test suites + bug creation + board reporting

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

# LLM Provider (at least one required for LLM correction)
OPENAI_API_KEY=sk-your-api-key-here       # OpenAI
GEMINI_API_KEY=your-gemini-key-here        # Google Gemini (alternative)
ANTHROPIC_API_KEY=your-anthropic-key-here  # Anthropic (alternative)
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
| `create-bug` | Create formatted ADO bug report | `python workflows.py create-bug --file bugs/my_bug.txt` |

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

# 9. Create a bug report (local preview)
python workflows.py create-bug --file bugs/my_bug.txt

# 10. Create a bug report with dry-run (preview ADO fields without uploading)
python workflows.py create-bug --file bugs/my_bug.txt --upload --dry-run

# 11. Create a bug report and upload to ADO
python workflows.py create-bug --file bugs/my_bug.txt --upload

# 12. Create a bug and link to parent story
python workflows.py create-bug --file bugs/my_bug.txt --upload --story-id 272261
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

# LLM settings (provider options: openai, gemini, anthropic, ollama)
llm_enabled: true
llm_provider: gemini           # or openai, anthropic, ollama
llm_model: gemini-2.0-flash    # model name for chosen provider
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

### LLM Providers

The framework supports multiple LLM providers via a factory pattern. Set `llm_provider` in your YAML config or `.env`:

| Provider | Config Value | Env Variable | Models |
|----------|-------------|--------------|--------|
| OpenAI | `openai` | `OPENAI_API_KEY` | `gpt-4o-mini`, `gpt-4o` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash`, `gemini-1.5-pro` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Ollama (local) | `ollama` | N/A | Any local model |

YAML config `llm_provider` takes precedence over `.env` defaults. API keys are always resolved from environment variables.

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

## Bug Creation

Create formatted ADO Bug work items from structured `.txt` files following the **ENV Drawing Bug Template**.

### Input File Format

Create a `.txt` file (see `bugs/sample_bug.txt` for a complete example):

```
TITLE: DRAW: Feature Name / Brief Description
SEVERITY: 2 - High
STORY_ID: 272261

ISSUE: One sentence describing what is wrong.

ADDITIONAL_INFO:
- Regression from build 3.2.1
- WCAG 2.1 AA 1.3.1 (for accessibility bugs)

ATTACHMENTS:
- screenshot.png
- video.mp4

STEPS:
1. Launch the ENV QuickDraw application.
2. Navigate to the affected area.
3. Perform the action.
   a. Observation text << NOT EXPECTED (see attached screenshot.png)
      i. Expected: What should happen instead.
      ii. Expected: Additional expected behavior.

SYSTEM_INFO:
- OS: Windows 11 Pro 23H2
- App Version: ENV QuickDraw 3.2.4
```

### Bug Title Conventions

| Type | Format |
|------|--------|
| Normal bug | `DRAW: Feature / Brief Description` |
| WCAG/Accessibility | `DRAW: WCAG Accessibility Errors / Feature / Error` |

### CLI Commands

```bash
# Preview locally (saves HTML to output/)
python workflows.py create-bug --file bugs/my_bug.txt

# Dry run — preview what would be uploaded without creating in ADO
python workflows.py create-bug --file bugs/my_bug.txt --upload --dry-run

# Upload to ADO (creates Bug work item, returns URL)
python workflows.py create-bug --file bugs/my_bug.txt --upload

# Upload and link to parent story
python workflows.py create-bug --file bugs/my_bug.txt --upload --story-id 272261
```

### Template Sections (auto-generated)

The formatter produces ADO HTML matching the ENV Drawing Bug Template:

- **ISSUE:** — One sentence, same line as heading
- **ADDITIONAL INFORMATION:** — WCAG refs, regression notes
- **SUPPORTING DOCUMENTATION PROVIDED:** — Bulleted attachment filenames
- **RECREATE STEPS:** — Numbered steps with `<< NOT EXPECTED` marker (yellow highlight)
- **TRIAGE/CAUSE INFORMATION:** — Empty (for development)
- **FIX SUMMARY:** — Empty (for development)

---

## Board Story Report

Generate a CSV summary of all user stories from specific ADO board columns, with test case counts.

```bash
python scripts/fetch_board_stories.py
```

**Output:** `output/board_stories_summary.csv` with columns:

| Column | Description |
|--------|-------------|
| User Story Title | Story ID and title |
| # Test Cases | Count of linked test cases (via TestedBy relations + test suites) |
| Tablet Testing Needed | Left empty for dev team to fill in |

The script queries stories from **Most Wanted**, **Development**, and **Quality Assurance** board columns, filtered by area path. Excludes `[Out of Scope]` stories.

---

## AC Coverage Validation

The LLM correction pipeline automatically validates that every acceptance criterion (AC) has at least one test case covering it. If gaps are detected, it generates targeted gap-filling tests.

### How It Works

1. **Keyword extraction** from each AC (strips stop words, punctuation)
2. **Keyword matching** against test case text (title + objective + steps) at 40% threshold with minimum 2 keyword hits
3. **Gap detection** — ACs with zero matching test cases are flagged
4. **Targeted LLM call** — generates 1-2 tests per uncovered AC
5. **Structural fixes** — ensures generated tests have PRE-REQ, launch, close steps

### Console Output

```
  AC coverage: All 12 ACs covered by existing tests
```

Or when gaps are found:

```
  Warning: 1 AC(s) have no test coverage:
    AC 11: Undo/Redo applies to rename, visibility, lock, order, delete (limit 50)
  → Generating tests for 1 uncovered AC(s)...
  → Added 3 gap-filling test(s)
```

This runs automatically during `generate` and `upload` workflows. No extra flags needed.

---

## ChromaDB Semantic Matching

Previously generated test steps are stored in ChromaDB (vector database) and used as reference during LLM correction. This ensures consistent wording across test generations for the same story.

- **Auto-embeds** using `all-MiniLM-L6-v2` sentence transformer
- **Distance metric**: lower = more similar (0.2 very similar, 1.5+ less similar)
- **Persistent storage** in `./db/` folder
- To **regenerate cleanly**, delete the story's steps from ChromaDB before re-running

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
"create bug from bugs/my_bug.txt"
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
│   │   └── example-web-app.yaml
│   ├── project_config.py     # Configuration loader
│   └── project_manager.py    # Project management
│
├── bugs/                     # Bug report input files
│   └── sample_bug.txt        # Example bug template
│
├── core/                     # ALL business logic (Clean Architecture)
│   ├── application/use_cases/ # Use case implementations
│   │   ├── bug_parser.py     # Parse .txt bug files
│   │   └── bug_formatter.py  # Format bugs to ADO HTML
│   ├── config/               # App configuration
│   │   └── environment.py    # Environment variables
│   ├── domain/               # Domain models
│   │   ├── models.py         # UserStory, TestCase, etc.
│   │   └── bug_report.py     # BugReport, RecreateStep
│   ├── interfaces/           # Contracts (protocols)
│   │   ├── llm_provider.py   # ILLMProvider interface
│   │   ├── repository.py     # IStoryRepository, ITestSuiteRepository, etc.
│   │   └── vector_store.py   # IVectorStore interface
│   └── services/             # ALL services centralized here
│       ├── test_generator.py # Main test generation
│       ├── objective_service.py  # Objective generation
│       ├── summary_service.py    # QA summary generation
│       ├── test_validator.py     # QualityGate validation
│       ├── embeddings/       # Vector embeddings
│       │   └── test_step_embedder.py  # ChromaDB step embedding
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
│           ├── corrector.py      # LLM correction + AC coverage validation
│           ├── prompt_builder.py # Dynamic prompt generation
│           ├── factory.py        # LLM provider factory
│           ├── openai_provider.py
│           ├── gemini_provider.py
│           └── anthropic_provider.py
│
├── infrastructure/           # External services (adapters)
│   ├── ado/                  # Azure DevOps client
│   │   ├── http_client.py    # Low-level ADO HTTP client
│   │   ├── ado_repository.py # ADO API wrapper (stories, test cases, suites)
│   │   └── ado_bug_repository.py # ADO Bug creation
│   ├── vector_db/            # Vector database
│   │   └── chroma_repository.py  # ChromaDB implementation
│   └── export/               # Export generators
│       ├── csv_generator.py
│       └── objective_generator.py
│
├── integrations/             # External tool integrations
│   └── mcp_server.py         # GitHub Copilot MCP server
│
├── scripts/                  # Utility scripts
│   └── fetch_board_stories.py # ADO board story report
│
├── tests/                    # Unit & integration tests
│   ├── unit/
│   └── integration/
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
- Gemini `gemini-2.0-flash` is a fast, cost-effective alternative

### Gemini rate limit errors

- Gemini free tier has strict daily rate limits
- Upgrade to a paid API key or switch to `openai` in your YAML config

### ChromaDB polluted reference steps

- Bad reference steps from previous generations can affect new outputs
- Delete the `./db/` folder to clear all stored embeddings, or
- Re-generate the story to overwrite stale references

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

**v6.0** — Phase 2: Intelligent Coverage & Semantic Matching

### Phase 2 (v6.0) — Current

- **AC coverage validation** — automatically detects missing acceptance criteria coverage and generates gap-filling tests via targeted LLM call
- **ChromaDB semantic matching** — stores previously generated test steps as reference embeddings for consistent wording across generations
- **Gemini provider** — Google Gemini (Flash + Pro) support via `google-genai` SDK with JSON response mode
- **LLM factory pattern** — provider-agnostic architecture (OpenAI, Gemini, Anthropic, Ollama) with YAML config override
- **Board story report** (`scripts/fetch_board_stories.py`) — fetches user stories from ADO board columns with test case counts
- **Enhanced LLM corrector** — structural fixes (PRE-REQ, launch, close steps), forbidden language cleanup, accessibility test auto-generation

### Phase 1 (v5.2)

- **Bug creation command** (`create-bug`) — create ADO Bug work items from structured `.txt` files
- **Multi-provider LLM** — initial OpenAI and Anthropic support
- **Anti-hallucination guardrails** — LLM-generated tests are grounded in acceptance criteria
- **`--dry-run` flag** for bug creation — preview without uploading to ADO
- **Docker support** for consistent team environments
- **MCP integration** — use from GitHub Copilot Chat
- Project-agnostic framework with YAML configuration
- Enhanced LLM prompts (expert QA engineer persona)
- `update-objectives` workflow now fetches directly from ADO (no CSV required)
