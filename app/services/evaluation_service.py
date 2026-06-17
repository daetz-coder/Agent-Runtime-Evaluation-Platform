"""
Evaluation service for orchestrating agent evaluations.
"""

import uuid
from datetime import datetime
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
            created_at=datetime.utcnow(),
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
            trajectory = AgentTrajectory(
                task_id=task_id,
                step_number=step_data.get("step_number", 0),
                action_type=step_data.get("action_type", "unknown"),
                action_detail=step_data.get("action_detail", {}),
                observation=step_data.get("observation"),
                timestamp=step_data.get("timestamp", datetime.utcnow()),
            )
            self.db.add(trajectory)

        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()

        await self.db.flush()
        return True

    async def run_evaluation(
        self,
        task_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[EvaluationResponse]:
        """Run evaluation for a task."""
        # Get task
        task = await self._get_task_model(task_id)
        if not task:
            return None

        # Get trajectory
        trajectory = await self._get_trajectory(task_id)

        # Create evaluation record
        eval_id = str(uuid.uuid4())
        evaluation = Evaluation(
            id=eval_id,
            task_id=task_id,
            status=EvaluationStatus.IN_PROGRESS,
            created_at=datetime.utcnow(),
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
            evaluation.completed_at = datetime.utcnow()

            # Update task status
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()

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
            overall = OverallEvaluation(
                planning=evaluation.planning_feedback or {},
                tactical=evaluation.tactical_feedback or {},
                tool_use=evaluation.tool_use_feedback or {},
                memory=evaluation.memory_feedback or {},
                replan=evaluation.replan_feedback or {},
                overall_score=evaluation.overall_score,
                summary="",  # Could regenerate if needed
                recommendations=[],
            )

        return EvaluationResponse(
            id=evaluation.id,
            task_id=evaluation.task_id,
            status=evaluation.status.value,
            created_at=evaluation.created_at,
            completed_at=evaluation.completed_at,
            evaluation=overall,
        )

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
