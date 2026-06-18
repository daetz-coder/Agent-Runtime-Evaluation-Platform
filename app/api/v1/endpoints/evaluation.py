"""
Evaluation endpoints.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, async_session_factory
from app.models.schemas import EvaluationRequest, EvaluationResponse, EvaluationListItem
from app.services.evaluation_service import EvaluationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[EvaluationListItem])
async def list_evaluations(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List evaluations with pagination."""
    service = EvaluationService(db)
    return await service.list_evaluations(skip=skip, limit=limit, status=status)


async def _run_evaluation_background(task_id: str, eval_id: str):
    """Background task: run evaluation graph and persist results."""
    try:
        async with async_session_factory() as db:
            service = EvaluationService(db)
            await service.run_evaluation(task_id=task_id, context=None)
            await db.commit()
            logger.info(f"Evaluation {eval_id} completed for task {task_id}")
    except Exception as e:
        logger.error(f"Evaluation {eval_id} failed for task {task_id}: {e}")


@router.post("/", response_model=EvaluationResponse, status_code=202)
async def run_evaluation(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Run evaluation for a task (truly async).

    - **task_id**: UUID of the task to evaluate
    - **include_details**: Include detailed feedback (default: true)

    Returns immediately with the evaluation ID (status=in_progress).
    The evaluation runs in the background.
    Poll GET /evaluations/{id} until status becomes 'completed' or 'failed'.
    """
    service = EvaluationService(db)

    # Verify task exists
    task = await service.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Create evaluation record (IN_PROGRESS) and return immediately
    evaluation = await service.create_evaluation(request.task_id)

    if not evaluation:
        raise HTTPException(status_code=500, detail="Evaluation failed to start")

    # 显式 commit — 确保前端立即跳转时 GET 能查到这条记录
    await db.commit()

    # Run the actual evaluation in background
    background_tasks.add_task(
        _run_evaluation_background,
        request.task_id,
        evaluation.id,
    )

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


@router.delete("/{evaluation_id}")
async def delete_evaluation(
    evaluation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an evaluation record.

    - **evaluation_id**: UUID of the evaluation
    """
    service = EvaluationService(db)
    deleted = await service.delete_evaluation(evaluation_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return {"message": "Evaluation deleted", "evaluation_id": evaluation_id}
