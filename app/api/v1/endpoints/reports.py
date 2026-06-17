"""
Reports and analytics endpoints.
"""

from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.db.models import AgentTask, Evaluation, TaskStatus, EvaluationStatus
from app.models.schemas import EvaluationSummary

router = APIRouter()


@router.get("/summary", response_model=EvaluationSummary)
async def get_evaluation_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary of all evaluations.

    Returns aggregated statistics including:
    - Total number of evaluations
    - Average scores across all dimensions
    - Score distributions
    - Top issues identified
    - Recommendations
    """
    # Get all completed evaluations
    result = await db.execute(
        select(Evaluation).where(Evaluation.status == EvaluationStatus.COMPLETED)
    )
    evaluations = result.scalars().all()

    if not evaluations:
        return EvaluationSummary(
            total_evaluations=0,
            average_scores={
                "planning": 0,
                "tactical": 0,
                "tool_use": 0,
                "memory": 0,
                "replan": 0,
                "overall": 0,
            },
            score_distribution={
                "planning": [],
                "tactical": [],
                "tool_use": [],
                "memory": [],
                "replan": [],
                "overall": [],
            },
            top_issues=["No evaluations completed yet"],
            recommendations=["Complete some evaluations to get recommendations"],
        )

    # Calculate averages
    total = len(evaluations)
    avg_scores = {
        "planning": sum(e.planning_score or 0 for e in evaluations) / total,
        "tactical": sum(e.tactical_score or 0 for e in evaluations) / total,
        "tool_use": sum(e.tool_use_score or 0 for e in evaluations) / total,
        "memory": sum(e.memory_score or 0 for e in evaluations) / total,
        "replan": sum(e.replan_score or 0 for e in evaluations) / total,
        "overall": sum(e.overall_score or 0 for e in evaluations) / total,
    }

    # Calculate distributions
    distributions = {
        "planning": [e.planning_score for e in evaluations if e.planning_score is not None],
        "tactical": [e.tactical_score for e in evaluations if e.tactical_score is not None],
        "tool_use": [e.tool_use_score for e in evaluations if e.tool_use_score is not None],
        "memory": [e.memory_score for e in evaluations if e.memory_score is not None],
        "replan": [e.replan_score for e in evaluations if e.replan_score is not None],
        "overall": [e.overall_score for e in evaluations if e.overall_score is not None],
    }

    # Identify top issues
    top_issues = _identify_top_issues(avg_scores)

    # Generate recommendations
    recommendations = _generate_global_recommendations(avg_scores, distributions)

    return EvaluationSummary(
        total_evaluations=total,
        average_scores=avg_scores,
        score_distribution=distributions,
        top_issues=top_issues,
        recommendations=recommendations,
    )


@router.get("/tasks/{task_id}/history")
async def get_task_evaluation_history(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get evaluation history for a specific task.

    - **task_id**: UUID of the task
    """
    # Verify task exists
    task_result = await db.execute(
        select(AgentTask).where(AgentTask.id == task_id)
    )
    task = task_result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get all evaluations for this task
    eval_result = await db.execute(
        select(Evaluation)
        .where(Evaluation.task_id == task_id)
        .order_by(Evaluation.created_at.desc())
    )
    evaluations = eval_result.scalars().all()

    return {
        "task_id": task_id,
        "task_goal": task.goal,
        "evaluations": [
            {
                "id": e.id,
                "status": e.status.value,
                "created_at": e.created_at,
                "completed_at": e.completed_at,
                "overall_score": e.overall_score,
            }
            for e in evaluations
        ],
    }


@router.get("/dimensions/{dimension}")
async def get_dimension_statistics(
    dimension: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics for a specific evaluation dimension.

    - **dimension**: One of: planning, tactical, tool_use, memory, replan
    """
    valid_dimensions = ["planning", "tactical", "tool_use", "memory", "replan"]

    if dimension not in valid_dimensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dimension. Must be one of: {', '.join(valid_dimensions)}"
        )

    # Get all completed evaluations
    result = await db.execute(
        select(Evaluation).where(Evaluation.status == EvaluationStatus.COMPLETED)
    )
    evaluations = result.scalars().all()

    if not evaluations:
        return {
            "dimension": dimension,
            "count": 0,
            "average": 0,
            "min": 0,
            "max": 0,
            "distribution": [],
        }

    # Get scores for this dimension
    score_field = f"{dimension}_score"
    scores = [getattr(e, score_field) for e in evaluations if getattr(e, score_field) is not None]

    if not scores:
        return {
            "dimension": dimension,
            "count": 0,
            "average": 0,
            "min": 0,
            "max": 0,
            "distribution": [],
        }

    return {
        "dimension": dimension,
        "count": len(scores),
        "average": sum(scores) / len(scores),
        "min": min(scores),
        "max": max(scores),
        "distribution": scores,
    }


def _identify_top_issues(avg_scores: Dict[str, float]) -> List[str]:
    """Identify top issues based on average scores."""
    issues = []

    threshold = 60  # Below this is considered an issue

    for dimension, score in avg_scores.items():
        if dimension == "overall":
            continue
        if score < threshold:
            if dimension == "planning":
                issues.append("Planning quality needs improvement: Plans lack coverage or proper granularity")
            elif dimension == "tactical":
                issues.append("Tactical decisions are suboptimal: Actions not always relevant or efficient")
            elif dimension == "tool_use":
                issues.append("Tool usage is inefficient: Poor tool selection or parameter accuracy")
            elif dimension == "memory":
                issues.append("Memory retention is weak: Key facts are being forgotten")
            elif dimension == "replan":
                issues.append("Replanning is inadequate: Not triggering replan when needed")

    if not issues:
        issues.append("No significant issues identified")

    return issues


def _generate_global_recommendations(
    avg_scores: Dict[str, float],
    distributions: Dict[str, List[float]],
) -> List[str]:
    """Generate global recommendations."""
    recommendations = []

    # Overall quality assessment
    overall = avg_scores.get("overall", 0)

    if overall >= 80:
        recommendations.append("Excellent performance! Focus on maintaining consistency.")
    elif overall >= 60:
        recommendations.append("Good performance with room for improvement in weaker dimensions.")
    else:
        recommendations.append("Performance needs significant improvement. Focus on fundamental agent design.")

    # Specific recommendations based on scores
    if avg_scores.get("planning", 0) < 60:
        recommendations.append("Implement structured planning: Break goals into clear milestones with dependencies.")

    if avg_scores.get("tactical", 0) < 60:
        recommendations.append("Improve action selection: Validate each action against current state before execution.")

    if avg_scores.get("tool_use", 0) < 60:
        recommendations.append("Enhance tool selection: Create tool selection guidelines and validate parameters.")

    if avg_scores.get("memory", 0) < 60:
        recommendations.append("Strengthen memory management: Implement explicit fact tracking and retrieval.")

    if avg_scores.get("replan", 0) < 60:
        recommendations.append("Add replanning triggers: Monitor failure patterns and trigger replan proactively.")

    return recommendations
