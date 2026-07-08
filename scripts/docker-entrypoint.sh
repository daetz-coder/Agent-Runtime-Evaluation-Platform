#!/bin/bash
# =============================================================================
# Agent Runtime Evaluation Platform — Docker Entrypoint
# =============================================================================
# Handles first-run initialization, directory setup, and app startup.
# =============================================================================

set -e

echo "================================================================"
echo " Agent Runtime Evaluation Platform"
echo " Version: 0.1.0"
echo " Environment: ${APP_ENV:-production}"
echo "================================================================"

# ── Ensure runtime directories exist ────────────────────────────────────
mkdir -p /app/data /app/app/wiki_agent/data /app/app/wiki_agent/models
mkdir -p /model-cache/sentence-transformers /model-cache/huggingface

# ── Warm model cache if cold ────────────────────────────────────────────
# If the embedding model isn't cached, download it now so startup
# doesn't block on model download.
MODEL_CACHE="${SENTENCE_TRANSFORMERS_HOME:-/model-cache/sentence-transformers}"
EMBEDDING_MODEL="BAAI/bge-small-zh-v1.5"
if [ ! -d "$MODEL_CACHE/$EMBEDDING_MODEL" ]; then
    echo "[Init] Warming embedding model cache: $EMBEDDING_MODEL ..."
    python -c "
from sentence_transformers import SentenceTransformer
SentenceTransformer('$EMBEDDING_MODEL', cache_folder='$MODEL_CACHE')
" 2>&1 | tail -1
    echo "[Init] Embedding model cached."
fi

# ── Check API keys ─────────────────────────────────────────────────────
if [ -z "$DEEPSEEK_API_KEY" ] && [ -z "$ZHIPUAI_API_KEY" ] && [ -z "$QWEN_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo ""
    echo " ⚠️  WARNING: No LLM API keys configured!"
    echo "    At least one of DEEPSEEK_API_KEY, ZHIPUAI_API_KEY,"
    echo "    QWEN_API_KEY, or OPENAI_API_KEY must be set."
    echo "    Evaluation and Wiki Agent will fail without one."
    echo ""
fi

# ── Execute main command ───────────────────────────────────────────────
echo "[Init] Starting: $@"
echo ""
exec "$@"
