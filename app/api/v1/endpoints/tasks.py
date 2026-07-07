"""
Task management endpoints.
"""

from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.db.database import get_db
from app.db.models import AgentTask, TaskStatus
from app.models.schemas import TaskCreate, TaskResponse, TaskUpdate, TrajectoryStep
from app.services.evaluation_service import EvaluationService

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new agent task."""
    service = EvaluationService(db)
    task = await service.create_task(task_data)
    return task


@router.get("/dashboard")
async def get_tasks_dashboard(
    db: AsyncSession = Depends(get_db),
):
    """Get task dashboard counters and recent tasks."""
    cache_key = EvaluationService._dashboard_cache_key()

    cached = await cache_get(cache_key)
    if cached is not None:
        total_tasks = cached["total_tasks"]
        status_counts = cached["status_counts"]
    else:
        count_query = select(func.count()).select_from(AgentTask)
        status_query = select(AgentTask.status, func.count(AgentTask.id)).group_by(AgentTask.status)

        total_result = await db.execute(count_query)
        total_tasks = total_result.scalar_one()

        status_counts: Dict[str, int] = {status.value: 0 for status in TaskStatus}
        status_result = await db.execute(status_query)
        for status, count in status_result.all():
            status_counts[status.value if hasattr(status, "value") else str(status)] = count

        await cache_set(
            cache_key, {"total_tasks": total_tasks, "status_counts": status_counts}, ttl=settings.CACHE_DASHBOARD_TTL
        )

    recent_query = select(AgentTask).order_by(AgentTask.created_at.desc()).limit(5)
    recent_result = await db.execute(recent_query)
    recent_tasks = recent_result.scalars().all()

    return {
        "total_tasks": total_tasks,
        "status_counts": status_counts,
        "recent_tasks": [
            {
                "id": task.id,
                "goal": task.goal,
                "context": task.context,
                "status": task.status.value,
                "workspace_id": task.workspace_id,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
            }
            for task in recent_tasks
        ],
    }


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List all tasks."""
    service = EvaluationService(db)
    tasks, total = await service.list_tasks_with_count(skip=skip, limit=limit)
    return JSONResponse(
        content=[t.model_dump(mode="json") for t in tasks],
        headers={"X-Total-Count": str(total)},
    )


@router.post("/{task_id}/trajectory", status_code=201)
async def add_trajectory(
    task_id: str,
    steps: List[TrajectoryStep],
    db: AsyncSession = Depends(get_db),
):
    """
    Add trajectory steps to an existing task.

    Used by the Dashboard, SDK HTTP transport, and external Agent integrations
    that capture their own runtime trace.
    """
    service = EvaluationService(db)
    steps_data = [step.model_dump() for step in steps]
    success = await service.add_trajectory(task_id, steps_data)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": f"Added {len(steps)} trajectory steps", "task_id": task_id}


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing task."""
    service = EvaluationService(db)
    task = await service.update_task(task_id, task_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/trajectory")
async def get_trajectory(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get execution trajectory for a task."""
    service = EvaluationService(db)
    trajectory = await service.get_trajectory(task_id)
    if trajectory is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "steps": trajectory}


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get task by ID."""
    service = EvaluationService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a task and all its trajectory and evaluation records."""
    service = EvaluationService(db)
    deleted = await service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted", "task_id": task_id}
