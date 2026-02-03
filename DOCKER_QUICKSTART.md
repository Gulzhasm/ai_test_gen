# Docker Quickstart for test-gen

## Prerequisites

1. **Install Docker Desktop**
   - Mac: https://docs.docker.com/desktop/install/mac-install/
   - Windows: https://docs.docker.com/desktop/install/windows-install/
   - Linux: https://docs.docker.com/desktop/install/linux-install/

2. **Get the `.env` file** from team lead (contains ADO credentials)

---

## Quick Start (2 minutes)

```bash
# 1. Clone the repo
git clone <repo-url>
cd test_gen

# 2. Copy your .env file to project root
cp /path/to/.env .

# 3. Build the image (first time only, takes ~3 min)
docker build -t test-gen:v1 .

# 4. Test it works
docker run test-gen:v1 --help
```

---

## Common Commands

### Generate Test Cases
```bash
# Basic generation (with LLM correction)
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 generate --story-id 272780

# Fast generation (skip LLM, rule-based only)
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 generate --story-id 272780 --skip-correction
```

### Upload to ADO
```bash
# Dry run first (preview, no changes)
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 upload --story-id 272780 --dry-run

# Live upload
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 upload --story-id 272780
```

### Update Objectives
```bash
docker run --env-file .env -v $(pwd)/output:/app/output \
    test-gen:v1 update-objectives --story-id 272780
```

### List Projects
```bash
docker run test-gen:v1 list-projects
```

---

## Shell Aliases (Optional)

Add these to your `~/.bashrc` or `~/.zshrc` for convenience:

```bash
# Quick alias for test-gen
alias testgen='docker run --env-file .env -v $(pwd)/output:/app/output test-gen:v1'

# Now you can simply run:
# testgen generate --story-id 272780
# testgen upload --story-id 272780 --dry-run
```

---

## Troubleshooting

### "Cannot connect to Docker daemon"
- Make sure Docker Desktop is running (check system tray/menu bar)

### "No such file: .env"
- Copy your `.env` file to the project root directory
- Never commit `.env` to git!

### "Permission denied" on output folder
```bash
# Fix permissions
sudo chown -R $(whoami) output/
```

### Need to debug inside container?
```bash
docker run -it --entrypoint /bin/bash test-gen:v1
# Now you're inside the container, explore freely
```

### Rebuild after code changes
```bash
docker build -t test-gen:v1 .
# Docker caches layers, so rebuilds are fast if only code changed
```

---

## Understanding the Output

After running `generate`, check the `output/` folder:
- `{story_id}_*_TESTS.csv` - Test cases ready for ADO import
- `{story_id}_*_OBJECTIVES.txt` - Human-readable test objectives
- `{story_id}_*_DEBUG.json` - Full data for debugging

---

## Why Docker?

| Without Docker | With Docker |
|----------------|-------------|
| "Works on my machine" | Works everywhere |
| Install Python 3.10, pip, spacy, download models... | Just `docker build` |
| Dependency conflicts | Isolated environment |
| Different results on different machines | Reproducible builds |

---

## Need Help?

- Check logs in Docker Desktop (click on container → Logs tab)
- Run with `--help`: `docker run test-gen:v1 --help`
- Ask in team Slack channel
