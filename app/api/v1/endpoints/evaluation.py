"""
Evaluation endpoints.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Annotated, List, Optional, Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.workspace import AuditAction, WorkspaceRole, add_audit_log
from app.api.workspace_context import WorkspaceContext, get_workspace_context, require_role
from app.db.database import get_db, async_session_factory
from app.core.config import settings
from app.models.schemas import EvaluationRequest, EvaluationResponse, EvaluationListItem, TrajectoryStep, StreamEvaluationRequest
from app.services.evaluation_service import EvaluationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[EvaluationListItem])
async def list_evaluations(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """List evaluations with pagination."""
    require_role(ctx, WorkspaceRole.VIEWER)
    service = EvaluationService(db)
    evaluations, total = await service.list_evaluations_with_count(
        skip=skip, limit=limit, status=status, workspace_id=ctx.filter_workspace_id(),
    )
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
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Run evaluation for a task (truly async).

    - **task_id**: UUID of the task to evaluate
    - **include_details**: Include detailed feedback (default: true)

    Returns immediately with the evaluation ID (status=in_progress).
    When use_stream=false (default), evaluation runs in background — poll GET /evaluations/{id}.
    When use_stream=true, call POST /evaluations/stream from the client for live progress.
    """
    require_role(ctx, WorkspaceRole.EVALUATOR)
    ws_filter = ctx.filter_workspace_id()
    service = EvaluationService(db)

    task = await service.get_task(request.task_id, workspace_id=ws_filter)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    evaluation = await service.create_evaluation(
        request.task_id, stream_mode=request.use_stream, workspace_id=ws_filter,
    )

    if not evaluation:
        raise HTTPException(status_code=500, detail="Evaluation failed to start")

    ws_id = ws_filter or ctx.workspace_id
    if ws_id:
        await add_audit_log(db, ws_id, ctx.user_id, AuditAction.EVAL_CREATED, "evaluation", evaluation.id)

    await db.commit()

    if not request.use_stream:
        background_tasks.add_task(
            _run_evaluation_background,
            request.task_id,
            evaluation.id,
        )

    return evaluation


@router.get("/settings")
async def get_eval_settings():
    """返回评估公开配置（不含密钥）。"""
    return {
        "default_provider": settings.DEFAULT_LLM_PROVIDER,
        "parallel_enabled": settings.EVAL_PARALLEL,
        "auth_enabled": settings.AUTH_ENABLED,
        "webhook_configured": bool(settings.EVAL_WEBHOOK_URL),
    }


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Get evaluation by ID.

    - **evaluation_id**: UUID of the evaluation
    """
    require_role(ctx, WorkspaceRole.VIEWER)
    service = EvaluationService(db)
    evaluation = await service.get_evaluation(evaluation_id, workspace_id=ctx.filter_workspace_id())

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return evaluation


@router.post("/quick", response_model=EvaluationResponse)
async def quick_evaluation(
    task_id: str = Body(..., embed=True),
    context: Optional[Dict[str, Any]] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Quick evaluation endpoint (synchronous).

    - **task_id**: UUID of the task to evaluate
    - **context**: Optional additional context

    Note: This runs synchronously and may take some time.
    Use the async endpoint for better performance.
    """
    require_role(ctx, WorkspaceRole.EVALUATOR)
    ws_filter = ctx.filter_workspace_id()
    service = EvaluationService(db)

    task = await service.get_task(task_id, workspace_id=ws_filter)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    evaluation = await service.run_evaluation(task_id=task_id, context=context, workspace_id=ws_filter)

    if not evaluation:
        raise HTTPException(status_code=500, detail="Evaluation failed")

    return evaluation


