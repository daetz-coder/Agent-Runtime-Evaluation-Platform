"""工作区 API 端点。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.workspace import (
    Workspace, WorkspaceMember, WorkspaceRole, AuditAction, AuditLog,
    WorkspaceCreate, WorkspaceResponse, MemberCreate, AuditLogResponse,
    create_workspace, add_audit_log,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ── 工作区管理 ──

@router.post("/", response_model=WorkspaceResponse, status_code=201)
async def create_ws(data: WorkspaceCreate, db: AsyncSession = Depends(get_db)):
    return await create_workspace(db, data)


@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workspace).order_by(Workspace.created_at.desc()))
    return [WorkspaceResponse.model_validate(ws) for ws in result.scalars().all()]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse.model_validate(ws)


@router.post("/{workspace_id}/rotate-key")
async def rotate_api_key(workspace_id: str, db: AsyncSession = Depends(get_db)):
    import secrets
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.api_key = f"ws_{secrets.token_hex(16)}"
    await add_audit_log(db, workspace_id, "system", AuditAction.API_KEY_ROTATED, "workspace", workspace_id)
    await db.flush()
    return {"workspace_id": workspace_id, "api_key": ws.api_key}


# ── 成员管理 ──

@router.post("/{workspace_id}/members")
async def add_member(workspace_id: str, data: MemberCreate, db: AsyncSession = Depends(get_db)):
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    member = WorkspaceMember(workspace_id=workspace_id, user_id=data.user_id, role=data.role)
    db.add(member)
    await add_audit_log(db, workspace_id, data.user_id, AuditAction.MEMBER_ADDED, "member", data.user_id,
                        {"role": data.role.value})
    await db.flush()
    return {"workspace_id": workspace_id, "user_id": data.user_id, "role": data.role.value}


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(workspace_id: str, user_id: str, db: AsyncSession = Depends(get_db)):
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
    await add_audit_log(db, workspace_id, "system", AuditAction.MEMBER_REMOVED, "member", user_id)
    await db.flush()
    return {"message": "Member removed"}


# ── 审计日志 ──

@router.get("/{workspace_id}/audit", response_model=List[AuditLogResponse])
async def get_audit_logs(
    workspace_id: str,
    limit: int = 50,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog).where(AuditLog.workspace_id == workspace_id)
    if action:
        query = query.where(AuditLog.action == AuditAction(action))
    query = query.order_by(AuditLog.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [AuditLogResponse.model_validate(log) for log in result.scalars().all()]
