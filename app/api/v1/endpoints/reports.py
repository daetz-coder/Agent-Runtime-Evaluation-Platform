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
    # Aggregate averages in SQL (avoid loading full evaluation rows)
    stats_result = await db.execute(
        select(
            func.count(Evaluation.id),
            func.avg(Evaluation.planning_score),
            func.avg(Evaluation.tactical_score),
            func.avg(Evaluation.tool_use_score),
            func.avg(Evaluation.memory_score),
            func.avg(Evaluation.replan_score),
            func.avg(Evaluation.overall_score),
        ).where(Evaluation.status == EvaluationStatus.COMPLETED)
    )
    total, avg_planning, avg_tactical, avg_tool, avg_memory, avg_replan, avg_overall = stats_result.one()
    total = total or 0

    if total == 0:
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

    scores_result = await db.execute(
        select(
            Evaluation.planning_score,
            Evaluation.tactical_score,
            Evaluation.tool_use_score,
            Evaluation.memory_score,
            Evaluation.replan_score,
            Evaluation.overall_score,
        ).where(Evaluation.status == EvaluationStatus.COMPLETED)
    )
    score_rows = scores_result.all()

    avg_scores = {
        "planning": float(avg_planning or 0),
        "tactical": float(avg_tactical or 0),
        "tool_use": float(avg_tool or 0),
        "memory": float(avg_memory or 0),
        "replan": float(avg_replan or 0),
        "overall": float(avg_overall or 0),
    }

    distributions = {
        "planning": [r[0] for r in score_rows if r[0] is not None],
        "tactical": [r[1] for r in score_rows if r[1] is not None],
        "tool_use": [r[2] for r in score_rows if r[2] is not None],
        "memory": [r[3] for r in score_rows if r[3] is not None],
        "replan": [r[4] for r in score_rows if r[4] is not None],
        "overall": [r[5] for r in score_rows if r[5] is not None],
    }

    top_issues = _identify_top_issues(avg_scores)
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


@router.get("/export/{task_id}")
async def export_report(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    导出单次评估报告为 Markdown 格式。

    - **task_id**: 任务 UUID
    """
    from app.db.models import Evaluation, EvaluationStatus
    from sqlalchemy import select as sa_select

    result = await db.execute(
        sa_select(Evaluation).where(
            Evaluation.task_id == task_id,
            Evaluation.status == EvaluationStatus.COMPLETED,
        ).order_by(Evaluation.created_at.desc()).limit(1)
    )
    eval_row = result.scalar_one_or_none()
    if not eval_row:
        raise HTTPException(status_code=404, detail="No completed evaluation found")

    md = f"""# Agent Evaluation Report

**Task ID**: {task_id}
**Evaluated**: {eval_row.created_at.isoformat()}

## Overall Score: {eval_row.overall_score:.1f}/100

## Dimension Scores

| Dimension | Score | Weight |
|-----------|-------|--------|
| Planning  | {eval_row.planning_score or 0:.1f} | 25% |
| Tactical  | {eval_row.tactical_score or 0:.1f} | 25% |
| Tool Use  | {eval_row.tool_use_score or 0:.1f} | 20% |
| Memory    | {eval_row.memory_score or 0:.1f} | 15% |
| Replan    | {eval_row.replan_score or 0:.1f} | 15% |

## Summary

{eval_row.summary or 'No summary available.'}

## Recommendations

{chr(10).join('- ' + r for r in (eval_row.recommendations or ['No recommendations.']))}
"""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=md, media_type="text/markdown; charset=utf-8",
                              headers={"Content-Disposition": f"attachment; filename=eval-{task_id[:8]}.md"})


@router.get("/compare/{task_id}")
async def compare_evaluations(
    task_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """
    对比同一任务的多轮评估结果，跟踪 Agent 质量变化趋势。

    - **task_id**: 任务 UUID
    - **limit**: 返回最近 N 轮评估（默认 10）
    """
    from app.db.models import Evaluation, EvaluationStatus
    from sqlalchemy import select as sa_select, func as sa_func

    # 获取所有已完成评估
    result = await db.execute(
        sa_select(Evaluation)
        .where(Evaluation.task_id == task_id, Evaluation.status == EvaluationStatus.COMPLETED)
        .order_by(Evaluation.created_at.asc())
        .limit(limit)
    )
    evals = result.scalars().all()

    if not evals:
        raise HTTPException(status_code=404, detail="No evaluations found for this task")

    scores_history = [
        {
            "evaluation_id": e.id,
            "created_at": e.created_at.isoformat(),
            "overall": e.overall_score,
            "planning": e.planning_score,
            "tactical": e.tactical_score,
            "tool_use": e.tool_use_score,
            "memory": e.memory_score,
            "replan": e.replan_score,
        }
        for e in evals
    ]

    # 趋势计算
    if len(scores_history) >= 2:
        first = scores_history[0]["overall"] or 0
        last = scores_history[-1]["overall"] or 0
        trend = "improving" if last > first else "declining" if last < first else "stable"
        delta = last - first
    else:
        trend = "insufficient_data"
        delta = 0

    return {
        "task_id": task_id,
        "total_evaluations": len(scores_history),
        "trend": trend,
        "score_delta": round(delta, 1),
        "history": scores_history,
    }
