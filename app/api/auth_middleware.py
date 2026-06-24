"""
可选 API Key 认证中间件。

配置:
    AUTH_ENABLED=true     # 启用认证（默认 false）
    API_KEY=your-key-here # API 密钥（默认使用 SECRET_KEY）

认证方式:
    Header: Authorization: Bearer <api_key>
    Query:  ?api_key=<api_key>

如果 AUTH_ENABLED=false，所有请求直接放行。
"""

import logging
from typing import Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

# 不需要认证的路径
_SKIP_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json", "/wiki-admin", "/vector-admin"}


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件。"""

    async def dispatch(self, request: Request, call_next):
        # 跳过公开路径
        if request.url.path in _SKIP_PATHS or request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)

        # 认证未启用则放行
        if not settings.AUTH_ENABLED:
            return await call_next(request)

        api_key = _extract_api_key(request)
        expected_key = settings.API_KEY or settings.SECRET_KEY

        if not api_key or api_key != expected_key:
            logger.warning("Auth failed from %s: %s", request.client.host if request.client else "unknown", request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


def _extract_api_key(request: Request) -> Optional[str]:
    """从请求中提取 API Key。"""
    # Header: Authorization: Bearer <key>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Query: ?api_key=<key>
    return request.query_params.get("api_key")
