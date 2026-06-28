"""
多租户支持 — Workspace 隔离、RBAC 角色、操作审计日志。
"""

from __future__ import annotations

import enum
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import DateTime, ForeignKey, String, Text, JSON, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── 枚举 ──

class WorkspaceRole(str, enum.Enum):
    ADMIN = "admin"
    EVALUATOR = "evaluator"
    VIEWER = "viewer"


class AuditAction(str, enum.Enum):
    # 评估相关
    EVAL_CREATED = "eval_created"
    EVAL_COMPLETED = "eval_completed"
    EVAL_DELETED = "eval_deleted"
    # 任务相关
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_DELETED = "task_deleted"
    TRAJECTORY_ADDED = "trajectory_added"
    # 工作区相关
    WORKSPACE_CREATED = "workspace_created"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    API_KEY_ROTATED = "api_key_rotated"


# ── ORM 模型 ──

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Resource quotas (0 = unlimited)
    sandbox_quota: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_steps_per_eval: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    eval_count_limit_monthly: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    storage_limit_mb: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)

    # 关系
    members: Mapped[List["WorkspaceMember"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"))
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)  # 外部用户标识
    role: Mapped[WorkspaceRole] = mapped_column(SQLEnum(WorkspaceRole), default=WorkspaceRole.EVALUATOR)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    workspace: Mapped["Workspace"] = relationship(back_populates="members")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[AuditAction] = mapped_column(SQLEnum(AuditAction), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="audit_logs")


# ── Pydantic Schemas ──

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    api_key: str
    created_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MemberCreate(BaseModel):
    user_id: str
    role: WorkspaceRole = WorkspaceRole.EVALUATOR


class AuditLogResponse(BaseModel):
    id: int
    workspace_id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── 服务函数 ──

async def create_workspace(db, data: WorkspaceCreate) -> WorkspaceResponse:
    import secrets
    ws = Workspace(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        api_key=f"ws_{secrets.token_hex(16)}",
    )
    db.add(ws)
    db.add(AuditLog(
        workspace_id=ws.id,
        user_id="system",
        action=AuditAction.WORKSPACE_CREATED,
        resource_type="workspace",
        resource_id=ws.id,
        details={"name": ws.name},
    ))
    await db.flush()
    return WorkspaceResponse.model_validate(ws)


async def add_audit_log(
    db,
    workspace_id: str,
    user_id: str,
    action: AuditAction,
    resource_type: str,
    resource_id: str,
    details: Optional[dict] = None,
) -> None:
    db.add(AuditLog(
        workspace_id=workspace_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    ))
