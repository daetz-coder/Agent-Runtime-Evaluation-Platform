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

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db.database import async_session_factory

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

        from app.api.workspace_context import authenticate_request

        async with async_session_factory() as db:
            ctx = await authenticate_request(request, db)
            if not ctx.is_authenticated:
                logger.warning(
                    "Auth failed from %s: %s",
                    request.client.host if request.client else "unknown",
                    request.url.path,
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or missing API key"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            request.state.workspace_context = ctx

        return await call_next(request)


def extract_api_key(request: Request) -> Optional[str]:
    """从请求中提取 API Key。"""
    # Header: Authorization: Bearer <key>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Query: ?api_key=<key>
    return request.query_params.get("api_key")


# 向后兼容内部引用
_extract_api_key = extract_api_key
