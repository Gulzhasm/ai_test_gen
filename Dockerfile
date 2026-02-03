# ============================================================================
# DOCKERFILE FOR TEST-GEN
# ============================================================================

# ---------------------------------------------------------------------------
# STAGE: Base Image
# ---------------------------------------------------------------------------
# python:3.10-slim is ~150MB (vs python:3.10 at ~900MB)
# "slim" removes build tools but keeps what you need to RUN Python
FROM python:3.10-slim

# ---------------------------------------------------------------------------
# METADATA (optional but good practice)
# ---------------------------------------------------------------------------
LABEL maintainer="gulzhasm@gmail.com"
LABEL description="AI-powered test case generator"
LABEL version="1.0"

# ---------------------------------------------------------------------------
# ENVIRONMENT VARIABLES
# ---------------------------------------------------------------------------
# Prevents Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Ensures Python output is sent straight to terminal (no buffering)
ENV PYTHONUNBUFFERED=1

# ---------------------------------------------------------------------------
# WORKING DIRECTORY
# ---------------------------------------------------------------------------
# Creates /app if it doesn't exist, then cd into it
WORKDIR /app

# ---------------------------------------------------------------------------
# INSTALL SYSTEM DEPENDENCIES
# ---------------------------------------------------------------------------
# Some Python packages need system libraries to compile
# We install them, then clean up to keep image small
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*
#   └── Clean up apt cache (saves ~100MB)

# ---------------------------------------------------------------------------
# COPY REQUIREMENTS FIRST (Layer Caching Optimization!)
# ---------------------------------------------------------------------------
# Why copy requirements.txt separately?
# - Docker caches layers
# - If requirements.txt hasn't changed, Docker reuses cached layer
# - This means "pip install" is skipped on subsequent builds
# - HUGE time saver during development!
COPY requirements.txt .

# ---------------------------------------------------------------------------
# INSTALL PYTHON DEPENDENCIES
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# DOWNLOAD SPACY MODEL
# ---------------------------------------------------------------------------
# spaCy needs language models downloaded separately
# Do this in Dockerfile so it's baked into the image
RUN python -m spacy download en_core_web_sm

# ---------------------------------------------------------------------------
# COPY APPLICATION CODE
# ---------------------------------------------------------------------------
# This is LAST because your code changes most frequently
# When code changes, only this layer and below rebuild
COPY . .

# ---------------------------------------------------------------------------
# CREATE OUTPUT DIRECTORY
# ---------------------------------------------------------------------------
# Ensure output directory exists (will be mounted as volume in practice)
RUN mkdir -p /app/output

# ---------------------------------------------------------------------------
# DEFAULT COMMAND
# ---------------------------------------------------------------------------
# ENTRYPOINT = fixed part of command
# CMD = default arguments (can be overridden)
#
# Usage examples:
#   docker run test-gen --help
#   docker run test-gen generate --story-id 272780
#   docker run test-gen upload --story-id 272780 --dry-run

ENTRYPOINT ["python", "workflows.py"]
CMD ["--help"]
