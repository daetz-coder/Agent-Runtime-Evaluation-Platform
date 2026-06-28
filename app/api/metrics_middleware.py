"""
Prometheus metrics HTTP middleware — instruments all HTTP requests.

Automatically records:
  - Request count by method, endpoint, status code
  - Request duration by method, endpoint
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import HTTP_REQUEST_COUNT, HTTP_REQUEST_DURATION


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip metrics endpoint itself
        if request.url.path in ("/metrics", "/api/v1/system/metrics"):
            return await call_next(request)

        method = request.method
        # Normalize endpoint to reduce cardinality (strip IDs)
        endpoint = _normalize_endpoint(request.url.path)

        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        HTTP_REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status=str(response.status_code),
        ).inc()

        HTTP_REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

        return response


def _normalize_endpoint(path: str) -> str:
    """Normalize URL path by replacing UUIDs and IDs with placeholders."""
    import re

    # Replace UUIDs with {id}
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "{id}",
        path,
    )
    # Replace numeric IDs
    path = re.sub(r"/\d+", "/{id}", path)
    return path
