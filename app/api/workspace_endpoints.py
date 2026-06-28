"""工作区 API 端点。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace import (
    AuditAction,
    AuditLog,
    AuditLogResponse,
    MemberCreate,
    Workspace,
    WorkspaceCreate,
    WorkspaceMember,
    WorkspaceResponse,
    WorkspaceRole,
    add_audit_log,
    create_workspace,
)
from app.api.workspace_context import (
    WorkspaceContext,
    get_workspace_context,
    require_super_admin,
    require_workspace_access,
)
from app.db.database import get_db

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("/", response_model=WorkspaceResponse, status_code=201)
async def create_ws(
    data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    require_super_admin(ctx)
    return await create_workspace(db, data)


@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    if ctx.is_super_admin or not ctx.workspace_id:
        require_super_admin(ctx)
        result = await db.execute(select(Workspace).order_by(Workspace.created_at.desc()))
        return [WorkspaceResponse.model_validate(ws) for ws in result.scalars().all()]
    result = await db.execute(select(Workspace).where(Workspace.id == ctx.workspace_id))
    ws = result.scalar_one_or_none()
    return [WorkspaceResponse.model_validate(ws)] if ws else []


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    require_workspace_access(ctx, workspace_id, WorkspaceRole.VIEWER)
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse.model_validate(ws)


@router.post("/{workspace_id}/rotate-key")
async def rotate_api_key(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    require_workspace_access(ctx, workspace_id, WorkspaceRole.ADMIN)
    import secrets

    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.api_key = f"ws_{secrets.token_hex(16)}"
    await add_audit_log(db, workspace_id, ctx.user_id, AuditAction.API_KEY_ROTATED, "workspace", workspace_id)
    await db.flush()
    return {"workspace_id": workspace_id, "api_key": ws.api_key}


@router.post("/{workspace_id}/members")
async def add_member(
    workspace_id: str,
    data: MemberCreate,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    require_workspace_access(ctx, workspace_id, WorkspaceRole.ADMIN)
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    member = WorkspaceMember(workspace_id=workspace_id, user_id=data.user_id, role=data.role)
    db.add(member)
    await add_audit_log(
        db,
        workspace_id,
        ctx.user_id,
        AuditAction.MEMBER_ADDED,
        "member",
        data.user_id,
        {"role": data.role.value},
    )
    await db.flush()
    return {"workspace_id": workspace_id, "user_id": data.user_id, "role": data.role.value}


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    require_workspace_access(ctx, workspace_id, WorkspaceRole.ADMIN)
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(member)
    await add_audit_log(db, workspace_id, ctx.user_id, AuditAction.MEMBER_REMOVED, "member", user_id)
    await db.flush()
    return {"message": "Member removed"}


@router.get("/{workspace_id}/audit", response_model=List[AuditLogResponse])
async def get_audit_logs(
    workspace_id: str,
    limit: int = 50,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    require_workspace_access(ctx, workspace_id, WorkspaceRole.VIEWER)
    query = select(AuditLog).where(AuditLog.workspace_id == workspace_id)
    if action:
        query = query.where(AuditLog.action == AuditAction(action))
    query = query.order_by(AuditLog.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [AuditLogResponse.model_validate(log) for log in result.scalars().all()]
