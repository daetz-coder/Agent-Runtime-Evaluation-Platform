"""
Evaluation endpoints.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.schemas import EvaluationRequest, EvaluationResponse
from app.services.evaluation_service import EvaluationService

router = APIRouter()


@router.post("/", response_model=EvaluationResponse, status_code=202)
async def run_evaluation(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Run evaluation for a task.

    - **task_id**: UUID of the task to evaluate
    - **include_details**: Include detailed feedback (default: true)

    This endpoint starts an asynchronous evaluation process.
    Use the returned evaluation ID to check status and get results.
    """
    service = EvaluationService(db)

    # Verify task exists
    task = await service.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Run evaluation
    evaluation = await service.run_evaluation(
        task_id=request.task_id,
        context=None,
    )

    if not evaluation:
        raise HTTPException(status_code=500, detail="Evaluation failed to start")

    return evaluation


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get evaluation by ID.

    - **evaluation_id**: UUID of the evaluation
    """
    service = EvaluationService(db)
    evaluation = await service.get_evaluation(evaluation_id)

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return evaluation


@router.post("/quick", response_model=EvaluationResponse)
async def quick_evaluation(
    task_id: str,
    context: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Quick evaluation endpoint (synchronous).

    - **task_id**: UUID of the task to evaluate
    - **context**: Optional additional context

    Note: This runs synchronously and may take some time.
    Use the async endpoint for better performance.
    """
    service = EvaluationService(db)

    # Verify task exists
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Run evaluation synchronously
    evaluation = await service.run_evaluation(
        task_id=task_id,
        context=context,
    )

    if not evaluation:
        raise HTTPException(status_code=500, detail="Evaluation failed")

    return evaluation
