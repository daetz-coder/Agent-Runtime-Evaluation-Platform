"""
Resource quota enforcement for multi-tenant workspaces.

Checks workspace quotas before allowing operations:
  - sandbox_quota: max concurrent sandbox sessions
  - max_steps_per_eval: max agent steps per evaluation
  - eval_count_limit_monthly: max evaluations per month
  - storage_limit_mb: max workspace file storage

Usage:
    from app.services.quota import QuotaService, QuotaExceeded
    quota = QuotaService(db)
    await quota.check_eval_limit(workspace_id)
    await quota.check_sandbox_quota(workspace_id)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace import Workspace
from app.db.models import AgentTask, Evaluation

logger = logging.getLogger(__name__)

SANDBOX_EVAL_MODE = "sandbox"


class QuotaExceeded(Exception):
    """Raised when a workspace quota is exceeded."""

    def __init__(self, quota_type: str, limit: int, current: int):
        self.quota_type = quota_type
        self.limit = limit
        self.current = current
        super().__init__(f"Quota exceeded: {quota_type} limit={limit}, current={current}")


class QuotaService:
    """Checks and enforces workspace resource quotas."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_workspace(self, workspace_id: Optional[str]) -> Optional[Workspace]:
        """Get workspace by ID."""
        if not workspace_id:
            return None
        result = await self.db.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def check_eval_limit(self, workspace_id: Optional[str]) -> None:
        """Check if workspace has reached its monthly evaluation limit."""
        ws = await self.get_workspace(workspace_id)
        if not ws or ws.eval_count_limit_monthly <= 0:
            return  # No workspace or unlimited

        # Count evaluations this month
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await self.db.execute(
            select(func.count())
            .select_from(Evaluation)
            .join(AgentTask, Evaluation.task_id == AgentTask.id)
            .where(
                AgentTask.workspace_id == workspace_id,
                Evaluation.created_at >= month_start,
            )
        )
        count = result.scalar_one()

        if count >= ws.eval_count_limit_monthly:
            raise QuotaExceeded(
                "eval_count_limit_monthly",
                ws.eval_count_limit_monthly,
                count,
            )

    async def check_max_steps(self, workspace_id: Optional[str], requested_steps: int) -> None:
        """Check if requested steps exceeds workspace max."""
        ws = await self.get_workspace(workspace_id)
        if not ws or ws.max_steps_per_eval <= 0:
            return

        if requested_steps > ws.max_steps_per_eval:
            raise QuotaExceeded(
                "max_steps_per_eval",
                ws.max_steps_per_eval,
                requested_steps,
            )

    async def check_sandbox_quota(self, workspace_id: Optional[str]) -> None:
        """Check if workspace has reached its concurrent sandbox limit."""
        ws = await self.get_workspace(workspace_id)
        if not ws or ws.sandbox_quota <= 0:
            return

        from app.db.models import TaskStatus

        result = await self.db.execute(
            select(func.count())
            .select_from(AgentTask)
            .where(
                AgentTask.workspace_id == workspace_id,
                AgentTask.status == TaskStatus.RUNNING,
                AgentTask.context.isnot(None),
                AgentTask.context["eval_mode"].as_string() == SANDBOX_EVAL_MODE,
            )
        )
        running = result.scalar_one()

        if running >= ws.sandbox_quota:
            raise QuotaExceeded("sandbox_quota", ws.sandbox_quota, running)


async def enforce_workspace_quotas(
    db: AsyncSession,
    workspace_id: Optional[str],
    *,
    sandbox: bool = False,
    max_steps: Optional[int] = None,
) -> None:
    """Run workspace quota checks; raises QuotaExceeded on violation."""
    quota = QuotaService(db)
    await quota.check_eval_limit(workspace_id)
    if sandbox:
        await quota.check_sandbox_quota(workspace_id)
    if max_steps is not None and max_steps > 0:
        await quota.check_max_steps(workspace_id, max_steps)
