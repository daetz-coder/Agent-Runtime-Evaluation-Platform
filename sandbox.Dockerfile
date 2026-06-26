# =============================================================================
# Sandbox execution image — isolated from the main platform.
# Pre-built with Python, Bash, and Node.js for executing agent code snippets.
#
# Build: docker build -t agent-eval-sandbox:latest -f sandbox.Dockerfile .
# =============================================================================

FROM python:3.11-slim

# Install bash, core utilities, and Node.js 20 LTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    coreutils \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install common Python packages agents typically use
RUN pip install --no-cache-dir \
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
