# CLI Reference

Complete command-line interface documentation for the Test Generation Framework.

All commands are verified against the argparse definitions in `workflows.py`.

Throughout, `<project-id>` is one of the IDs shown by `list-projects` and
`<story-id>` is a work item ID.

---

## The three gotchas

Read these first — they cause most of the confusing failures.

### 1. `--project` goes BEFORE the subcommand

`--project` is registered on the top-level parser, so argparse only accepts it
before the subcommand name. Putting it after fails.

```bash
# CORRECT
python workflows.py --project <project-id> generate --story-id <story-id>


python workflows.py generate --story-id <story-id> --project <project-id>
```

### 2. Omitting `--project` silently uses `env-quickdraw`

There is no `DEFAULT_PROJECT` environment variable. When `--project` is absent the
framework falls back to the hardcoded `env-quickdraw` configuration. Generation
still reports success, but it uses that project's area path, UI surfaces and
vocabulary — so the output is contaminated with another project's terminology and
lands under the wrong ADO area path.

This is the single most likely way to waste a run, and it is silent. **Always pass
`--project` explicitly, on every command, even when you think the default is
right.**

### 3. A PARTIAL result exits with code 0

Only a hard failure exits `1`. A partial run prints `WARNING:` and exits `0`, so
CI and shell `&&` chains treat it as success. Read the output; do not rely on the
exit code alone.

---

## Before you run anything

```bash
cd /path/to/test_gen
source venv310/bin/activate
python workflows.py list-projects     # confirm your project ID and spelling
```

`list-projects` marks one project `(active)`. That label reflects internal state,
not what a given command will use — passing `--project` is still required.

