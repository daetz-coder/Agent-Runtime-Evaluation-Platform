# syntax=docker/dockerfile:1
# =============================================================================
# Sandbox execution image — isolated from the main platform.
# Pre-built with Python, Bash, and Node.js for executing agent code snippets.
#
# Build: docker build -t agent-eval-sandbox:latest -f sandbox.Dockerfile .
# =============================================================================

FROM python:3.11-slim

# 使用阿里云 Debian 镜像加速 + 持久化 apt 缓存
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    bash \
    coreutils \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install common Python packages agents typically use (使用清华 PyPI 镜像 + 持久化 pip 缓存)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    numpy \
    pandas \
    requests \
    beautifulsoup4 \
    sympy \
    Pillow

# Create non-root user for execution (security)
RUN useradd -m -u 1000 sandbox

# Switch to non-root user
USER sandbox
WORKDIR /tmp

# Container will sleep until code is injected via exec_run
CMD ["sleep", "infinity"]
