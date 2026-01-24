# Quick Start Guide

## Setup (One-Time)

```bash
# 1. Install dependencies
pip install requests beautifulsoup4 python-dotenv

# 2. Create .env file with your ADO PAT
echo "ADO_PAT=your_personal_access_token_here" > .env
```

## Commands

### 1. Generate Tests Locally (CSV/TXT)
```bash
python3 test_framework.py generate --story-id <STORY_ID>
```

### 2. Update Test Summaries in ADO
```bash
python3 test_framework.py update-summaries \
  --csv "path/to/tests.csv" \
  --objectives "path/to/objectives.txt"
```

### 3. Generate + Upload to ADO (Full Automation)
```bash
python3 test_framework.py generate-upload --story-id <STORY_ID>
```

## Example: Story 269496

```bash
# Generate and upload tests to ADO
python3 test_framework.py generate-upload --story-id 269496

# Expected output:
# ✓ Generated 11 tests
# ✓ Found suite: 269496 : Model Space and Canvas
# ✓ Uploaded 11 tests to suite
# ✓ Updated 11 objectives
```

## Test Suite Requirements

The test suite in ADO must be named:
```
{STORY_ID} : {STORY_NAME}
```

Example: `269496 : Model Space and Canvas`

Note: Space before the colon is required!

## Output Files

All generated files are saved to `output/` directory:
- `{STORY_ID}_{FEATURE}_TESTS.csv` - Test cases
- `{STORY_ID}_{FEATURE}_OBJECTIVES.txt` - Objectives
- `{STORY_ID}_{FEATURE}_DEBUG.csv` - Debug output (workflow 3)

## Need Help?

See [README.md](README.md) for full documentation.
