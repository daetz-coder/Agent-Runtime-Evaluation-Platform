"""
工作区上下文与 RBAC 依赖。

认证模式（AUTH_ENABLED=true）:
- 全局 API_KEY / SECRET_KEY → 超级管理员（跨工作区）
- Workspace.api_key (ws_*) → 绑定到该工作区（默认 admin 权限）
- 可选 Header X-User-Id → 查询 WorkspaceMember 角色

认证关闭时所有请求无工作区隔离（向后兼容）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_middleware import extract_api_key
from app.api.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.core.config import settings
from app.db.database import get_db

logger = logging.getLogger(__name__)

ROLE_LEVEL = {
    WorkspaceRole.VIEWER: 1,
    WorkspaceRole.EVALUATOR: 2,
    WorkspaceRole.ADMIN: 3,
}


@dataclass
class WorkspaceContext:
    """当前请求的工作区上下文。"""

    is_authenticated: bool = True
    is_super_admin: bool = False
    workspace_id: Optional[str] = None
    user_id: str = "system"
    role: Optional[WorkspaceRole] = None

    def filter_workspace_id(self) -> Optional[str]:
        """用于数据库查询的工作区 ID；None 表示不过滤。"""
        if not settings.AUTH_ENABLED or self.is_super_admin:
            return None
        return self.workspace_id

    def require_workspace(self) -> str:
        """要求已绑定工作区（非超级管理员创建资源时）。"""
        if not settings.AUTH_ENABLED or self.is_super_admin:
            return self.workspace_id or ""
        if not self.workspace_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace required")
        return self.workspace_id


async def authenticate_request(request: Request, db: AsyncSession) -> WorkspaceContext:
    """解析请求中的 API Key，返回工作区上下文。"""
    if not settings.AUTH_ENABLED:
        return WorkspaceContext(is_authenticated=True)

    api_key = extract_api_key(request)
    if not api_key:
        return WorkspaceContext(is_authenticated=False)

    global_key = settings.API_KEY or settings.SECRET_KEY
    if api_key == global_key:
        user_id = request.headers.get("X-User-Id", "system")
        return WorkspaceContext(
            is_authenticated=True,
            is_super_admin=True,
            user_id=user_id,
            role=WorkspaceRole.ADMIN,
        )

    result = await db.execute(select(Workspace).where(Workspace.api_key == api_key, Workspace.is_active.is_(True)))
    workspace = result.scalar_one_or_none()
    if not workspace:
        return WorkspaceContext(is_authenticated=False)

    user_id = request.headers.get("X-User-Id", "api-key")
    role = WorkspaceRole.ADMIN

    if user_id != "api-key":
        member_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = member_result.scalar_one_or_none()
        if member:
            role = member.role
        else:
            return WorkspaceContext(is_authenticated=False)

    return WorkspaceContext(
        is_authenticated=True,
        workspace_id=workspace.id,
        user_id=user_id,
        role=role,
    )


async def get_workspace_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    """FastAPI 依赖：获取当前请求的工作区上下文。"""
    cached = getattr(request.state, "workspace_context", None)
    if cached is not None:
        return cached
    return await authenticate_request(request, db)


def require_role(ctx: WorkspaceContext, minimum: WorkspaceRole) -> None:
    """检查当前用户是否具备最低角色权限。"""
    if not settings.AUTH_ENABLED or ctx.is_super_admin:
        return
    if ctx.role is None or ROLE_LEVEL[ctx.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def require_super_admin(ctx: WorkspaceContext) -> None:
    """要求超级管理员权限。"""
    if not settings.AUTH_ENABLED:
        return
    if not ctx.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin required")


def require_workspace_access(
    ctx: WorkspaceContext, workspace_id: str, minimum: WorkspaceRole = WorkspaceRole.VIEWER
) -> None:
    """要求对指定工作区的访问权限。"""
    if not settings.AUTH_ENABLED:
        return
    if ctx.is_super_admin:
        return
    if ctx.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied")
    require_role(ctx, minimum)


def resolve_task_workspace_id(ctx: WorkspaceContext, request: Request) -> Optional[str]:
    """解析创建任务时的工作区 ID。

    工作区 API Key：绑定当前工作区。
    超级管理员：可通过 X-Workspace-Id 指定，否则为 NULL（全局任务）。
    """
    if not settings.AUTH_ENABLED:
        return None
    if ctx.is_super_admin:
        header_ws = request.headers.get("X-Workspace-Id")
        return header_ws.strip() if header_ws else None
    return ctx.require_workspace()
