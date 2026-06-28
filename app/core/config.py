"""
Application configuration using pydantic-settings.
"""

from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Application
    APP_NAME: str = "Agent Evaluation Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SQL_ECHO: bool = False
    SECRET_KEY: str = ""

    @model_validator(mode="after")
    def _ensure_secret_key(self):
        if not self.SECRET_KEY:
            if self.APP_ENV == "development":
                self.SECRET_KEY = "dev-insecure-secret-change-in-production"
            else:
                import secrets

                self.SECRET_KEY = secrets.token_hex(32)
        return self

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./agent_eval.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TIMEOUT: int = 2
    REDIS_KEY_PREFIX: str = "eval:"

    # Cache TTLs (seconds)
    CACHE_LLM_RESPONSES: bool = True
    CACHE_LLM_TTL: int = 86400  # 24h
    CACHE_REPORTS_TTL: int = 300  # 5min
    CACHE_TRENDS_TTL: int = 600  # 10min
    CACHE_TASK_TTL: int = 60  # 1min
    CACHE_TRAJECTORY_TTL: int = 300  # 5min
    CACHE_DASHBOARD_TTL: int = 30  # 30s
    CACHE_SESSION_TTL: int = 3600  # 1h

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_EVAL_PER_MINUTE: int = 10

    # LLM Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""

    # DeepSeek Configuration
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ZhipuAI (GLM) Configuration
    ZHIPUAI_API_KEY: str = ""
    ZHIPUAI_MODEL: str = "glm-4"

    # Qwen (DashScope) Configuration — OpenAI 兼容 API
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen3.7-plus"

    # Default LLM Configuration
    DEFAULT_LLM_PROVIDER: str = "deepseek"
    DEFAULT_LLM_MODEL: str = "deepseek-chat"

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    ENABLE_TRACING: bool = True

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Auth
    AUTH_ENABLED: bool = False
    API_KEY: str = ""

    # Evaluation Adapter
    EVAL_ENABLED: bool = True
    EVAL_AUTO_COLLECT: bool = True
    EVAL_API_BASE_URL: str = "http://127.0.0.1:8000"
    EVAL_API_KEY: str = ""
    EVAL_BATCH_SIZE: int = 10
    EVAL_WEBHOOK_URL: str = ""
    EVAL_PARALLEL: bool = True

    # Code Execution Sandbox (Docker-based) — shared with Agent Runtime
    # Note: enable/disable via AGENT_RUNTIME_ENABLED below
    SANDBOX_TIMEOUT: int = 30  # seconds per snippet (SandboxExecutor)
    SANDBOX_MEMORY_LIMIT_MB: int = 256
    SANDBOX_CPU_CORES: int = 1
    SANDBOX_OUTPUT_LIMIT: int = 10_240_000  # 10 MB
    SANDBOX_ACQUIRE_TIMEOUT: float = 10.0  # seconds to wait for pool
    SANDBOX_CACHE_TTL: int = 86400  # 24h cache for identical executions

    # Mock Sandbox Mode — for local development without Docker
    SANDBOX_MOCK_MODE: bool = False
    """When True, AgentRuntime returns a fixed mock trajectory instead of
    running inside Docker.  Useful for rapid prompt iteration."""

    # Agent Runtime (Agent in Sandbox)
    AGENT_RUNTIME_ENABLED: bool = True
    AGENT_MAX_STEPS: int = 20
    AGENT_TIMEOUT: int = 300  # 5 minutes total agent timeout

    # Sandbox Session (for Agent Runtime)
    SANDBOX_SESSION_POOL_SIZE: int = 3
    SANDBOX_SESSION_TIMEOUT: int = 600  # 10 minutes per container session
    SANDBOX_WORKSPACE_SIZE_MB: int = 512  # /workspace tmpfs size
    SANDBOX_TOOL_TIMEOUT: int = 60  # timeout per tool execution (seconds)

    # Agent Default Tools
    AGENT_DEFAULT_TOOLS: List[str] = [
        "python_execute",
        "bash_execute",
        "file_read",
        "file_write",
        "file_list",
    ]

    # Evaluation weights (shared between full and incremental eval)
    EVAL_DIMENSION_WEIGHTS: dict = {
        "planning": 0.20,
        "tactical": 0.20,
        "tool_use": 0.15,
        "memory": 0.15,
        "replan": 0.15,
        "retrieval": 0.15,
    }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
