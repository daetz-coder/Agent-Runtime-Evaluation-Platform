"""
Evaluation endpoints.
"""

import logging
import json
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db, async_session_factory
from app.core.config import settings
from app.models.schemas import EvaluationRequest, EvaluationResponse, EvaluationListItem, TrajectoryStep
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
    evaluations, total = await service.list_evaluations_with_count(skip=skip, limit=limit, status=status)
    # 通过 response header 返回总数
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=[e.model_dump(mode="json") for e in evaluations],
        headers={"X-Total-Count": str(total)},
    )


async def _run_evaluation_background(task_id: str, eval_id: str):
    """Background task: run evaluation graph and persist results."""
    try:
        async with async_session_factory() as db:
            service = EvaluationService(db)
            result = await service.run_evaluation(task_id=task_id, context=None)
            await db.commit()
            logger.info(f"Evaluation {eval_id} completed for task {task_id}")
            # Webhook 通知
            await _notify_webhook(task_id, eval_id, result)
    except Exception as e:
        logger.error(f"Evaluation {eval_id} failed for task {task_id}: {e}")


async def _notify_webhook(task_id: str, eval_id: str, result):
    """发送 webhook 通知（如果配置了 EVAL_WEBHOOK_URL）。"""
    webhook_url = settings.EVAL_WEBHOOK_URL if hasattr(settings, 'EVAL_WEBHOOK_URL') else ""
    if not webhook_url:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(webhook_url, json={
                "event": "evaluation.completed",
                "task_id": task_id,
                "evaluation_id": eval_id,
            })
    except Exception:
        logger.debug("Webhook notification failed")


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
    task_id: str = Body(..., embed=True),
    context: Optional[Dict[str, Any]] = Body(None, embed=True),
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


@router.post("/batch")
async def batch_evaluation(
    task_ids: List[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    批量评估多个任务（异步）。

    - **task_ids**: 任务 ID 列表
    """
    service = EvaluationService(db)
    results = []
    for task_id in task_ids:
        task = await service.get_task(task_id)
        if not task:
            results.append({"task_id": task_id, "status": "not_found"})
            continue
        evaluation = await service.create_evaluation(task_id)
        background_tasks.add_task(_run_evaluation_background, task_id, evaluation.id)
        results.append({
            "task_id": task_id,
            "evaluation_id": evaluation.id,
            "status": "accepted",
        })
    return {"batch_size": len(task_ids), "results": results}


@router.post("/stream")
async def evaluation_stream(
    task_id: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE 流式评估 — 每个评估器完成时实时推送分数。

    - **task_id**: 任务 UUID

    事件类型:
    - progress: {dimension, score, progress, total}
    - result: {scores: {...}, overall: ...}
    - error: {message}
    - done
    """
    from app.evaluators import (
        PlanningEvaluator, TacticalEvaluator, ToolUseEvaluator,
        MemoryEvaluator, ReplanEvaluator,
            RetrievalEvaluator,
    )
    from app.models.schemas import TrajectoryStep as TS
    from sse_starlette.sse import EventSourceResponse
    import asyncio

    # Verify task
    service = EvaluationService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get trajectory
    traj_result = await db.execute(
        select(AgentTrajectory).where(AgentTrajectory.task_id == task_id)
        .order_by(AgentTrajectory.step_number)
    )
    traj_rows = traj_result.scalars().all()
    steps = [TS(
        step_number=t.step_number, action_type=t.action_type,
        action_detail=t.action_detail or {}, observation=t.observation,
        timestamp=t.timestamp,
    ) for t in traj_rows]

    evaluators = [
        ("planning", PlanningEvaluator),
        ("tactical", TacticalEvaluator),
        ("tool_use", ToolUseEvaluator),
        ("memory", MemoryEvaluator),
        ("replan", ReplanEvaluator),
        ("retrieval", RetrievalEvaluator),
    ]
    total = len(evaluators)
    scores: dict = {}
    queue: asyncio.Queue = asyncio.Queue()

    async def run_eval(dim_name: str, EvalClass):
        try:
            ev = EvalClass()
            r = await ev.evaluate(goal=task.goal, trajectory=steps, context=task.context)
            score = getattr(r, "overall", 0)
            scores[dim_name] = score
            await queue.put({"event": "progress", "data": json.dumps({
                "dimension": dim_name, "score": score,
                "progress": len(scores), "total": total,
            })})
        except Exception as e:
            await queue.put({"event": "error", "data": json.dumps({
                "dimension": dim_name, "message": str(e),
            })})

    async def event_generator():
        # Start all evaluators
        asyncio.create_task(asyncio.gather(*[
            run_eval(dim, cls) for dim, cls in evaluators
        ]))

        completed = 0
        while completed < total:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=120)
                yield msg
                if msg["event"] == "progress":
                    completed = json.loads(msg["data"])["progress"]
                    if completed >= total:
                        break
            except asyncio.TimeoutError:
                yield {"event": "error", "data": json.dumps({"message": "Evaluation timeout"})}
                break

        # Send final result
        if scores:
            weights = {"planning": 0.20, "tactical": 0.20, "tool_use": 0.15, "memory": 0.15, "replan": 0.15, "retrieval": 0.15}
            overall = sum(weights.get(d, 0) * s for d, s in scores.items())
            yield {"event": "result", "data": json.dumps({
                "scores": scores, "overall": round(overall, 1),
            })}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())


@router.post("/consensus")
async def consensus_evaluation(
    task_id: str = Body(..., embed=True),
    include_all: bool = Body(False, embed=True),
    db: AsyncSession = Depends(get_db),
):
    """
    多模型共识评估 — DeepSeek + OpenAI + Anthropic 独立评分。

    - **task_id**: 任务 UUID
    - **include_all**: 是否返回所有 5 个维度的共识结果

    返回均值 (mean_score)、标准差 (std_score，一致性指标，越小越可信)、各模型分数。
    """
    from app.evaluators.consensus import ConsensusEvaluator

    # 获取任务和轨迹
    service = EvaluationService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 获取轨迹步骤
    from app.db.models import AgentTrajectory
    result = await db.execute(
        select(AgentTrajectory).where(AgentTrajectory.task_id == task_id)
        .order_by(AgentTrajectory.step_number)
    )
    trajectory_rows = result.scalars().all()

    trajectory = [
        TrajectoryStep(
            step_number=t.step_number,
            action_type=t.action_type,
            action_detail=t.action_detail or {},
            observation=t.observation,
            timestamp=t.timestamp,
        )
        for t in trajectory_rows
    ]

    evaluator = ConsensusEvaluator()

    if include_all:
        results = await evaluator.evaluate_all_dimensions(task.goal, trajectory, task.context)
        return {
            "task_id": task_id,
            "available_providers": evaluator.available_providers,
            "dimensions": {
                dim: r.model_dump() for dim, r in results.items()
            },
        }
    else:
        result = await evaluator.evaluate(task.goal, trajectory, task.context)
        return {
            "task_id": task_id,
            "available_providers": evaluator.available_providers,
            "result": result.model_dump(),
        }


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
