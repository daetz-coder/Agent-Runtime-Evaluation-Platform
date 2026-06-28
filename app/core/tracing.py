"""
OpenTelemetry tracing initialization and convenience API.

Graceful degradation: if OTEL collector is unreachable or tracing is disabled,
all tracing silently becomes a no-op (no exceptions, no latency impact).

Usage:
    # In any module:
    from app.core.tracing import get_tracer
    tracer = get_tracer(__name__)

    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("key", "value")
        ...

    # Or use the decorator:
    from app.core.tracing import traced

    @traced("my_async_operation")
    async def my_function(arg):
        ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, TypeVar

from opentelemetry import trace
from opentelemetry.trace import StatusCode, Tracer

logger = logging.getLogger(__name__)

_SERVICE_NAME = "agent-eval-platform"

_tracer_provider: Optional[trace.TracerProvider] = None
_is_active: bool = False

F = TypeVar("F", bound=Callable[..., Any])


# ── Lifecycle ─────────────────────────────────────────────────


def init_tracing() -> bool:
    """
    Initialize the OpenTelemetry TracerProvider with OTLP exporter.

    Returns True if tracing is active, False if disabled or unavailable.
    Safe to call multiple times; subsequent calls are no-ops.
    """
    global _tracer_provider, _is_active

    from app.core.config import settings

    if not settings.ENABLE_TRACING:
        logger.info("Tracing disabled by config (ENABLE_TRACING=false)")
        return False

    if _tracer_provider is not None:
        return _is_active

    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        resource = Resource.create({
            "service.name": _SERVICE_NAME,
            "service.version": "0.1.0",
            "deployment.environment": settings.APP_ENV,
        })

        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=True,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _tracer_provider = provider
        _is_active = True

        logger.info(
            "Tracing initialized: endpoint=%s, service=%s",
            settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            _SERVICE_NAME,
        )
        return True

    except Exception as e:
        logger.warning(
            "Tracing initialization failed — running without tracing: %s", e
        )
        # Set a no-op provider so get_tracer never fails
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        _tracer_provider = trace.get_tracer_provider()
        _is_active = False
        return False


def shutdown_tracing() -> None:
    """Flush pending spans and shut down the TracerProvider."""
    global _tracer_provider, _is_active

    if _tracer_provider is not None:
        try:
            if hasattr(_tracer_provider, "shutdown"):
                _tracer_provider.shutdown()
        except Exception as e:
            logger.debug("Tracing shutdown error (ignored): %s", e)
        finally:
            _tracer_provider = None
            _is_active = False
            logger.info("Tracing shut down")


# ── Convenience API ───────────────────────────────────────────


def get_tracer(name: str) -> Tracer:
    """
    Get a named tracer. Safe to call before init_tracing() —
    returns a no-op tracer if tracing is not initialized.
    """
    return trace.get_tracer(name)


def is_tracing_active() -> bool:
    """Return True if tracing is active and exporting spans."""
    return _is_active


def traced(
    name: Optional[str] = None,
    attributes: Optional[dict] = None,
) -> Callable[[F], F]:
    """
    Decorator that wraps a function (sync or async) in a tracing span.

    Usage:
        @traced("my_operation")
        async def my_func(x, y):
            ...

        @traced()  # uses function name as span name
        def sync_func():
            ...
    """

    def decorator(func: F) -> F:
        span_name = name or func.__qualname__

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer(func.__module__)
                with tracer.start_as_current_span(span_name) as span:
                    if attributes:
                        span.set_attributes(attributes)
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(StatusCode.OK)
                        return result
                    except Exception as exc:
                        span.set_status(StatusCode.ERROR, str(exc))
                        span.record_exception(exc)
                        raise

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer(func.__module__)
                with tracer.start_as_current_span(span_name) as span:
                    if attributes:
                        span.set_attributes(attributes)
                    try:
                        result = func(*args, **kwargs)
                        span.set_status(StatusCode.OK)
                        return result
                    except Exception as exc:
                        span.set_status(StatusCode.ERROR, str(exc))
                        span.record_exception(exc)
                        raise

            return sync_wrapper  # type: ignore[return-value]

    return decorator
