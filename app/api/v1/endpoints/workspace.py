"""
Workspace management endpoints (multi-tenant CRUD + member RBAC).
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace import Workspace, WorkspaceMember, WorkspaceResponse, WorkspaceRole
from app.api.workspace_context import (
    WorkspaceContext,
    get_workspace_context,
    require_role,
    require_super_admin,
    require_workspace_access,
)
from app.db.database import get_db

router = APIRouter()


# ── Request / Response schemas ──────────────────────────────────


class WorkspaceCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class MemberAddRequest(BaseModel):
    user_id: str
    role: WorkspaceRole = WorkspaceRole.VIEWER


class MemberResponse(BaseModel):
    user_id: str
    role: str


# ── Endpoints ───────────────────────────────────────────────────


@router.post("/", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    body: WorkspaceCreateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Create a new workspace. Requires super admin."""
    require_super_admin(ctx)

    ws_id = str(uuid.uuid4())
    api_key = f"ws_{uuid.uuid4().hex}"

    workspace = Workspace(
        id=ws_id,
        name=body.name,
        description=body.description,
        api_key=api_key,
    )
    db.add(workspace)
    await db.flush()

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        api_key=workspace.api_key,
        created_at=workspace.created_at.isoformat() if workspace.created_at else "",
        is_active=workspace.is_active,
    )


@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """List all workspaces. Requires super admin."""
    require_super_admin(ctx)
    result = await db.execute(select(Workspace).where(Workspace.is_active.is_(True)))
    workspaces = result.scalars().all()
    return [
        WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            api_key=ws.api_key,
            created_at=ws.created_at.isoformat() if ws.created_at else "",
            is_active=ws.is_active,
        )
        for ws in workspaces
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Get workspace details."""
    require_workspace_access(ctx, workspace_id)
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        api_key=workspace.api_key,
        created_at=workspace.created_at.isoformat() if workspace.created_at else "",
        is_active=workspace.is_active,
    )


@router.post("/{workspace_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    workspace_id: str,
    body: MemberAddRequest,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Add a member to a workspace. Requires admin on that workspace."""
    require_workspace_access(ctx, workspace_id, WorkspaceRole.ADMIN)

    # Check workspace exists
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Upsert member
    existing = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == body.user_id,
        )
    )
    member = existing.scalar_one_or_none()
    if member:
        member.role = body.role
    else:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=body.user_id,
            role=body.role,
        )
        db.add(member)

    await db.flush()
    return MemberResponse(user_id=member.user_id, role=member.role.value)


@router.delete("/{workspace_id}", status_code=204)
async def deactivate_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Deactivate a workspace. Requires super admin."""
    require_super_admin(ctx)
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace.is_active = False
    await db.flush()