---

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--project` | `-p` | Project configuration to use. Must precede the subcommand. Defaults to `env-quickdraw`. |
| `--help` | `-h` | Show help message |

---

## Commands

### `list-projects`

List all available project configurations. Takes no arguments.

```bash
python workflows.py list-projects
```

---

### `generate`

Generate test cases for a story and write them to the output folder. Does not
touch Azure DevOps.

```bash
python workflows.py --project <project-id> generate --story-id <story-id> [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--story-id` | yes | Work item ID (integer) |
| `--output-dir` | no | Output directory (default: `output/`) |
| `--skip-correction` | no | Skip the LLM correction pass — faster, markedly lower quality |

**Files written** (where `<slug>` is derived from the story title):

- `output/<id>_<slug>_HYBRID_TESTS.csv` — ADO-importable test cases
- `output/<id>_<slug>_HYBRID_OBJECTIVES.txt` — objectives for the Summary tab
- `output/<id>_<slug>_HYBRID_DEBUG.json` — full steps and objectives as JSON
- `output/<id>_<slug>_qa_summary.txt` — QA planning summary
- `output/<id>_PROMPTS_DEBUG.txt` — **the proof the LLM actually ran**

> **Always verify the LLM path ran.** `SUCCESS` does not mean the LLM was used.
> If `output/<id>_PROMPTS_DEBUG.txt` is missing, or its timestamp is from an
> earlier run, the LLM was skipped (no funds, bad key, timeout) and the
> rule-based template engine produced generic filler that looks superficially
> plausible.
>
> ```bash
> ls -la output/<story-id>_PROMPTS_DEBUG.txt
> ```
>
> The file is written *during* LLM correction and the CSV is saved at the end of
> the run, so on a healthy run the prompts file is a few seconds older than the
> CSV. Only a gap of hours means it is a leftover.

---

### `upload`

Generate test cases **and** upload them to the ADO test suite in one step.

```bash
python workflows.py --project <project-id> upload --story-id <story-id> [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--story-id` | yes | Work item ID (integer) |
| `--output-dir` | no | Output directory |
| `--skip-correction` | no | Skip the LLM correction pass |
| `--dry-run` | no | Preview without uploading |
| `--auto-create-suite` | no | Create the test suite if absent (default: **on**) |
| `--no-auto-create-suite` | no | Fail instead of creating a missing suite |

Always dry-run first:

```bash
python workflows.py --project <project-id> upload --story-id <story-id> --dry-run
python workflows.py --project <project-id> upload --story-id <story-id>
```

---

### `upload-existing`

Upload test cases already sitting in the output folder, with no regeneration.

```bash
python workflows.py --project <project-id> upload-existing --story-id <story-id> [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--story-id` | yes | Work item ID (integer) |
| `--output-dir` | no | Directory to search for existing files |

Use it when you generated earlier and reviewed the files, when you hand-edited
the CSV, or when generation succeeded but the upload failed and you don't want
to pay for generation twice.

---

### `update-objectives`

Update the objectives / Summary field (`System.Description`) on test cases that
already exist in ADO. With no `--csv`, it fetches the test cases from ADO directly.

```bash
python workflows.py --project <project-id> update-objectives --story-id <story-id> [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--story-id` | yes | Story ID used to locate local objective files and the ADO suite |
| `--csv` | no | CSV exported from ADO; omit to fetch from ADO |
| `--output-dir` | no | Directory containing local test files |
| `--dry-run` | no | Preview changes without writing to ADO |

---

### `update-from-feedback`

Rewrite test cases from a reviewer's written feedback.

```bash
python workflows.py --project <project-id> update-from-feedback --csv <CSV> --feedback <TXT> [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--csv` | yes | CSV exported from ADO with the existing test cases |
| `--feedback` | yes | Text file containing reviewer/customer feedback |
| `--dry-run` | no | Preview changes without updating ADO |
| `--use-llm` | no | Use an LLM to interpret the feedback |
| `--output` | no | Save proposed fixes to a JSON file for review first |

---

### `create-bug`

Build a formatted bug report from a structured `.txt` file.

```bash
python workflows.py --project <project-id> create-bug --file <TXT> [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--file` | yes | Structured `.txt` file with the bug details |
| `--upload` | no | Push to ADO (default: local preview only) |
| `--dry-run` | no | Preview the formatted ADO fields; use together with `--upload` |
| `--story-id` | no | Link the bug to a parent story |

---

### `init-project`

Scaffold a new project configuration YAML.

```bash
python workflows.py init-project --name <NAME> [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--name` | yes | Application name |
| `--id` | no | Project ID (defaults to the app name) |
| `--org` | no | ADO organization |
| `--ado-project` | no | ADO project name |
| `--area-path` | no | ADO area path |
| `--interactive` / `-i` | no | Interactive mode |

> A scaffolded YAML is a starting point, not a working config. Copying the
> example and editing only the obvious fields reliably produces bad output.
> Follow `docs/ONBOARDING_GUIDE.md` and the `onboard-project` skill.

---

### `discover`

Infer a project configuration by analyzing several existing stories.

```bash
python workflows.py discover --story-ids <id> [<id> ...] --project-name <NAME> [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--story-ids` | yes | One or more story IDs (space-separated) |
| `--project-name` | yes | Name for the discovered project |
| `--org` | no | ADO organization |
| `--ado-project` | no | ADO project name |

---

## Typical workflows

### Generate, review, then upload (recommended)

```bash
source venv310/bin/activate

python workflows.py list-projects
python workflows.py --project <project-id> generate --story-id <story-id>

ls -la output/<story-id>_PROMPTS_DEBUG.txt      # confirm the LLM ran
# ...review the CSV against the acceptance criteria...

python workflows.py --project <project-id> upload-existing --story-id <story-id>
```

### One-shot generate and upload

```bash
python workflows.py --project <project-id> upload --story-id <story-id> --dry-run
python workflows.py --project <project-id> upload --story-id <story-id>
```

### Working across several projects

Every command names its project, so there is no mode to switch and nothing to
remember between runs:

```bash
python workflows.py --project <project-a> generate --story-id <story-id>
python workflows.py --project <project-b> generate --story-id <story-id>
```

If you run the same project repeatedly, a shell alias keeps the project explicit
while saving typing. Define it per person, not in the repository, so no shared
default can ever be wrong for someone:

```bash
alias tg-myproject='python workflows.py --project <project-id>'
tg-myproject generate --story-id <story-id>
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success **or** partial success (partial prints `WARNING:`) |
| 1 | Failure — story not found, upload failed, config error |

---

## Environment Variables

Read from `.env` in the repository root. Values in a project's YAML take
precedence for ADO settings; `.env` takes precedence for LLM and judge settings.

| Variable | Description |
|----------|-------------|
| `ADO_PAT` | Azure DevOps Personal Access Token (required) |
| `ADO_ORG` | ADO organization; the project YAML `ado.organization` wins if set |
| `ADO_PROJECT` | ADO project; the project YAML `ado.project` wins if set |
| `ADO_AREA_PATH` | Area path; the project YAML `ado.area_path` wins if set |
| `OUTPUT_DIR` | Default output directory |
| `LLM_ENABLED` | Master switch for the LLM correction pass |
| `LLM_PROVIDER` / `LLM_MODEL` | Generation model — **overrides the YAML** |
| `JUDGE_ENABLED` | Master switch for the judge validation pass |
| `JUDGE_PROVIDER` / `JUDGE_MODEL` | Judge model — **overrides the YAML** |
| `OPENAI_API_KEY` | Required when either provider is `openai` |
| `GEMINI_API_KEY` | Required when either provider is `gemini` |
| `ANTHROPIC_API_KEY` | Required when either provider is `anthropic` |

Because `.env` overrides the YAML for LLM and judge settings, two people with
different `.env` files get different models for the same project. When output
quality differs between machines, compare `.env` first.

There is no `DEFAULT_PROJECT` variable — pass `--project` on every command.

---

## Troubleshooting

**`error: unrecognized arguments: --project <id>`**
Move `--project` before the subcommand. See gotcha 1.

**Output uses the wrong terminology, area path or UI surfaces**
You almost certainly omitted `--project` and got `env-quickdraw`. See gotcha 2.

**Output looks generic — steps like "Help Menu", or byte-identical across tests**
The LLM path was skipped and the template engine ran. Confirm
`output/<story-id>_PROMPTS_DEBUG.txt` exists with a current timestamp, then check
the API key and account balance for the provider named in `LLM_PROVIDER`.

**`Judge: ISSUES REMAIN after N round(s)`**
The judge could not fix everything within `judge_max_rounds`. The unresolved
issues are printed to stdout only — they are **not** saved to any file, so
capture the console output before it scrolls away. Review the CSV by hand.

**Generated tests reference fields or behaviour that do not exist**
The generator invented them. Ground the model by listing the real fields in the
project YAML (`application.feature_notes`) and constraining
`rules.allowed_areas`, then regenerate. Do not hand-edit the CSV — the next
regeneration discards the fix.

**Story not found**
Verify the ID, that `ADO_PAT` has read permission, and that the project YAML
points at the right ADO organization and project.

**Upload fails**
Dry-run first, confirm `ADO_PAT` has write permission, and confirm the
`area_path` in the project YAML exists in ADO.
