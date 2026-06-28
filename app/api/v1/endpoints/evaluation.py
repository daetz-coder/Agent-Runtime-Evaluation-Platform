"""
Evaluation endpoints.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace import AuditAction, WorkspaceRole, add_audit_log
from app.api.workspace_context import WorkspaceContext, get_workspace_context, require_role
from app.core.config import settings
from app.db.database import async_session_factory, get_db
from app.models.schemas import (
    EvaluationListItem,
    EvaluationRequest,
    EvaluationResponse,
    IncrementalEvalRequest,
    IncrementalEvalResponse,
    JudgeRawData,
    ReplayResponse,
    SandboxEvalRequest,
    SandboxEvalResponse,
    StreamEvaluationRequest,
    TrajectoryDiffResponse,
    TrajectoryStep,
)
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
        skip=skip,
        limit=limit,
        status=status,
        workspace_id=ctx.filter_workspace_id(),
    )
    # 通过 response header 返回总数
    from fastapi.responses import JSONResponse

    return JSONResponse(
        content=[e.model_dump(mode="json") for e in evaluations],
        headers={"X-Total-Count": str(total)},
    )


async def _run_evaluation_background(
    task_id: str,
    eval_id: str,
    workspace_id: Optional[str] = None,
):
    """Background task: run evaluation graph and persist results."""
    try:
        async with async_session_factory() as db:
            service = EvaluationService(db)
            result = await service.run_evaluation(
                task_id=task_id,
                context=None,
                workspace_id=workspace_id,
            )
            await db.commit()
            if result is None:
                logger.error("Evaluation %s returned no result for task %s", eval_id, task_id)
                return
            logger.info("Evaluation %s completed for task %s", eval_id, task_id)
            await _notify_webhook(task_id, eval_id, result)
    except Exception as e:
        logger.error("Evaluation %s failed for task %s: %s", eval_id, task_id, e)
        try:
            async with async_session_factory() as db:
                service = EvaluationService(db)
                await service.abort_pending_evaluation(eval_id, task_id, workspace_id=workspace_id)
                await db.commit()
        except Exception as cleanup_err:
            logger.error("Failed to abort evaluation %s: %s", eval_id, cleanup_err)


async def _notify_webhook(task_id: str, eval_id: str, result):
    """Send webhook notification via WebhookService with retry."""
    from app.services.webhook import WebhookService

    await WebhookService.notify(
        "evaluation.completed",
        {
            "task_id": task_id,
            "evaluation_id": eval_id,
        },
    )


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

    from app.services.quota import QuotaExceeded, enforce_workspace_quotas

    try:
        await enforce_workspace_quotas(db, ws_filter)
    except QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))

    service = EvaluationService(db)

    task = await service.get_task(request.task_id, workspace_id=ws_filter)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    evaluation = await service.create_evaluation(
        request.task_id,
        stream_mode=request.use_stream,
        workspace_id=ws_filter,
    )

    if not evaluation:
        raise HTTPException(status_code=500, detail="Evaluation failed to start")

    ws_id = ws_filter or ctx.workspace_id
    if ws_id:
        await add_audit_log(db, ws_id, ctx.user_id, AuditAction.EVAL_CREATED, "evaluation", evaluation.id)

    await db.commit()

    if not request.use_stream:
        # Prefer Celery task queue; fall back to BackgroundTasks
        try:
            from app.celery_app import run_evaluation_task

            run_evaluation_task.delay(
                request.task_id,
                evaluation.id,
                workspace_id=ws_filter,
            )
        except Exception:
            background_tasks.add_task(
                _run_evaluation_background,
                request.task_id,
                evaluation.id,
                ws_filter,
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
        "agent_runtime_enabled": settings.AGENT_RUNTIME_ENABLED,
        "agent_default_tools": settings.AGENT_DEFAULT_TOOLS,
        "sandbox_available": _is_sandbox_ready(),
    }


def _is_sandbox_ready() -> bool:
    """Check if both sandbox subsystems are available."""
    from app.agent_runtime.sandbox.executor import is_sandbox_available
    from app.agent_runtime.sandbox.session_pool import is_session_pool_available

    return is_sandbox_available() or is_session_pool_available()


# ── Agent in Sandbox Endpoints ────────────────────────────────


@router.post("/run", response_model=SandboxEvalResponse)
async def run_sandbox_evaluation(
    request: SandboxEvalRequest,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Run agent in sandbox and evaluate (Agent in Sandbox mode).

    The platform creates a sandbox container, runs a built-in agent that:
    - Reasons with an LLM (configurable model/provider)
    - Executes tools inside the sandbox (python, bash, file operations)
    - Captures full trajectory automatically

    After the agent completes, the 6-dimension evaluation runs on the captured trajectory.

    - **goal**: Task objective for the agent
    - **model**: LLM model (default: from config)
    - **provider**: LLM provider (deepseek/openai/anthropic/zhipuai/qwen)
    - **workspace_files**: Initial files {path: content} for /workspace
    - **tools**: Allowed tools list
    - **max_steps**: Maximum agent steps (default: 20)
    """
    require_role(ctx, WorkspaceRole.EVALUATOR)
    ws_filter = ctx.filter_workspace_id()

    if not settings.AGENT_RUNTIME_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Agent runtime is disabled (AGENT_RUNTIME_ENABLED=false)",
        )

    # Check workspace quotas
    from app.services.quota import QuotaExceeded, enforce_workspace_quotas

    try:
        await enforce_workspace_quotas(
            db,
            ws_filter,
            sandbox=True,
            max_steps=request.max_steps,
        )
    except QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))

    service = EvaluationService(db)
    result = await service.run_sandbox_evaluation(request, workspace_id=ws_filter)

    ws_id = ws_filter or ctx.workspace_id
    if ws_id:
        await add_audit_log(
            db,
            ws_id,
            ctx.user_id,
            AuditAction.EVAL_CREATED,
            "evaluation",
            result.evaluation_id,
            {"mode": "sandbox", "task_id": result.task_id},
        )

    await db.commit()
    return result