@router.post("/batch")
async def batch_evaluation(
    background_tasks: BackgroundTasks,
    task_ids: Annotated[List[str], Body(embed=True)],
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    批量评估多个任务（异步）。

    - **task_ids**: 任务 ID 列表
    """
    require_role(ctx, WorkspaceRole.EVALUATOR)
    ws_filter = ctx.filter_workspace_id()
    service = EvaluationService(db)
    results = []
    for task_id in task_ids:
        task = await service.get_task(task_id, workspace_id=ws_filter)
        if not task:
            results.append({"task_id": task_id, "status": "not_found"})
            continue
        evaluation = await service.create_evaluation(task_id, workspace_id=ws_filter)
        background_tasks.add_task(_run_evaluation_background, task_id, evaluation.id)
        results.append({
            "task_id": task_id,
            "evaluation_id": evaluation.id,
            "status": "accepted",
        })
    return {"batch_size": len(task_ids), "results": results}


@router.post("/stream")
async def evaluation_stream(
    request: StreamEvaluationRequest,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    SSE 流式评估 — 每个评估器完成时实时推送分数，可选持久化到 evaluation_id。

    事件类型:
    - progress: {dimension, score, progress, total}
    - result: {scores, overall}
    - error: {message}
    - done
    """
    from app.evaluators import (
        PlanningEvaluator, TacticalEvaluator, ToolUseEvaluator,
        MemoryEvaluator, ReplanEvaluator,
        RetrievalEvaluator,
    )
    from app.db.models import AgentTrajectory, AgentTask, TaskStatus, Evaluation, EvaluationStatus
    from app.models.schemas import TrajectoryStep as TS
    from sse_starlette.sse import EventSourceResponse

    require_role(ctx, WorkspaceRole.EVALUATOR)
    ws_filter = ctx.filter_workspace_id()
    service = EvaluationService(db)
    task = await service.get_task(request.task_id, workspace_id=ws_filter)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    traj_result = await db.execute(
        select(AgentTrajectory).where(AgentTrajectory.task_id == request.task_id)
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
    dim_results: dict = {}
    queue: asyncio.Queue = asyncio.Queue()
    progress_lock = asyncio.Lock()
    progress_count = 0
    task_id = request.task_id
    evaluation_id = request.evaluation_id

    async def mark_running():
        if not evaluation_id:
            return
        async with async_session_factory() as session:
            task_row = await session.get(AgentTask, task_id)
            if task_row:
                task_row.status = TaskStatus.RUNNING
                task_row.started_at = task_row.started_at or datetime.now(timezone.utc)
                await session.commit()

    async def run_eval(dim_name: str, EvalClass):
        nonlocal progress_count
        try:
            ev = EvalClass()
            r = await ev.evaluate(goal=task.goal, trajectory=steps, context=task.context)
            score = getattr(r, "overall", 0)
            dim_results[dim_name] = r.model_dump() if hasattr(r, "model_dump") else {"overall": score}
            async with progress_lock:
                progress_count += 1
                current = progress_count
            await queue.put({"event": "progress", "data": json.dumps({
                "dimension": dim_name, "score": score,
                "progress": current, "total": total,
            })})
        except Exception as e:
            dim_results[dim_name] = {"overall": 0, "feedback": str(e)}
            async with progress_lock:
                progress_count += 1
                current = progress_count
            await queue.put({"event": "error", "data": json.dumps({
                "dimension": dim_name, "message": str(e),
            })})
            await queue.put({"event": "progress", "data": json.dumps({
                "dimension": dim_name, "score": 0,
                "progress": current, "total": total,
            })})

    async def yield_completed_evaluation(eval_row: Evaluation):
        """Replay SSE events from a completed evaluation without re-running LLMs."""
        dims = ("planning", "tactical", "tool_use", "memory", "replan", "retrieval")
        score_values: dict = {}
        for index, dim in enumerate(dims, start=1):
            fb = getattr(eval_row, f"{dim}_feedback") or {}
            score = fb.get("overall") if isinstance(fb, dict) else getattr(eval_row, f"{dim}_score", 0)
            score = float(score or 0)
            score_values[dim] = score
            yield {"event": "progress", "data": json.dumps({
                "dimension": dim, "score": score, "progress": index, "total": total,
            })}
        overall = float(eval_row.overall_score or 0)
        yield {"event": "result", "data": json.dumps({
            "scores": score_values, "overall": overall, "evaluation_id": evaluation_id,
        })}
        yield {"event": "done", "data": "{}"}

    async def event_generator():
        if evaluation_id:
            eval_row = await db.get(Evaluation, evaluation_id)
            if eval_row and eval_row.status == EvaluationStatus.COMPLETED:
                async for msg in yield_completed_evaluation(eval_row):
                    yield msg
                return

        await mark_running()

        # Launch all evaluators concurrently (fire-and-forget via task)
        _ = asyncio.ensure_future(asyncio.gather(*[
            run_eval(dim, cls) for dim, cls in evaluators
        ]))

        completed = 0
        while completed < total:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=180)
                yield msg
                if msg["event"] == "progress":
                    completed = json.loads(msg["data"])["progress"]
            except asyncio.TimeoutError:
                yield {"event": "error", "data": json.dumps({"message": "Evaluation timeout"})}
                return

        weights = {
            "planning": 0.20, "tactical": 0.20, "tool_use": 0.15,
            "memory": 0.15, "replan": 0.15, "retrieval": 0.15,
        }
        score_values = {
            d: (dim_results.get(d) or {}).get("overall", 0)
            for d in weights
        }
        overall = round(sum(weights[d] * score_values[d] for d in weights), 1)
        parallel_result = {**dim_results, "overall": {"overall_score": overall}}

        if evaluation_id:
            try:
                async with async_session_factory() as session:
                    svc = EvaluationService(session)
                    await svc.finalize_from_parallel(evaluation_id, task_id, parallel_result)
                    await session.commit()
            except Exception as e:
                logger.error("Failed to persist stream evaluation %s: %s", evaluation_id, e)
                yield {"event": "error", "data": json.dumps({"message": f"Persist failed: {e}"})}

        yield {"event": "result", "data": json.dumps({
            "scores": score_values, "overall": overall,
            "evaluation_id": evaluation_id,
        })}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())


@router.post("/consensus")
async def consensus_evaluation(
    task_id: str = Body(..., embed=True),
    include_all: bool = Body(False, embed=True),
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    多模型共识评估 — DeepSeek + OpenAI + Anthropic 独立评分。

    - **task_id**: 任务 UUID
    - **include_all**: 是否返回所有 6 个维度的共识结果

    返回均值 (mean_score)、标准差 (std_score，一致性指标，越小越可信)、各模型分数。
    """
    from app.evaluators.consensus import ConsensusEvaluator

    # 获取任务和轨迹
    require_role(ctx, WorkspaceRole.EVALUATOR)
    ws_filter = ctx.filter_workspace_id()
    service = EvaluationService(db)
    task = await service.get_task(task_id, workspace_id=ws_filter)
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
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Delete an evaluation record.

    - **evaluation_id**: UUID of the evaluation
    """
    require_role(ctx, WorkspaceRole.ADMIN)
    service = EvaluationService(db)
    deleted = await service.delete_evaluation(evaluation_id, workspace_id=ctx.filter_workspace_id())

    if not deleted:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return {"message": "Evaluation deleted", "evaluation_id": evaluation_id}
