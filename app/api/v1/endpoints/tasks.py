"""
Task management endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.schemas import TaskCreate, TaskResponse, TrajectoryStep
from app.services.evaluation_service import EvaluationService

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new agent task.

    - **goal**: The goal/objective for the agent to achieve
    - **context**: Additional context (optional)
    """
    service = EvaluationService(db)
    return await service.create_task(task_data)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get task by ID.

    - **task_id**: UUID of the task
    """
    service = EvaluationService(db)
    task = await service.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    List all tasks.

    - **skip**: Number of records to skip
    - **limit**: Maximum number of records to return
    """
    service = EvaluationService(db)
    return await service.list_tasks(skip=skip, limit=limit)


@router.post("/{task_id}/trajectory", status_code=201)
async def add_trajectory(
    task_id: str,
    steps: List[TrajectoryStep],
    db: AsyncSession = Depends(get_db),
):
    """
    Add trajectory steps to a task.

    - **task_id**: UUID of the task
    - **steps**: List of trajectory steps
    """
    service = EvaluationService(db)

    # Convert steps to dict format
    steps_data = [step.model_dump() for step in steps]

    success = await service.add_trajectory(task_id, steps_data)

    if not success:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"message": f"Added {len(steps)} trajectory steps", "task_id": task_id}