@router.post("/run/stream")
async def run_sandbox_evaluation_stream(
    request: SandboxEvalRequest,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    SSE streaming sandbox evaluation — real-time agent steps + evaluation progress.

    Events:
    - agent_step: {step_number, action_type, detail}
    - agent_done: {success, steps_taken, final_answer}
    - eval_progress: {dimension, score, progress, total}
    - result: {evaluation}
    - error: {message}
    - done
    """
    from sse_starlette.sse import EventSourceResponse

    from app.agent_runtime.runner import AgentRunner

    require_role(ctx, WorkspaceRole.EVALUATOR)
    ws_filter = ctx.filter_workspace_id()

    if not settings.AGENT_RUNTIME_ENABLED:
        raise HTTPException(status_code=503, detail="Agent runtime is disabled")

    from app.services.quota import QuotaExceeded, enforce_workspace_quotas

    try:
        await enforce_workspace_quotas(
            db,
            ws_filter,
            sandbox=True,
            max_steps=request.max_steps,
        )
    except QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))

    async def event_generator():
        # Run agent and stream trajectory steps as they happen
        service = EvaluationService(db)

        # Create task first
        from app.models.schemas import TaskCreate
        from app.services.quota import SANDBOX_EVAL_MODE

        sandbox_context = dict(request.context or {})
        sandbox_context["eval_mode"] = SANDBOX_EVAL_MODE
        task_data = TaskCreate(goal=request.goal, context=sandbox_context)
        task_response = await service.create_task(task_data, workspace_id=ws_filter)
        task_id = task_response.id

        yield {"event": "task_created", "data": json.dumps({"task_id": task_id})}

        # Run agent (non-streaming for now — full result)
        runner = AgentRunner()
        agent_result = await runner.run(
            goal=request.goal,
            workspace_files=request.workspace_files,
            tools=request.tools,
            model=request.model,
            provider=request.provider,
            context=request.context,
            max_steps=request.max_steps,
            temperature=request.temperature,
        )

        # Stream trajectory steps
        for step in agent_result.trajectory:
            yield {"event": "agent_step", "data": json.dumps(step, default=str)}

        yield {
            "event": "agent_done",
            "data": json.dumps(
                {
                    "success": agent_result.success,
                    "steps_taken": agent_result.steps_taken,
                    "duration_ms": agent_result.duration_ms,
                    "final_answer": agent_result.final_answer[:500],
                }
            ),
        }

        # Save trajectory and run evaluation
        if agent_result.trajectory:
            await service.add_trajectory(task_id, agent_result.trajectory, workspace_id=ws_filter)

        # Run evaluators with streaming progress
        if agent_result.trajectory and agent_result.success:
            from app.evaluators import (
                MemoryEvaluator,
                PlanningEvaluator,
                ReplanEvaluator,
                RetrievalEvaluator,
                TacticalEvaluator,
                ToolUseEvaluator,
            )
            from app.models.schemas import TrajectoryStep as TS

            steps = [
                TS(
                    step_number=s["step_number"],
                    action_type=s["action_type"],
                    action_detail=s.get("action_detail", {}),
                    observation=s.get("observation"),
                    timestamp=s.get("timestamp"),
                )
                for s in agent_result.trajectory
            ]

            evaluators = [
                ("planning", PlanningEvaluator),
                ("tactical", TacticalEvaluator),
                ("tool_use", ToolUseEvaluator),
                ("memory", MemoryEvaluator),
                ("replan", ReplanEvaluator),
                ("retrieval", RetrievalEvaluator),
            ]
            total = len(evaluators)
            dim_results = {}

            for idx, (dim_name, EvalClass) in enumerate(evaluators, 1):
                try:
                    ev = EvalClass()
                    r = await ev.evaluate(goal=request.goal, trajectory=steps, context=request.context)
                    score = getattr(r, "overall", 0)
                    dim_results[dim_name] = r.model_dump() if hasattr(r, "model_dump") else {"overall": score}
                    yield {
                        "event": "eval_progress",
                        "data": json.dumps(
                            {
                                "dimension": dim_name,
                                "score": score,
                                "progress": idx,
                                "total": total,
                            }
                        ),
                    }
                except Exception as e:
                    dim_results[dim_name] = {"overall": 0, "feedback": str(e)}
                    yield {
                        "event": "error",
                        "data": json.dumps(
                            {
                                "dimension": dim_name,
                                "message": str(e),
                            }
                        ),
                    }

            # Compute overall score
            weights = {
                "planning": 0.20,
                "tactical": 0.20,
                "tool_use": 0.15,
                "memory": 0.15,
                "replan": 0.15,
                "retrieval": 0.15,
            }
            score_values = {d: (dim_results.get(d) or {}).get("overall", 0) for d in weights}
            overall = round(sum(weights[d] * score_values[d] for d in weights), 1)

            yield {
                "event": "result",
                "data": json.dumps(
                    {
                        "scores": score_values,
                        "overall": overall,
                    }
                ),
            }

        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())


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

    from app.services.quota import QuotaExceeded, enforce_workspace_quotas

    service = EvaluationService(db)
    results = []
    for task_id in task_ids:
        task = await service.get_task(task_id, workspace_id=ws_filter)
        if not task:
            results.append({"task_id": task_id, "status": "not_found"})
            continue
        try:
            await enforce_workspace_quotas(db, ws_filter)
        except QuotaExceeded as e:
            results.append({"task_id": task_id, "status": "quota_exceeded", "detail": str(e)})
            continue
        evaluation = await service.create_evaluation(task_id, workspace_id=ws_filter)
        try:
            from app.celery_app import run_evaluation_task

            run_evaluation_task.delay(task_id, evaluation.id, workspace_id=ws_filter)
        except Exception:
            background_tasks.add_task(
                _run_evaluation_background,
                task_id,
                evaluation.id,
                ws_filter,
            )
        results.append(
            {
                "task_id": task_id,
                "evaluation_id": evaluation.id,
                "status": "accepted",
            }
        )
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
    from sse_starlette.sse import EventSourceResponse

    from app.db.models import AgentTask, AgentTrajectory, Evaluation, EvaluationStatus, TaskStatus
    from app.evaluators import (
        MemoryEvaluator,
        PlanningEvaluator,
        ReplanEvaluator,
        RetrievalEvaluator,
        TacticalEvaluator,
        ToolUseEvaluator,
    )
    from app.models.schemas import TrajectoryStep as TS

    require_role(ctx, WorkspaceRole.EVALUATOR)
    ws_filter = ctx.filter_workspace_id()

    from app.services.quota import QuotaExceeded, enforce_workspace_quotas

    try:
        await enforce_workspace_quotas(db, ws_filter)
    except QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))

    service = EvaluationService(db)
    task = await service.get_task(request.task_id, workspace_id=ws_filter)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    traj_result = await db.execute(
        select(AgentTrajectory).where(AgentTrajectory.task_id == request.task_id).order_by(AgentTrajectory.step_number)
    )
    traj_rows = traj_result.scalars().all()
    steps = [
        TS(
            step_number=t.step_number,
            action_type=t.action_type,
            action_detail=t.action_detail or {},
            observation=t.observation,
            timestamp=t.timestamp,
        )
        for t in traj_rows
    ]

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
            await queue.put(
                {
                    "event": "progress",
                    "data": json.dumps(
                        {
                            "dimension": dim_name,
                            "score": score,
                            "progress": current,
                            "total": total,
                        }
                    ),
                }
            )
        except Exception as e:
            dim_results[dim_name] = {"overall": 0, "feedback": str(e)}
            async with progress_lock:
                progress_count += 1
                current = progress_count
            await queue.put(
                {
                    "event": "error",
                    "data": json.dumps(
                        {
                            "dimension": dim_name,
                            "message": str(e),
                        }
                    ),
                }
            )
            await queue.put(
                {
                    "event": "progress",
                    "data": json.dumps(
                        {
                            "dimension": dim_name,
                            "score": 0,
                            "progress": current,
                            "total": total,
                        }
                    ),
                }
            )

    async def yield_completed_evaluation(eval_row: Evaluation):
        """Replay SSE events from a completed evaluation without re-running LLMs."""
        dims = ("planning", "tactical", "tool_use", "memory", "replan", "retrieval")
        score_values: dict = {}
        for index, dim in enumerate(dims, start=1):
            fb = getattr(eval_row, f"{dim}_feedback") or {}
            score = fb.get("overall") if isinstance(fb, dict) else getattr(eval_row, f"{dim}_score", 0)
            score = float(score or 0)
            score_values[dim] = score
            yield {
                "event": "progress",
                "data": json.dumps(
                    {
                        "dimension": dim,
                        "score": score,
                        "progress": index,
                        "total": total,
                    }
                ),
            }
        overall = float(eval_row.overall_score or 0)
        yield {
            "event": "result",
            "data": json.dumps(
                {
                    "scores": score_values,
                    "overall": overall,
                    "evaluation_id": evaluation_id,
                }
            ),
        }
        yield {"event": "done", "data": "{}"}

    async def event_generator():
        if evaluation_id:
            eval_row = await db.get(Evaluation, evaluation_id)
            if eval_row and eval_row.status == EvaluationStatus.COMPLETED:
                if eval_row.task_id != request.task_id:
                    yield {"event": "error", "data": json.dumps({"message": "Evaluation not found for this task"})}
                    return
                async for msg in yield_completed_evaluation(eval_row):
                    yield msg
                return

        await mark_running()

        # Launch all evaluators concurrently (fire-and-forget via task)
        _ = asyncio.ensure_future(asyncio.gather(*[run_eval(dim, cls) for dim, cls in evaluators]))

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
            "planning": 0.20,
            "tactical": 0.20,
            "tool_use": 0.15,
            "memory": 0.15,
            "replan": 0.15,
            "retrieval": 0.15,
        }
        score_values = {d: (dim_results.get(d) or {}).get("overall", 0) for d in weights}
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

        yield {
            "event": "result",
            "data": json.dumps(
                {
                    "scores": score_values,
                    "overall": overall,
                    "evaluation_id": evaluation_id,
                }
            ),
        }
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
        select(AgentTrajectory).where(AgentTrajectory.task_id == task_id).order_by(AgentTrajectory.step_number)
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
            "dimensions": {dim: r.model_dump() for dim, r in results.items()},
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


# ============== Replay Debugger ==============


@router.get("/{evaluation_id}/replay", response_model=ReplayResponse)
async def get_evaluation_replay(
    evaluation_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Get step-by-step replay data for an evaluation.

    Returns each trajectory step with LLM raw prompt/response,
    enabling the frontend replay debugger.
    """
    require_role(ctx, WorkspaceRole.VIEWER)
    from app.db.models import Evaluation
    from app.services.replay_service import ReplayService

    evaluation = await db.get(Evaluation, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # Fetch trajectory
    from app.db.models import AgentTask, AgentTrajectory

    task = await db.get(AgentTask, evaluation.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(
        select(AgentTrajectory).where(AgentTrajectory.task_id == task.id).order_by(AgentTrajectory.step_number)
    )
    steps = result.scalars().all()
    trajectory = [
        {
            "step_number": s.step_number,
            "action_type": s.action_type,
            "action_detail": s.action_detail,
            "observation": s.observation,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
        }
        for s in steps
    ]

    service = ReplayService()
    return await service.get_replay(
        evaluation=evaluation,
        trajectory=trajectory,
        goal=task.goal,
    )


# ============== Judge Transparency ==============


@router.get("/{evaluation_id}/judge-raw", response_model=Dict[str, JudgeRawData])
@router.get("/{evaluation_id}/judge-raw/{dimension}", response_model=Dict[str, JudgeRawData])
async def get_evaluation_judge_raw(
    evaluation_id: str,
    dimension: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Get raw judge LLM prompt and response for evaluation dimensions.

    - **dimension**: Optional — one of planning/tactical/tool_use/memory/replan/retrieval.
      Omit to get all dimensions with available judge raw data.
    """
    require_role(ctx, WorkspaceRole.VIEWER)
    from app.db.models import Evaluation
    from app.services.judge_service import JudgeService

    evaluation = await db.get(Evaluation, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    service = JudgeService()
    return await service.get_judge_raw(evaluation, dimension=dimension)


# ============== Trajectory Diff ==============


@router.get("/diff", response_model=TrajectoryDiffResponse)
async def compare_evaluations(
    base_evaluation_id: str,
    head_evaluation_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Compare trajectories between two evaluations.

    Returns step-by-step diff showing added/removed/changed steps.
    Useful for understanding what changed between two agent runs.
    """
    require_role(ctx, WorkspaceRole.VIEWER)
    from app.db.models import Evaluation
    from app.services.diff_service import DiffService

    service = DiffService()

    base_eval = await db.get(Evaluation, base_evaluation_id)
    head_eval = await db.get(Evaluation, head_evaluation_id)

    if not base_eval or not head_eval:
        raise HTTPException(status_code=404, detail="One or both evaluations not found")

    from app.db.models import AgentTask, AgentTrajectory

    base_task = await db.get(AgentTask, base_eval.task_id)
    head_task = await db.get(AgentTask, head_eval.task_id)

    async def _get_traj(task_id: str) -> list:
        r = await db.execute(
            select(AgentTrajectory).where(AgentTrajectory.task_id == task_id).order_by(AgentTrajectory.step_number)
        )
        return [
            {
                "step_number": s.step_number,
                "action_type": s.action_type,
                "action_detail": s.action_detail,
                "observation": s.observation,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            }
            for s in r.scalars().all()
        ]

    base_traj = await _get_traj(base_eval.task_id)
    head_traj = await _get_traj(head_eval.task_id)

    return await service.compare(
        base_trajectory=base_traj,
        head_trajectory=head_traj,
        base_eval_id=base_evaluation_id,
        head_eval_id=head_evaluation_id,
        base_goal=base_task.goal if base_task else "",
        head_goal=head_task.goal if head_task else "",
    )


# ============== Incremental Evaluation ==============


@router.post("/incremental", response_model=IncrementalEvalResponse)
async def incremental_evaluation(
    request: IncrementalEvalRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Run an incremental evaluation — only re-evaluate dimensions affected by changes.

    Compares the head task's trajectory against the base evaluation's trajectory,
    detects what changed, and re-evaluates only the affected dimensions.
    Unaffected dimension scores are reused from the base evaluation.

    Use ``force_dimensions`` to override and force specific dimensions to re-evaluate.
    """
    require_role(ctx, WorkspaceRole.EVALUATOR)
    from app.services.incremental_eval import IncrementalEvalService

    service = IncrementalEvalService()
    eval_id, reused_dims, re_eval_dims, diff, status, overall_score = await service.incremental_evaluate(
        base_eval_id=request.base_evaluation_id,
        head_task_id=request.head_task_id,
        force_dims=request.force_dimensions,
        workspace_id=ctx.filter_workspace_id(),
    )

    return IncrementalEvalResponse(
        evaluation_id=eval_id,
        task_id=request.head_task_id,
        status=status,
        overall_score=overall_score or 0.0,
        reused_dimensions=reused_dims,
        re_evaluated_dimensions=re_eval_dims,
        changes_detected=[f"Step {s.step_number}: {s.change_type}" for s in diff.steps if s.change_type != "unchanged"],
        diff_summary=diff,
    )


# ============== Regression Detection ==============


@router.get("/regression/check")
async def check_regression(
    base_evaluation_id: str,
    head_evaluation_id: str,
    include_diff: bool = True,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Compare two evaluations and detect score regressions.

    Returns per-dimension score deltas, regression flags, and optionally
    a trajectory diff explaining *why* the regression occurred.
    Useful for CI gate: block PRs that degrade agent performance.
    """
    require_role(ctx, WorkspaceRole.VIEWER)
    from app.services.regression_detection import RegressionDetectionService

    service = RegressionDetectionService()
    report = await service.compare(
        base_eval_id=base_evaluation_id,
        head_eval_id=head_evaluation_id,
        include_diff=include_diff,
    )

    return {
        "base_evaluation_id": report.base_evaluation_id,
        "head_evaluation_id": report.head_evaluation_id,
        "has_regression": report.has_regression,
        "overall_change": report.overall_change,
        "summary": report.summary,
        "dimensions": {
            dim: {
                "base_score": dim_info.base_score,
                "head_score": dim_info.head_score,
                "delta": dim_info.delta,
                "is_regression": dim_info.is_regression,
                "threshold": dim_info.threshold,
            }
            for dim, dim_info in report.dimensions.items()
        },
        "diff": report.diff.model_dump() if report.diff else None,
    }
