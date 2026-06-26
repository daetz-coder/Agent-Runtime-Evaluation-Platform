# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

# 使用阿里云 Debian 镜像加速 + 持久化 apt 缓存
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
#
# System dependency notes:
#   git          - required by gitpython (app/wiki_agent/wiki/git_service.py)
#   libgomp1     - OpenMP runtime for PyTorch / sentence-transformers
#   curl         - health-check utility

# 使用清华 PyPI 镜像加速安装依赖 + 持久化 pip 缓存
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy application code
COPY app ./app
COPY sdk ./sdk
COPY alembic ./alembic
COPY alembic.ini ./

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "app.main"]
