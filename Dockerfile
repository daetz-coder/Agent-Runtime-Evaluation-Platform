# =============================================================================
# Agent Runtime Evaluation Platform — Dockerfile
# Multi-stage build: frontend (Node 20) → backend (Python 3.11-slim)
# =============================================================================

# ── Stage 1: Build Frontend ────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python Backend ────────────────────────────────────────────────
FROM python:3.11-slim

LABEL description="Agent Runtime Evaluation Platform"
LABEL version="0.1.0"

# Prevents Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Sentence-transformers cache — mount a volume here
    SENTENCE_TRANSFORMERS_HOME=/model-cache/sentence-transformers \
    HUGGINGFACE_HUB_CACHE=/model-cache/huggingface \
    # Default port
    PORT=8000

# Install system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    # Milvus Lite needs these
    libstdc++6 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (layer caching: only reinstall when pyproject.toml changes)
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]" 2>&1 | tail -5

# Copy source code
COPY app/ ./app/
COPY sdk/ ./sdk/
COPY prompts/ ./prompts/
COPY main.py ./

# Copy pre-built frontend from stage 1
COPY --from=frontend-builder /build/frontend/dist/ ./frontend/dist/

# Create wiki-agent runtime directories (persist via volume)
RUN mkdir -p app/wiki_agent/data app/wiki_agent/models

# Pre-warm model cache: download embedding model at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='/model-cache/sentence-transformers')" 2>&1 | tail -3

EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:${PORT}/health || exit 1

# Entrypoint
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
