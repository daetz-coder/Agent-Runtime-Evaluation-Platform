"""
Evaluation service for orchestrating agent evaluations.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import AgentTask, AgentTrajectory, Evaluation, TaskStatus, EvaluationStatus
from app.models.schemas import (
    TaskCreate,
    TaskResponse,
    TrajectoryStep,
    EvaluationRequest,
    EvaluationResponse,
    EvaluationListItem,
    OverallEvaluation,
)
from app.graphs.evaluation_graph import create_evaluation_graph, EvaluationState


class EvaluationService:
    """Service for managing agent evaluations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(self, task_data: TaskCreate) -> TaskResponse:
        """Create a new agent task."""
        task_id = str(uuid.uuid4())

        task = AgentTask(
            id=task_id,
            goal=task_data.goal,
            context=task_data.context,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(task)
        await self.db.flush()

        return TaskResponse(
            id=task.id,
            goal=task.goal,
            context=task.context,
            status=task.status.value,
            created_at=task.created_at,
        )

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Get task by ID."""
        result = await self.db.execute(
            select(AgentTask).where(AgentTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            return None

        return TaskResponse(
            id=task.id,
            goal=task.goal,
            context=task.context,
            status=task.status.value,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )

    async def add_trajectory(
        self,
        task_id: str,
        steps: List[Dict[str, Any]],
    ) -> bool:
        """Add trajectory steps to a task."""
        # Verify task exists
        task = await self._get_task_model(task_id)
        if not task:
            return False

        # Add trajectory steps
        for step_data in steps:
            observation = step_data.get("observation")
            if observation is not None and not isinstance(observation, str):
                observation = json.dumps(observation, ensure_ascii=False, default=str)

            trajectory = AgentTrajectory(
                task_id=task_id,
                step_number=step_data.get("step_number", 0),
                action_type=step_data.get("action_type", "unknown"),
                action_detail=step_data.get("action_detail", {}),
                observation=observation,
                timestamp=step_data.get("timestamp", datetime.now(timezone.utc)),
            )
            self.db.add(trajectory)

        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        await self.db.flush()
        return True

    async def create_evaluation(self, task_id: str) -> Optional[EvaluationResponse]:
        """Create an evaluation record (IN_PROGRESS) without running the graph.

        Used by the async endpoint to return immediately, then the background
        task calls run_evaluation() to do the actual work.
        """
        task = await self._get_task_model(task_id)
        if not task:
            return None

        eval_id = str(uuid.uuid4())
        evaluation = Evaluation(
            id=eval_id,
            task_id=task_id,
            status=EvaluationStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(evaluation)
        await self.db.flush()

        return EvaluationResponse(
            id=evaluation.id,
            task_id=evaluation.task_id,
            status=evaluation.status.value,
            created_at=evaluation.created_at,
            completed_at=None,
            evaluation=None,
        )

    async def run_evaluation(
        self,
        task_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[EvaluationResponse]:
        """Run evaluation for a task.

        If an IN_PROGRESS evaluation already exists for this task, it will be
        updated. Otherwise a new one is created.
        """
        # Get task
        task = await self._get_task_model(task_id)
        if not task:
            return None

        # Get trajectory
        trajectory = await self._get_trajectory(task_id)

        # Find existing IN_PROGRESS evaluation or create a new one
        result = await self.db.execute(
            select(Evaluation).where(
                Evaluation.task_id == task_id,
                Evaluation.status == EvaluationStatus.IN_PROGRESS,
            )
        )
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            eval_id = str(uuid.uuid4())
            evaluation = Evaluation(
                id=eval_id,
                task_id=task_id,
                status=EvaluationStatus.IN_PROGRESS,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(evaluation)
            await self.db.flush()

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
                "overall_evaluation": None,
                "error": None,
            }

            # Run evaluation graph
            graph = create_evaluation_graph()
            result = await graph.ainvoke(state)

            # Check for errors
            if result.get("error"):
                evaluation.status = EvaluationStatus.FAILED
                await self.db.flush()
                return None

            # Update evaluation with results
            overall = result.get("overall_evaluation", {})
            evaluation.planning_score = overall.get("planning", {}).get("overall")
            evaluation.tactical_score = overall.get("tactical", {}).get("overall")
            evaluation.tool_use_score = overall.get("tool_use", {}).get("overall")
            evaluation.memory_score = overall.get("memory", {}).get("overall")
            evaluation.replan_score = overall.get("replan", {}).get("overall")
            evaluation.overall_score = overall.get("overall_score")

            # Store detailed feedback
            evaluation.planning_feedback = overall.get("planning")
            evaluation.tactical_feedback = overall.get("tactical")
            evaluation.tool_use_feedback = overall.get("tool_use")
            evaluation.memory_feedback = overall.get("memory")
            evaluation.replan_feedback = overall.get("replan")

            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.completed_at = datetime.now(timezone.utc)

            # Update task status
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)

            await self.db.flush()

            return EvaluationResponse(
                id=evaluation.id,
                task_id=evaluation.task_id,
                status=evaluation.status.value,
                created_at=evaluation.created_at,
                completed_at=evaluation.completed_at,
                evaluation=OverallEvaluation(**overall) if overall else None,
            )

        except Exception as e:
            import traceback
            print(f"❌ Evaluation failed: {str(e)}")
            print(traceback.format_exc())
            evaluation.status = EvaluationStatus.FAILED
            await self.db.flush()
            raise e

    async def get_evaluation(self, eval_id: str) -> Optional[EvaluationResponse]:
        """Get evaluation by ID."""
        result = await self.db.execute(
            select(Evaluation).where(Evaluation.id == eval_id)
        )
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
            }
            overall = OverallEvaluation(
                planning=feedback["planning"],
                tactical=feedback["tactical"],
                tool_use=feedback["tool_use"],
                memory=feedback["memory"],
                replan=feedback["replan"],
                overall_score=evaluation.overall_score,
                summary=self._build_summary(feedback, evaluation.overall_score),
                recommendations=self._build_recommendations(feedback),
            )

        return EvaluationResponse(
            id=evaluation.id,
            task_id=evaluation.task_id,
            status=evaluation.status.value,
            created_at=evaluation.created_at,
            completed_at=evaluation.completed_at,
            evaluation=overall,
        )

    async def list_evaluations(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> List[EvaluationListItem]:
        """List evaluations with lightweight score fields."""
        query = select(Evaluation).order_by(Evaluation.created_at.desc())
        if status:
            try:
                query = query.where(Evaluation.status == EvaluationStatus(status))
            except ValueError:
                pass
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        evaluations = result.scalars().all()

        return [
            EvaluationListItem(
                id=item.id,
                task_id=item.task_id,
                status=item.status.value,
                created_at=item.created_at,
                completed_at=item.completed_at,
                overall_score=item.overall_score,
                planning_score=item.planning_score,
                tactical_score=item.tactical_score,
                tool_use_score=item.tool_use_score,
                memory_score=item.memory_score,
                replan_score=item.replan_score,
            )
            for item in evaluations
        ]

    async def get_trajectory(self, task_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get trajectory steps for a task."""
        task = await self._get_task_model(task_id)
        if not task:
            return None
        return await self._get_trajectory(task_id)

    async def list_tasks(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TaskResponse]:
        """List all tasks."""
        result = await self.db.execute(
            select(AgentTask)
            .offset(skip)
            .limit(limit)
            .order_by(AgentTask.created_at.desc())
        )
        tasks = result.scalars().all()

        return [
            TaskResponse(
                id=task.id,
                goal=task.goal,
                context=task.context,
                status=task.status.value,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
            )
            for task in tasks
        ]

    async def _get_task_model(self, task_id: str) -> Optional[AgentTask]:
        """Get task ORM model by ID."""
        result = await self.db.execute(
            select(AgentTask).where(AgentTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def _get_trajectory(self, task_id: str) -> List[Dict[str, Any]]:
        """Get trajectory steps for a task."""
        result = await self.db.execute(
            select(AgentTrajectory)
            .where(AgentTrajectory.task_id == task_id)
            .order_by(AgentTrajectory.step_number)
        )
        steps = result.scalars().all()

        return [
            {
                "step_number": step.step_number,
                "action_type": step.action_type,
                "action_detail": step.action_detail,
                "observation": step.observation,
                "timestamp": step.timestamp.isoformat() if step.timestamp else None,
            }
            for step in steps
        ]

    def _build_summary(self, feedback: Dict[str, Any], overall_score: float) -> str:
        """Rebuild a useful summary from persisted dimension feedback."""
        scores = {
            name: (value or {}).get("overall", 0)
            for name, value in feedback.items()
        }
        if not scores:
            return f"Overall score: {overall_score:.1f}/100."
        strongest = max(scores, key=scores.get)
        weakest = min(scores, key=scores.get)
        return (
            f"Overall score: {overall_score:.1f}/100. "
            f"Strongest dimension: {strongest} ({scores[strongest]:.1f}). "
            f"Weakest dimension: {weakest} ({scores[weakest]:.1f})."
        )

    def _build_recommendations(self, feedback: Dict[str, Any]) -> List[str]:
        """Rebuild recommendations from persisted dimension scores."""
        recommendations: List[str] = []
        labels = {
            "planning": "Improve planning before execution.",
            "tactical": "Improve next-action selection and tactical decisions.",
            "tool_use": "Improve tool selection, parameters, and result use.",
            "memory": "Improve retention and consistency across context.",
            "replan": "Improve replanning when failures or new facts appear.",
        }
        for name, message in labels.items():
            if (feedback.get(name) or {}).get("overall", 0) < 60:
                recommendations.append(message)
        return recommendations or ["Continue maintaining high performance across all evaluation dimensions."]
