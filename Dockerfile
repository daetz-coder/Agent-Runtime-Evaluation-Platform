# =============================================================================
# Agent Runtime Evaluation Platform — Dockerfile
#
# 两阶段构建：
#   Stage 1: Build Frontend  (Node 20 → static assets)
#   Stage 2: Runtime         (Python 3.11-slim → 将应用作为正经 package 安装)
# =============================================================================

# ── Stage 1: Frontend ───────────────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci && npm cache clean --force

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Runtime ───────────────────────────────────────────────────
FROM python:3.11-slim

LABEL description="Agent Runtime Evaluation Platform"
LABEL version="0.1.0"

# ── 环境变量 ────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SENTENCE_TRANSFORMERS_HOME=/model-cache/sentence-transformers \
    HUGGINGFACE_HUB_CACHE=/model-cache/huggingface

# ── 系统运行时依赖 ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/agent-eval

# ── 第 1 层：安装依赖（利用 Docker layer cache，仅 pyproject.toml 变更时重装） ─
COPY pyproject.toml ./

# 只拷贝源码目录（不拷贝 frontend 源码、文档等）
COPY app/ ./app/
COPY sdk/ ./sdk/
COPY prompts/ ./prompts/
COPY main.py ./

# 正经安装：生产模式，无 dev 依赖，非 editable
RUN pip install --no-cache-dir .

# ── 第 2 层：运行资产 ───────────────────────────────────────────────────
COPY --from=frontend /build/dist/ ./frontend/dist/

# 预下载 embedding 模型到缓存目录
RUN mkdir -p /model-cache/sentence-transformers /model-cache/huggingface \
    && python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='/model-cache/sentence-transformers'); \
print('Embedding model cached')"

# ── 第 3 层：运行时目录（由 docker-compose volume 持久化） ──────────────
RUN mkdir -p data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
