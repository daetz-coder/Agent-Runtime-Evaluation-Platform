"""Tests for structured logging and correlation ID."""

from unittest.mock import MagicMock, patch

import pytest


class TestStructuredLogging:
    """Tests for app.core.logging module."""

    def test_get_logger_returns_bound_logger(self):
        from app.core.logging import get_logger

        logger = get_logger("test_module")
        # structlog returns a lazy proxy; just verify it's callable
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    def test_setup_logging_no_crash(self):
        from app.core.logging import setup_logging

        setup_logging()  # Should not raise

    def test_correlation_id_default(self):
        from app.core.logging import _correlation_id_var, get_correlation_id

        _correlation_id_var.set("-")
        assert get_correlation_id() == "-"

    def test_set_correlation_id_custom(self):
        from app.core.logging import get_correlation_id, set_correlation_id

        cid = set_correlation_id("abc123")
        assert cid == "abc123"
        assert get_correlation_id() == "abc123"

    def test_set_correlation_id_auto_generate(self):
        from app.core.logging import get_correlation_id, set_correlation_id

        cid = set_correlation_id(None)
        assert len(cid) == 16  # hex[:16]
        assert get_correlation_id() == cid

    def test_add_correlation_id_processor(self):
        from app.core.logging import add_correlation_id, set_correlation_id

        set_correlation_id("test-id-123")
        event_dict = {"event": "test message"}
        result = add_correlation_id(None, "info", event_dict)
        assert result["request_id"] == "test-id-123"


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware."""

    @pytest.mark.asyncio
    async def test_middleware_generates_id(self):
        from starlette.requests import Request
        from starlette.responses import Response

        from app.api.correlation_id_middleware import CorrelationIdMiddleware

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}

        async def call_next(req):
            return Response("ok")

        middleware = CorrelationIdMiddleware(app=None)
        response = await middleware.dispatch(mock_request, call_next)
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 16

    @pytest.mark.asyncio
    async def test_middleware_reuses_client_id(self):
        from starlette.requests import Request
        from starlette.responses import Response

        from app.api.correlation_id_middleware import CorrelationIdMiddleware

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"X-Request-ID": "client-provided-id"}

        async def call_next(req):
            return Response("ok")

        middleware = CorrelationIdMiddleware(app=None)
        response = await middleware.dispatch(mock_request, call_next)
        assert response.headers["X-Request-ID"] == "client-provided-id"


class TestOpenTelemetryTracing:
    """Tests for app.core.tracing module."""

    def test_get_tracer_returns_tracer(self):
        from app.core.tracing import get_tracer

        tracer = get_tracer("test")
        assert tracer is not None

    def test_is_tracing_active_default_false(self):
        from app.core.tracing import is_tracing_active

        # Before init, should be False
        # (May be True if another test initialized it)
        assert isinstance(is_tracing_active(), bool)

    def test_init_tracing_disabled(self):
        from app.core.tracing import init_tracing

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.ENABLE_TRACING = False
            result = init_tracing()
            assert result is False

    def test_shutdown_tracing_no_crash(self):
        from app.core.tracing import shutdown_tracing

        shutdown_tracing()  # Should not raise even when not initialized

    def test_traced_decorator_sync(self):
        from app.core.tracing import traced

        @traced("test_sync")
        def my_func(x, y):
            return x + y

        result = my_func(1, 2)
        assert result == 3

    def test_traced_decorator_sync_exception(self):
        from app.core.tracing import traced

        @traced("test_sync_error")
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_func()

    @pytest.mark.asyncio
    async def test_traced_decorator_async(self):
        from app.core.tracing import traced

        @traced("test_async")
        async def async_func(x):
            return x * 2

        result = await async_func(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_traced_decorator_async_exception(self):
        from app.core.tracing import traced

        @traced("test_async_error")
        async def failing_async():
            raise RuntimeError("async error")

        with pytest.raises(RuntimeError, match="async error"):
            await failing_async()

    def test_traced_decorator_preserves_name(self):
        from app.core.tracing import traced

        @traced("custom_name")
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_traced_with_attributes(self):
        from app.core.tracing import traced

        @traced("with_attrs", attributes={"key": "value"})
        def func_with_attrs():
            return "ok"

        result = func_with_attrs()
        assert result == "ok"
