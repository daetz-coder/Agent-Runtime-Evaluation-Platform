"""
Correlation ID middleware — assigns a unique request ID to every HTTP request.

The ID is:
  - Generated if not present in X-Request-ID header
  - Set in contextvar for structlog propagation
  - Returned in X-Request-ID response header
  - Bounded to the request's async context
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import set_correlation_id

_HEADER = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Reuse client-provided ID or generate new one
        cid = request.headers.get(_HEADER) or uuid.uuid4().hex[:16]
        set_correlation_id(cid)

        response = await call_next(request)
        response.headers[_HEADER] = cid
        return response
