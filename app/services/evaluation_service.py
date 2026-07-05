"""
Evaluation service for orchestrating agent evaluations.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.metrics import EVALUATION_COUNT, EVALUATION_SCORE
from app.core.tracing import get_tracer
from app.db.models import AgentTask, AgentTrajectory, Evaluation, EvaluationStatus, TaskStatus
from app.evaluators.scoring import dimension_score, score_values, weighted_overall
from app.graphs.evaluation_graph import EvaluationState, create_evaluation_graph
from app.models.schemas import (
    AgentRunInfo,
    EvaluationListItem,
    EvaluationResponse,
    OverallEvaluation,
    RetrievalScore,
    SandboxEvalRequest,
    SandboxEvalResponse,
    TaskCreate,
    TaskResponse,
)

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

from app.constants import DIMENSION_LABELS


class EvaluationService:
    """Service for managing agent evaluations."""

    _local_stream_claims: set[str] = set()
    _stream_claim_lock = asyncio.Lock()

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _eval_dashboard_cache_key(workspace_id: Optional[str]) -> str:
        return f"eval_dashboard:{workspace_id or 'all'}"

    async def _invalidate_eval_caches(self, task_id: str, workspace_id: Optional[str] = None) -> None:
        """Invalidate report/task/dashboard caches after eval lifecycle changes."""
        from app.core.cache import cache_delete, cache_delete_pattern

        await cache_delete_pattern("report:*")
        await cache_delete(f"task:{task_id}")
        await cache_delete(f"trajectory:{task_id}")
        await cache_delete(self._dashboard_cache_key(workspace_id))
        await cache_delete(self._eval_dashboard_cache_key(workspace_id))

    @classmethod
    async def try_claim_stream(cls, evaluation_id: str, ttl: int = 600) -> bool:
        """Claim an evaluation stream to prevent duplicate concurrent LLM runs."""
        from app.core.cache import _client, cache_set_nx

        key = f"stream:claim:{evaluation_id}"
        if _client() is not None:
            return await cache_set_nx(key, True, ttl)
        async with cls._stream_claim_lock:
            if evaluation_id in cls._local_stream_claims:
                return False
            cls._local_stream_claims.add(evaluation_id)
            return True

    @classmethod
    async def release_stream_claim(cls, evaluation_id: str) -> None:
        """Release a stream claim after SSE completes."""
        from app.core.cache import _client, cache_delete

        await cache_delete(f"stream:claim:{evaluation_id}")
        if _client() is None:
            async with cls._stream_claim_lock:
                cls._local_stream_claims.discard(evaluation_id)

    @staticmethod
    def _dashboard_cache_key(workspace_id: Optional[str]) -> str:
        return f"dashboard:{workspace_id or 'all'}:counters"

    async def _fail_evaluation(
        self,
        evaluation: Evaluation,
        task: AgentTask,
        previous_status: TaskStatus,
        task_id: str,
    ) -> None:
        """Mark evaluation failed and restore task status."""
        evaluation.status = EvaluationStatus.FAILED
        task.status = previous_status
        await self.db.flush()
        await self._invalidate_eval_caches(task_id, task.workspace_id)

    async def abort_pending_evaluation(
        self,
        eval_id: str,
        task_id: str,
        workspace_id: Optional[str] = None,
    ) -> None:
        """Mark a stuck IN_PROGRESS evaluation as failed (background/Celery cleanup)."""
        task = await self._get_task_model(task_id, workspace_id=workspace_id)
        if not task:
            return

        result = await self.db.execute(select(Evaluation).where(Evaluation.id == eval_id))
        evaluation = result.scalar_one_or_none()
        if not evaluation or evaluation.status != EvaluationStatus.IN_PROGRESS:
            return

        previous_status = TaskStatus.PENDING if task.status == TaskStatus.RUNNING else task.status
        await self._fail_evaluation(evaluation, task, previous_status, task_id)

    @staticmethod
    def _task_to_response(task: AgentTask) -> TaskResponse:
        return TaskResponse(
            id=task.id,
            goal=task.goal,
            context=task.context,
            status=task.status.value,
            workspace_id=task.workspace_id,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )

    async def create_task(
        self,
        task_data: TaskCreate,
        workspace_id: Optional[str] = None,
    ) -> TaskResponse:
        """Create a new agent task."""
        task_id = task_data.id or str(uuid.uuid4())

        existing = await self._get_task_model(task_id)
        if existing:
            if existing.workspace_id != workspace_id:
                raise ValueError(f"Task {task_id} already exists in a different workspace scope")
            return self._task_to_response(existing)

        task = AgentTask(
            id=task_id,
            workspace_id=workspace_id,
            goal=task_data.goal,
            context=task_data.context,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(task)
        await self.db.flush()

        from app.core.cache import cache_delete

        await cache_delete(self._dashboard_cache_key(workspace_id))

        return self._task_to_response(task)

    async def get_task(self, task_id: str, workspace_id: Optional[str] = None) -> Optional[TaskResponse]:
        """Get task by ID."""
        from app.core.cache import cache_get, cache_set

        cache_key = f"task:{task_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            response = TaskResponse(**cached)
            if workspace_id and response.workspace_id != workspace_id:
                return None
            return response

        task = await self._get_task_model(task_id, workspace_id=workspace_id)
        if not task:
            return None

        response = self._task_to_response(task)
        await cache_set(cache_key, response.model_dump(mode="json"), ttl=settings.CACHE_TASK_TTL)
        return response

    async def update_task(
        self,
        task_id: str,
        task_data,
        workspace_id: Optional[str] = None,
    ) -> Optional[TaskResponse]:
        """Update an existing task."""
        task = await self._get_task_model(task_id, workspace_id=workspace_id)
        if not task:
            return None

        if task_data.goal is not None:
            task.goal = task_data.goal
        if task_data.context is not None:
            task.context = task_data.context
        if task_data.status is not None:
            try:
                task.status = TaskStatus(task_data.status)
            except ValueError:
                pass

        await self.db.flush()

        from app.core.cache import cache_delete

        await cache_delete(f"task:{task_id}")
        await cache_delete(self._dashboard_cache_key(workspace_id))
        await cache_delete(self._dashboard_cache_key(task.workspace_id))

        return self._task_to_response(task)

    async def add_trajectory(
        self,
        task_id: str,
        steps: List[Dict[str, Any]],
        workspace_id: Optional[str] = None,
    ) -> bool:
        """Add trajectory steps to a task."""
        task = await self._get_task_model(task_id, workspace_id=workspace_id)
        if not task:
            return False

        existing = await self.db.execute(
            select(AgentTrajectory.step_number).where(AgentTrajectory.task_id == task_id)
        )
        existing_numbers = set(existing.scalars().all())

        # Add trajectory steps
        for step_data in steps:
            step_number = step_data.get("step_number", 0)
            if step_number in existing_numbers:
                continue
            existing_numbers.add(step_number)

            observation = step_data.get("observation")
            if observation is not None and not isinstance(observation, str):
                observation = json.dumps(observation, ensure_ascii=False, default=str)

            timestamp_raw = step_data.get("timestamp", datetime.now(timezone.utc))
            if isinstance(timestamp_raw, str):
                try:
                    timestamp_raw = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    timestamp_raw = datetime.now(timezone.utc)
            if isinstance(timestamp_raw, datetime):
                if timestamp_raw.tzinfo is None:
                    timestamp_raw = timestamp_raw.replace(tzinfo=timezone.utc)
                else:
                    timestamp_raw = timestamp_raw.astimezone(timezone.utc)

            trajectory = AgentTrajectory(
                task_id=task_id,
                step_number=step_data.get("step_number", 0),
                action_type=step_data.get("action_type", "unknown"),
                action_detail=step_data.get("action_detail", {}),
                observation=observation,
                timestamp=timestamp_raw,
            )
            self.db.add(trajectory)

        await self.db.flush()

        # Invalidate trajectory cache
        from app.core.cache import cache_delete

        await cache_delete(f"trajectory:{task_id}")

        return True

    async def create_evaluation(
        self,
        task_id: str,
        stream_mode: bool = False,
        workspace_id: Optional[str] = None,
    ) -> Tuple[Optional[EvaluationResponse], bool]:
        """Create an evaluation record (IN_PROGRESS) without running the graph.

        Returns:
            Tuple of (response, created_new) — created_new is False when reusing IN_PROGRESS.
        """
        task = await self._get_task_model(task_id, workspace_id=workspace_id)
        if not task:
            return None, False

        result = await self.db.execute(
            select(Evaluation)
            .where(
                Evaluation.task_id == task_id,
                Evaluation.status == EvaluationStatus.IN_PROGRESS,
            )
            .order_by(Evaluation.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return (
                EvaluationResponse(
                    id=existing.id,
                    task_id=existing.task_id,
                    status=existing.status.value,
                    stream_mode=existing.stream_mode,
                    created_at=existing.created_at,
                    completed_at=existing.completed_at,
                    evaluation=None,
                ),
                False,
            )

        eval_id = str(uuid.uuid4())
        evaluation = Evaluation(
            id=eval_id,
            task_id=task_id,
            status=EvaluationStatus.IN_PROGRESS,
            stream_mode=stream_mode,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(evaluation)
        await self.db.flush()

        return (
            EvaluationResponse(
                id=evaluation.id,
                task_id=evaluation.task_id,
                status=evaluation.status.value,
                stream_mode=evaluation.stream_mode,
                created_at=evaluation.created_at,
                completed_at=None,
                evaluation=None,
            ),
            True,
        )

    async def run_evaluation(
        self,
        task_id: str,
        context: Optional[Dict[str, Any]] = None,
        workspace_id: Optional[str] = None,
        evaluation_id: Optional[str] = None,
    ) -> Optional[EvaluationResponse]:
        """Run evaluation for a task."""
        task = await self._get_task_model(task_id, workspace_id=workspace_id)
        if not task:
            return None

        # Get trajectory
        trajectory = await self._get_trajectory(task_id)

        # Use the requested evaluation record, or the latest IN_PROGRESS one
        if evaluation_id:
            result = await self.db.execute(select(Evaluation).where(Evaluation.id == evaluation_id))
            evaluation = result.scalar_one_or_none()
            if not evaluation or evaluation.task_id != task_id:
                return None
            if evaluation.status == EvaluationStatus.COMPLETED:
                return await self.get_evaluation(evaluation_id, workspace_id=workspace_id)
            if evaluation.status != EvaluationStatus.IN_PROGRESS:
                return None
        else:
            result = await self.db.execute(
                select(Evaluation)
                .where(
                    Evaluation.task_id == task_id,
                    Evaluation.status == EvaluationStatus.IN_PROGRESS,
                )
                .order_by(Evaluation.created_at.desc())
                .limit(1)
            )
            evaluation = result.scalar_one_or_none()
            if not evaluation:
                eval_id = str(uuid.uuid4())
                from app.agent_runtime.prompts import PROMPT_VERSION

                evaluation = Evaluation(
                    id=eval_id,
                    task_id=task_id,
                    status=EvaluationStatus.IN_PROGRESS,
                    created_at=datetime.now(timezone.utc),
                    prompt_version=PROMPT_VERSION,
                    model_name=settings.DEFAULT_LLM_MODEL,
                    model_provider=settings.DEFAULT_LLM_PROVIDER,
                )
                self.db.add(evaluation)
                await self.db.flush()

        # Task transitions to RUNNING when evaluation actually starts
        previous_status = task.status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Invalidate task cache (status changed)
        from app.core.cache import cache_delete

        await cache_delete(f"task:{task_id}")

        try:
            # Prepare state for graph
            state: EvaluationState = {
                "task_id": task_id,
                "goal": task.goal,
                "trajectory": trajectory,
                "context": context or task.context,
                "planning_score": None,
                "tactical_score": None,
                "tool_use_score": None,
                "memory_score": None,
                "replan_score": None,
                "retrieval_score": None,
                "overall_evaluation": None,
                "error": None,
            }

            # Run evaluation graph (parallel if configured)
            use_parallel = getattr(settings, "EVAL_PARALLEL", True)  # 默认并行
            with tracer.start_as_current_span("evaluation") as eval_span:
                eval_span.set_attribute("parallel", use_parallel)
                if use_parallel:
                    from app.graphs.evaluation_graph import evaluate_parallel
                    from app.models.schemas import TrajectoryStep as TS

                    steps = [
                        TS(
                            step_number=s["step_number"],
                            action_type=s["action_type"],
                            action_detail=s.get("action_detail", {}),
                            observation=s.get("observation"),
                            timestamp=s.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        )
                        for s in trajectory
                    ]
                    parallel_result = await evaluate_parallel(task.goal, steps, context or task.context)
                    overall_eval = self._build_overall_from_parallel(parallel_result)
                    overall = overall_eval.model_dump()
                    self._merge_judge_raw_into_overall(overall, parallel_result)
                    result = {"overall_evaluation": overall, "error": None}
                else:
                    graph = create_evaluation_graph()
                    result = await graph.ainvoke(state)
                    overall = result.get("overall_evaluation", {})

            # Check for errors
            if result.get("error"):
                await self._fail_evaluation(evaluation, task, previous_status, task_id)
                return None

            if not overall:
                await self._fail_evaluation(evaluation, task, previous_status, task_id)
                return None

            return await self._persist_evaluation_results(evaluation, task, overall)

        except Exception:
            logger.exception("Evaluation failed for task %s", task_id)
            await self._fail_evaluation(evaluation, task, previous_status, task_id)
            raise

    async def get_evaluation(
        self,
        eval_id: str,
        workspace_id: Optional[str] = None,
    ) -> Optional[EvaluationResponse]:
        """Get evaluation by ID."""
        query = select(Evaluation).where(Evaluation.id == eval_id)
        if workspace_id:
            query = query.join(AgentTask, Evaluation.task_id == AgentTask.id).where(
                AgentTask.workspace_id == workspace_id
            )
        result = await self.db.execute(query)
        evaluation = result.scalar_one_or_none()

        if not evaluation:
            return None

        # Build OverallEvaluation from stored data
        overall = None
        if evaluation.overall_score is not None:
            feedback = {
                "planning": evaluation.planning_feedback or {},
                "tactical": evaluation.tactical_feedback or {},
                "tool_use": evaluation.tool_use_feedback or {},
                "memory": evaluation.memory_feedback or {},
                "replan": evaluation.replan_feedback or {},
                "retrieval": evaluation.retrieval_feedback or {},
            }
            overall = OverallEvaluation(
                planning=feedback["planning"],
                tactical=feedback["tactical"],
                tool_use=feedback["tool_use"],
                memory=feedback["memory"],
                replan=feedback["replan"],
                retrieval=RetrievalScore(**feedback["retrieval"]) if feedback.get("retrieval") else None,
                overall_score=evaluation.overall_score,
                summary=self._build_summary(feedback, evaluation.overall_score),
                recommendations=self._build_recommendations(feedback),
            )

        return EvaluationResponse(
            id=evaluation.id,
            task_id=evaluation.task_id,
            status=evaluation.status.value,
            stream_mode=evaluation.stream_mode,
            created_at=evaluation.created_at,
            completed_at=evaluation.completed_at,
            evaluation=overall,
            prompt_version=evaluation.prompt_version,
            model_name=evaluation.model_name,
            model_provider=evaluation.model_provider,
        )

    # ── Agent in Sandbox ──────────────────────────────────────

    async def run_sandbox_evaluation(
        self,
        request: SandboxEvalRequest,
        workspace_id: Optional[str] = None,
    ) -> SandboxEvalResponse:
        """
        Run a full sandbox-based agent evaluation.

        Steps:
        1. Create a task in the DB
        2. Run AgentRunner in sandbox (LLM reasoning + tool execution)
        3. Save captured trajectory to DB
        4. Run 6 evaluators on the trajectory
        5. Save evaluation results
        6. Return SandboxEvalResponse
        """
        from app.agent_runtime.runner import AgentRunner

        with tracer.start_as_current_span("sandbox_evaluation") as root_span:
            root_span.set_attribute("goal", request.goal[:200])
            root_span.set_attribute("model", request.model or settings.DEFAULT_LLM_MODEL)
            root_span.set_attribute("provider", request.provider or settings.DEFAULT_LLM_PROVIDER)

            # 1. Create task
            with tracer.start_as_current_span("task_creation"):
                from app.services.quota import SANDBOX_EVAL_MODE

                sandbox_context = dict(request.context or {})
                sandbox_context["eval_mode"] = SANDBOX_EVAL_MODE
                task_data = TaskCreate(goal=request.goal, context=sandbox_context)
                task_response = await self.create_task(task_data, workspace_id=workspace_id)
                task_id = task_response.id
                root_span.set_attribute("task_id", task_id)

            # Mark task as running
            task_model = await self._get_task_model(task_id, workspace_id=workspace_id)
            if not task_model:
                raise ValueError(f"Task {task_id} not found")
            task_model.status = TaskStatus.RUNNING
            task_model.started_at = datetime.now(timezone.utc)
            await self.db.flush()

            # 2. Run agent in sandbox
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
            root_span.set_attribute("agent_success", agent_result.success)
            root_span.set_attribute("agent_steps", agent_result.steps_taken)

            # 3. Save trajectory to DB
            with tracer.start_as_current_span("trajectory_persist") as span:
                trajectory_steps = agent_result.trajectory
                span.set_attribute("step_count", len(trajectory_steps))
                if trajectory_steps:
                    await self.add_trajectory(task_id, trajectory_steps, workspace_id=workspace_id)

            # 4. Create evaluation record
            eval_id = str(uuid.uuid4())
            evaluation = Evaluation(
                id=eval_id,
                task_id=task_id,
                status=EvaluationStatus.IN_PROGRESS,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(evaluation)
            await self.db.flush()

            # 5. Run evaluators on the captured trajectory
            overall = None
            if trajectory_steps and agent_result.success:
                try:
                    with tracer.start_as_current_span("evaluation") as eval_span:
                        eval_span.set_attribute("evaluator_count", 6)
                        eval_span.set_attribute("parallel", True)

                        from app.graphs.evaluation_graph import evaluate_parallel
                        from app.models.schemas import TrajectoryStep as TS

                        steps = [
                            TS(
                                step_number=s["step_number"],
                                action_type=s["action_type"],
                                action_detail=s.get("action_detail", {}),
                                observation=s.get("observation"),
                                timestamp=s.get("timestamp", datetime.now(timezone.utc).isoformat()),
                            )
                            for s in trajectory_steps
                        ]

                        parallel_result = await evaluate_parallel(request.goal, steps, request.context)
                        overall_eval = self._build_overall_from_parallel(parallel_result)
                        overall = overall_eval.model_dump()
                        self._merge_judge_raw_into_overall(overall, parallel_result)
                        eval_span.set_attribute("overall_score", overall.get("overall_score", 0))

                        # Record Prometheus metrics
                        EVALUATION_COUNT.labels(status="success", mode="sandbox").inc()
                        score = overall.get("overall_score", 0)
                        EVALUATION_SCORE.observe(score)

                        await self._persist_evaluation_results(evaluation, task_model, overall)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).error("Evaluation failed: %s", e, exc_info=True)
                    evaluation.status = EvaluationStatus.FAILED
                    if task_model:
                        task_model.status = TaskStatus.FAILED
                        task_model.completed_at = datetime.now(timezone.utc)
                    await self.db.flush()
            else:
                # No trajectory or agent failed — mark evaluation as failed
                EVALUATION_COUNT.labels(status="failed", mode="sandbox").inc()
                evaluation.status = EvaluationStatus.FAILED
                if task_model:
                    task_model.status = TaskStatus.FAILED
                    task_model.completed_at = datetime.now(timezone.utc)
                await self.db.flush()

            # Build response
            agent_run_info = AgentRunInfo(
                success=agent_result.success,
                steps_taken=agent_result.steps_taken,
                duration_ms=agent_result.duration_ms,
                final_answer=agent_result.final_answer,
                workspace_state=agent_result.workspace_state,
                workspace_files=agent_result.workspace_files,
                error=agent_result.error,
            )

            return SandboxEvalResponse(
                task_id=task_id,
                evaluation_id=eval_id,
                status=evaluation.status.value,
                agent_run=agent_run_info,
                evaluation=OverallEvaluation(**overall) if overall else None,
                created_at=evaluation.created_at,
                completed_at=evaluation.completed_at,
            )

    async def list_evaluations_with_count(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        workspace_id: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> tuple[List[EvaluationListItem], int]:
        """List evaluations with total count for pagination."""
        from sqlalchemy import func as sql_func

        def _apply_filters(query):
            if workspace_id:
                query = query.where(AgentTask.workspace_id == workspace_id)
            if status:
                try:
                    query = query.where(Evaluation.status == EvaluationStatus(status))
                except ValueError:
                    pass
            if min_score is not None:
                query = query.where(Evaluation.overall_score >= min_score)
            if max_score is not None:
                query = query.where(Evaluation.overall_score <= max_score)
            return query

        count_query = _apply_filters(
            select(sql_func.count()).select_from(Evaluation).join(AgentTask, Evaluation.task_id == AgentTask.id)
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        query = _apply_filters(
            select(Evaluation, AgentTask.goal)
            .join(AgentTask, Evaluation.task_id == AgentTask.id)
            .order_by(Evaluation.created_at.desc())
        )
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            EvaluationListItem(
                id=item.id,
                task_id=item.task_id,
                task_goal=goal,
                status=item.status.value,
                stream_mode=item.stream_mode,
                created_at=item.created_at,
                completed_at=item.completed_at,
                overall_score=item.overall_score,
                planning_score=item.planning_score,
                tactical_score=item.tactical_score,
                tool_use_score=item.tool_use_score,
                memory_score=item.memory_score,
                replan_score=item.replan_score,
                retrieval_score=item.retrieval_score,
                prompt_version=item.prompt_version,
                model_name=item.model_name,
                model_provider=item.model_provider,
            )
            for item, goal in rows
        ]
        return items, total

    async def get_evaluations_dashboard(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate evaluation counters for list page stats."""
        from sqlalchemy import func as sql_func

        count_base = select(sql_func.count()).select_from(Evaluation).join(
            AgentTask, Evaluation.task_id == AgentTask.id
        )
        if workspace_id:
            count_base = count_base.where(AgentTask.workspace_id == workspace_id)
        total = (await self.db.execute(count_base)).scalar_one()

        status_counts: Dict[str, int] = {s.value: 0 for s in EvaluationStatus}
        status_query = (
            select(Evaluation.status, sql_func.count(Evaluation.id))
            .join(AgentTask, Evaluation.task_id == AgentTask.id)
            .group_by(Evaluation.status)
        )
        if workspace_id:
            status_query = status_query.where(AgentTask.workspace_id == workspace_id)
        for status, count in (await self.db.execute(status_query)).all():
            status_counts[status.value if hasattr(status, "value") else str(status)] = count

        avg_query = (
            select(sql_func.avg(Evaluation.overall_score))
            .join(AgentTask, Evaluation.task_id == AgentTask.id)
            .where(Evaluation.overall_score.isnot(None))
        )
        if workspace_id:
            avg_query = avg_query.where(AgentTask.workspace_id == workspace_id)
        average_score = round(float((await self.db.execute(avg_query)).scalar_one() or 0), 1)

        return {"total": total, "status_counts": status_counts, "average_score": average_score}

    async def list_evaluations(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> List[EvaluationListItem]:
        """List evaluations (backward compatibility)."""
        items, _ = await self.list_evaluations_with_count(skip, limit, status)
        return items

    async def get_trajectory(
        self,
        task_id: str,
        workspace_id: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get trajectory steps for a task."""
        task = await self._get_task_model(task_id, workspace_id=workspace_id)
        if not task:
            return None
        return await self._get_trajectory(task_id)

    async def list_tasks_with_count(
        self,
        skip: int = 0,
        limit: int = 100,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[List[TaskResponse], int]:
        """List tasks with total count for pagination."""
        from sqlalchemy import func as sql_func

        def _apply_filters(query):
            if workspace_id:
                query = query.where(AgentTask.workspace_id == workspace_id)
            if status:
                try:
                    query = query.where(AgentTask.status == TaskStatus(status))
                except ValueError:
                    pass
            if search:
                query = query.where(AgentTask.goal.ilike(f"%{search}%"))
            return query

        count_query = _apply_filters(select(sql_func.count()).select_from(AgentTask))
        total = (await self.db.execute(count_query)).scalar_one()

        list_query = _apply_filters(select(AgentTask).order_by(AgentTask.created_at.desc()))
        tasks = (await self.db.execute(list_query.offset(skip).limit(limit))).scalars().all()

        items = [self._task_to_response(task) for task in tasks]
        return items, total

    async def list_tasks(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TaskResponse]:
        """List all tasks."""
        items, _ = await self.list_tasks_with_count(skip=skip, limit=limit)
        return items

    async def delete_task(self, task_id: str, workspace_id: Optional[str] = None) -> bool:
        """Delete a task and all its trajectory and evaluation records (cascade)."""
        task = await self._get_task_model(task_id, workspace_id=workspace_id)
        if not task:
            return False
        await self.db.delete(task)
        await self.db.flush()

        from app.core.cache import cache_delete

        await cache_delete(f"task:{task_id}")
        await cache_delete(f"trajectory:{task_id}")
        await cache_delete(self._dashboard_cache_key(workspace_id))
        await cache_delete(self._dashboard_cache_key(task.workspace_id))

        return True

    async def delete_evaluation(self, eval_id: str, workspace_id: Optional[str] = None) -> bool:
        """Delete a single evaluation record."""
        query = select(Evaluation).where(Evaluation.id == eval_id)
        if workspace_id:
            query = query.join(AgentTask, Evaluation.task_id == AgentTask.id).where(
                AgentTask.workspace_id == workspace_id
            )
        result = await self.db.execute(query)
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            return False
        task_id = evaluation.task_id
        task = await self._get_task_model(task_id)
        await self.db.delete(evaluation)
        await self.db.flush()
        if task:
            await self._invalidate_eval_caches(task_id, task.workspace_id)
        return True

    async def _get_task_model(
        self,
        task_id: str,
        workspace_id: Optional[str] = None,
    ) -> Optional[AgentTask]:
        """Get task ORM model by ID."""
        query = select(AgentTask).where(AgentTask.id == task_id)
        if workspace_id:
            query = query.where(AgentTask.workspace_id == workspace_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_trajectory(self, task_id: str) -> List[Dict[str, Any]]:
        """Get trajectory steps for a task."""
        # Check cache first
        from app.core.cache import cache_get, cache_set

        cache_key = f"trajectory:{task_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        result = await self.db.execute(
            select(AgentTrajectory).where(AgentTrajectory.task_id == task_id).order_by(AgentTrajectory.step_number)
        )
        steps = result.scalars().all()

        trajectory = [
            {
                "step_number": step.step_number,
                "action_type": step.action_type,
                "action_detail": step.action_detail,
                "observation": step.observation,
                "timestamp": step.timestamp.isoformat() if step.timestamp else None,
            }
            for step in steps
        ]

        await cache_set(cache_key, trajectory, ttl=settings.CACHE_TRAJECTORY_TTL)
        return trajectory

    async def finalize_from_parallel(
        self,
        evaluation_id: str,
        task_id: str,
        parallel_result: Dict[str, Any],
    ) -> Optional[EvaluationResponse]:
        """Persist parallel evaluator output into an existing evaluation record."""
        task = await self._get_task_model(task_id)
        if not task:
            return None

        result = await self.db.execute(select(Evaluation).where(Evaluation.id == evaluation_id))
        evaluation = result.scalar_one_or_none()
        if not evaluation or evaluation.task_id != task_id:
            return None
        if evaluation.status != EvaluationStatus.IN_PROGRESS:
            return None

        task.status = TaskStatus.RUNNING
        task.started_at = task.started_at or datetime.now(timezone.utc)
        await self.db.flush()

        overall_eval = self._build_overall_from_parallel(parallel_result)
        overall = overall_eval.model_dump()
        self._merge_judge_raw_into_overall(overall, parallel_result)
        return await self._persist_evaluation_results(evaluation, task, overall)

    async def _persist_evaluation_results(
        self,
        evaluation: Evaluation,
        task: AgentTask,
        overall: Dict[str, Any],
    ) -> EvaluationResponse:
        """Write dimension scores and mark evaluation/task completed."""
        from app.agent_runtime.prompts import PROMPT_VERSION

        # Ensure version fields are set (they may already be from creation)
        if not evaluation.prompt_version:
            evaluation.prompt_version = PROMPT_VERSION
        if not evaluation.model_name:
            evaluation.model_name = settings.DEFAULT_LLM_MODEL
        if not evaluation.model_provider:
            evaluation.model_provider = settings.DEFAULT_LLM_PROVIDER

        evaluation.planning_score = self._dim_score(overall, "planning")
        evaluation.tactical_score = self._dim_score(overall, "tactical")
        evaluation.tool_use_score = self._dim_score(overall, "tool_use")
        evaluation.memory_score = self._dim_score(overall, "memory")
        evaluation.replan_score = self._dim_score(overall, "replan")
        evaluation.retrieval_score = self._dim_score(overall, "retrieval")
        evaluation.overall_score = overall.get("overall_score")

        evaluation.planning_feedback = overall.get("planning")
        evaluation.tactical_feedback = overall.get("tactical")
        evaluation.tool_use_feedback = overall.get("tool_use")
        evaluation.memory_feedback = overall.get("memory")
        evaluation.replan_feedback = overall.get("replan")
        evaluation.retrieval_feedback = overall.get("retrieval")

        evaluation.status = EvaluationStatus.COMPLETED
        evaluation.completed_at = datetime.now(timezone.utc)

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)

        await self.db.flush()

        await self._invalidate_eval_caches(task.id, task.workspace_id)

        return EvaluationResponse(
            id=evaluation.id,
            task_id=evaluation.task_id,
            status=evaluation.status.value,
            stream_mode=evaluation.stream_mode,
            created_at=evaluation.created_at,
            completed_at=evaluation.completed_at,
            evaluation=OverallEvaluation(**overall),
            prompt_version=evaluation.prompt_version,
            model_name=evaluation.model_name,
            model_provider=evaluation.model_provider,
        )

    @staticmethod
    def _merge_judge_raw_into_overall(overall: Dict[str, Any], parallel_result: Dict[str, Any]) -> None:
        """Preserve judge transparency data stripped by Pydantic model_dump()."""
        for dim in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval"):
            judge_raw = (parallel_result.get(dim) or {}).get("_judge_raw")
            if judge_raw:
                if dim not in overall or not isinstance(overall.get(dim), dict):
                    overall[dim] = {}
                overall[dim]["_judge_raw"] = judge_raw

    @staticmethod
    def _dim_score(overall: Dict[str, Any], dimension: str) -> Optional[float]:
        """Extract dimension overall score from normalized evaluation dict."""
        return dimension_score(overall.get(dimension))

    def _build_overall_from_parallel(self, parallel_result: Dict[str, Any]) -> OverallEvaluation:
        """Normalize evaluate_parallel() output into OverallEvaluation."""
        nested = parallel_result.get("overall")
        if isinstance(nested, dict):
            overall_score = float(nested.get("overall_score", 0))
        else:
            overall_score = float(parallel_result.get("overall_score", 0))

        feedback = {
            dim: parallel_result.get(dim) or {}
            for dim in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval")
        }
        retrieval_raw = feedback.get("retrieval") or {}
        if not isinstance(nested, dict) and "overall_score" not in parallel_result:
            overall_score = round(weighted_overall(feedback, settings.EVAL_DIMENSION_WEIGHTS), 1)

        return OverallEvaluation(
            planning=feedback["planning"],
            tactical=feedback["tactical"],
            tool_use=feedback["tool_use"],
            memory=feedback["memory"],
            replan=feedback["replan"],
            retrieval=RetrievalScore(**retrieval_raw) if retrieval_raw else None,
            overall_score=overall_score,
            summary=self._build_summary(feedback, overall_score),
            recommendations=self._build_recommendations(feedback),
        )

    def _build_summary(self, feedback: Dict[str, Any], overall_score: float) -> str:
        """Rebuild a useful summary from persisted dimension feedback."""
        scores = score_values(feedback, settings.EVAL_DIMENSION_WEIGHTS)
        applicable_scores = {name: score for name, score in scores.items() if score is not None}
        if not applicable_scores:
            return f"综合得分：{overall_score:.1f}/100。"
        strongest = max(applicable_scores, key=applicable_scores.get)
        weakest = min(applicable_scores, key=applicable_scores.get)
        return (
            f"综合得分：{overall_score:.1f}/100。"
            f"最强维度：{DIMENSION_LABELS.get(strongest, strongest)}（{applicable_scores[strongest]:.1f}）。"
            f"待改进维度：{DIMENSION_LABELS.get(weakest, weakest)}（{applicable_scores[weakest]:.1f}）。"
        )

    def _build_recommendations(self, feedback: Dict[str, Any]) -> List[str]:
        """Rebuild recommendations from LLM-generated suggestions (with hardcoded fallback)."""
        # Collect all LLM-generated suggestions first
        llm_suggestions = []
        for dim_name in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval"):
            dim_feedback = feedback.get(dim_name) or {}
            dim_suggestions = dim_feedback.get("llm_suggestions") or []
            if isinstance(dim_suggestions, list):
                llm_suggestions.extend(dim_suggestions)

        if llm_suggestions:
            return llm_suggestions[:6]

        # ── Hardcoded fallback ──
        recommendations: List[str] = []
        labels = {
            "planning": "改进规划：执行前补充关键步骤、依赖关系和验收标准。",
            "tactical": "改进战术决策：确保每一步行动都服务于当前目标和上下文。",
            "tool_use": "改进工具使用：加强工具选择、参数校验和结果利用。",
            "memory": "改进记忆保持：记录并复用关键事实，避免上下文不一致。",
            "replan": "改进重规划：在失败、新事实或路径受阻时及时调整计划。",
            "retrieval": "改进检索质量：提升证据相关性、覆盖度和引用准确性。",
        }
        for name, message in labels.items():
            dim_feedback = feedback.get(name) or {}
            if dim_feedback.get("applicable", True) is not False and dim_feedback.get("overall", 0) < 60:
                recommendations.append(message)
        return recommendations or ["继续保持当前表现，并持续监控各维度是否出现波动。"]
