# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

# 使用阿里云 Debian 镜像加速
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 使用清华 PyPI 镜像加速安装依赖
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

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
