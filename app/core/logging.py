"""
Structured logging with structlog + correlation ID support.

Replaces stdlib logging with structlog for JSON-formatted, contextual logs.
Each request gets a unique correlation ID that propagates through the entire
call chain (API → Agent → Evaluator).

Usage:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("message", key="value")

Correlation ID is automatically set by CorrelationIdMiddleware.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

from app.core.config import settings

# ── Correlation ID (context-local, async-safe) ───────────────

_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    return _correlation_id_var.get()


def set_correlation_id(cid: str | None = None) -> str:
    """Set correlation ID for the current context. Auto-generates if None."""
    cid = cid or uuid.uuid4().hex[:16]
    _correlation_id_var.set(cid)
    return cid


def add_correlation_id(logger: Any, method_name: str, event_dict: dict) -> dict:
    """structlog processor: inject correlation_id into every log entry."""
    event_dict["request_id"] = _correlation_id_var.get()
    return event_dict


# ── structlog Configuration ──────────────────────────────────


def setup_logging() -> None:
    """Configure structlog with JSON output for production, colored for dev."""

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_correlation_id,
    ]

    if settings.APP_ENV == "production":
        # JSON output for production (ELK/Loki compatible)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Colored console output for development
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO if settings.APP_ENV == "production" else logging.DEBUG)

    # Suppress noisy third-party loggers
    for name in (
        "uvicorn.access",
        "httpcore",
        "httpx",
        "sqlalchemy.engine",
        "aiosqlite",
        "sqlite3",
        "openai",
        "openai._base_client",
        "langchain",
        "langchain_core",
        "langchain_openai",
        "sdk.collector",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


# ── Convenience ──────────────────────────────────────────────


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger bound with the module name."""
    return structlog.get_logger(name)
