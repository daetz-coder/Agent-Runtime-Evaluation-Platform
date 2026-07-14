"""
Rate limiting middleware for evaluation endpoints.

Uses Redis Sorted Set sliding-window algorithm.
When Redis is unavailable, all requests are allowed through (graceful degradation).

Configuration:
    RATE_LIMIT_ENABLED=true
    RATE_LIMIT_EVAL_PER_MINUTE=10
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cache import check_rate_limit
from app.core.config import settings

logger = logging.getLogger(__name__)

# Only rate-limit POST requests to these path prefixes
_LIMITED_PATHS = {
    "/api/v1/evaluations/",  # matches /, /stream, /consensus, ...
    "/api/v1/benchmark/",  # matches /monotonicity/run
}

# Paths that should never be rate-limited regardless of method
_SKIP_PATHS = {
    "/api/v1/evaluations/settings",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter for evaluation endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Only active when enabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Only rate-limit POST to evaluation paths
        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        if not any(path.startswith(p) for p in _LIMITED_PATHS):
            return await call_next(request)
        if path in _SKIP_PATHS:
            return await call_next(request)

        # Determine client identifier (API key > client IP)
        client_id = _get_client_id(request)

        # Check rate limit
        allowed, retry_after = await check_rate_limit(
            key=f"eval:{client_id}",
            limit=settings.RATE_LIMIT_EVAL_PER_MINUTE,
            window_seconds=60,
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded for %s on %s (limit=%d/min)",
                client_id,
                path,
                settings.RATE_LIMIT_EVAL_PER_MINUTE,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_EVAL_PER_MINUTE),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return await call_next(request)


def _get_client_id(request: Request) -> str:
    """Extract a client identifier for rate limiting."""
    # Prefer API key if available
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return f"key:{auth_header[7:16]}"  # first 9 chars for privacy

    api_key = request.query_params.get("api_key")
    if api_key:
        return f"key:{api_key[:9]}"

    # Fall back to client IP
    if request.client:
        return f"ip:{request.client.host}"

    return "ip:unknown"
