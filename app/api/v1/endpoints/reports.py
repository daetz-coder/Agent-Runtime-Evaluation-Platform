"""
Reports and analytics endpoints.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace import WorkspaceRole
from app.api.workspace_context import WorkspaceContext, get_workspace_context, require_role
from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.db.database import get_db
from app.db.models import AgentTask, Evaluation, EvaluationStatus
from app.models.schemas import EvaluationSummary

router = APIRouter()


def _ws_suffix(ws_filter: Optional[str]) -> str:
    return ws_filter or "all"


async def _get_task_scoped(
    db: AsyncSession,
    task_id: str,
    ws_filter: Optional[str],
) -> Optional[AgentTask]:
    query = select(AgentTask).where(AgentTask.id == task_id)
    if ws_filter:
        query = query.where(AgentTask.workspace_id == ws_filter)
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _evaluations_base_query(ws_filter: Optional[str]):
    query = select(Evaluation).where(Evaluation.status == EvaluationStatus.COMPLETED)
    if ws_filter:
        query = query.join(AgentTask, Evaluation.task_id == AgentTask.id).where(AgentTask.workspace_id == ws_filter)
    return query


@router.get("/summary", response_model=EvaluationSummary)
async def get_evaluation_summary(
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    Get summary of all evaluations.
    """
    require_role(ctx, WorkspaceRole.VIEWER)
    ws_filter = ctx.filter_workspace_id()
    cache_key = f"report:summary:{ws_filter or 'all'}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return EvaluationSummary(**cached)

    stats_query = select(
        func.count(Evaluation.id),
        func.avg(Evaluation.planning_score),
        func.avg(Evaluation.tactical_score),
        func.avg(Evaluation.tool_use_score),
        func.avg(Evaluation.memory_score),
        func.avg(Evaluation.replan_score),
        func.avg(Evaluation.retrieval_score),
        func.avg(Evaluation.overall_score),
    ).where(Evaluation.status == EvaluationStatus.COMPLETED)
    if ws_filter:
        stats_query = stats_query.join(AgentTask, Evaluation.task_id == AgentTask.id).where(
            AgentTask.workspace_id == ws_filter
        )
    stats_result = await db.execute(stats_query)
    total, avg_planning, avg_tactical, avg_tool, avg_memory, avg_replan, avg_retrieval, avg_overall = stats_result.one()
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
                "retrieval": 0,
                "overall": 0,
            },
            score_distribution={
                "planning": [],
                "tactical": [],
                "tool_use": [],
                "memory": [],
                "replan": [],
                "retrieval": [],
                "overall": [],
            },
            top_issues=["No evaluations completed yet"],
            recommendations=["Complete some evaluations to get recommendations"],
        )

    scores_query = select(
        Evaluation.planning_score,
        Evaluation.tactical_score,
        Evaluation.tool_use_score,
        Evaluation.memory_score,
        Evaluation.replan_score,
        Evaluation.retrieval_score,
        Evaluation.overall_score,
    ).where(Evaluation.status == EvaluationStatus.COMPLETED)
    if ws_filter:
        scores_query = scores_query.join(AgentTask, Evaluation.task_id == AgentTask.id).where(
            AgentTask.workspace_id == ws_filter
        )
    scores_result = await db.execute(scores_query)
    score_rows = scores_result.all()

    avg_scores = {
        "planning": float(avg_planning or 0),
        "tactical": float(avg_tactical or 0),
        "tool_use": float(avg_tool or 0),
        "memory": float(avg_memory or 0),
        "replan": float(avg_replan or 0),
        "retrieval": float(avg_retrieval or 0),
        "overall": float(avg_overall or 0),
    }

    distributions = {
        "planning": [r[0] for r in score_rows if r[0] is not None],
        "tactical": [r[1] for r in score_rows if r[1] is not None],
        "tool_use": [r[2] for r in score_rows if r[2] is not None],
        "memory": [r[3] for r in score_rows if r[3] is not None],
        "replan": [r[4] for r in score_rows if r[4] is not None],
        "retrieval": [r[5] for r in score_rows if r[5] is not None],
        "overall": [r[6] for r in score_rows if r[6] is not None],
    }

    top_issues = _identify_top_issues(avg_scores)
    recommendations = _generate_global_recommendations(avg_scores, distributions)

    result = EvaluationSummary(
        total_evaluations=total,
        average_scores=avg_scores,
        score_distribution=distributions,
        top_issues=top_issues,
        recommendations=recommendations,
    )

    await cache_set(cache_key, result.model_dump(), ttl=settings.CACHE_REPORTS_TTL)
    return result


@router.get("/tasks/{task_id}/history")
async def get_task_evaluation_history(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Get evaluation history for a specific task."""
    require_role(ctx, WorkspaceRole.VIEWER)
    ws_filter = ctx.filter_workspace_id()
    task = await _get_task_scoped(db, task_id, ws_filter)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    eval_result = await db.execute(
        select(Evaluation).where(Evaluation.task_id == task_id).order_by(Evaluation.created_at.desc())
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
                "stream_mode": e.stream_mode,
            }
            for e in evaluations
        ],
    }


@router.get("/dimensions/{dimension}")
async def get_dimension_statistics(
    dimension: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Get statistics for a specific evaluation dimension."""
    require_role(ctx, WorkspaceRole.VIEWER)
    ws_filter = ctx.filter_workspace_id()
    valid_dimensions = ["planning", "tactical", "tool_use", "memory", "replan", "retrieval"]

    if dimension not in valid_dimensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dimension. Must be one of: {', '.join(valid_dimensions)}",
        )

    dim_cache_key = f"report:dim:{dimension}:{_ws_suffix(ws_filter)}"
    cached = await cache_get(dim_cache_key)
    if cached is not None:
        return cached

    result = await db.execute(_evaluations_base_query(ws_filter))
    evaluations = result.scalars().all()

    if not evaluations:
        empty_result = {
            "dimension": dimension,
            "count": 0,
            "average": 0,
            "min": 0,
            "max": 0,
            "distribution": [],
        }
        await cache_set(dim_cache_key, empty_result, ttl=settings.CACHE_REPORTS_TTL)
        return empty_result

    # Get scores for this dimension
    score_field = f"{dimension}_score"
    scores = [getattr(e, score_field) for e in evaluations if getattr(e, score_field) is not None]

    if not scores:
        empty_result = {
            "dimension": dimension,
            "count": 0,
            "average": 0,
            "min": 0,
            "max": 0,
            "distribution": [],
        }
        await cache_set(dim_cache_key, empty_result, ttl=settings.CACHE_REPORTS_TTL)
        return empty_result

    dim_result = {
        "dimension": dimension,
        "count": len(scores),
        "average": sum(scores) / len(scores),
        "min": min(scores),
        "max": max(scores),
        "distribution": scores,
    }

    await cache_set(dim_cache_key, dim_result, ttl=settings.CACHE_REPORTS_TTL)
    return dim_result


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
            elif dimension == "retrieval":
                issues.append("Retrieval quality needs improvement: Evidence accuracy or coverage is low")
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


@router.get("/trends")
async def get_trends(
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """获取评估趋势数据（Dashboard 趋势图）。"""
    require_role(ctx, WorkspaceRole.VIEWER)
    ws_filter = ctx.filter_workspace_id()
    cache_key = f"report:trends:{_ws_suffix(ws_filter)}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import func as sa_func

    trends_query = (
        select(
            sa_func.date(Evaluation.completed_at).label("date"),
            sa_func.avg(Evaluation.overall_score).label("avg_overall"),
            sa_func.avg(Evaluation.planning_score).label("avg_planning"),
            sa_func.avg(Evaluation.tactical_score).label("avg_tactical"),
            sa_func.avg(Evaluation.tool_use_score).label("avg_tool_use"),
            sa_func.avg(Evaluation.memory_score).label("avg_memory"),
            sa_func.avg(Evaluation.replan_score).label("avg_replan"),
            sa_func.avg(Evaluation.retrieval_score).label("avg_retrieval"),
            sa_func.count(Evaluation.id).label("count"),
        )
        .where(Evaluation.status == EvaluationStatus.COMPLETED)
        .group_by(sa_func.date(Evaluation.completed_at))
        .order_by(sa_func.date(Evaluation.completed_at).desc())
        .limit(30)
    )
    if ws_filter:
        trends_query = trends_query.join(AgentTask, Evaluation.task_id == AgentTask.id).where(
            AgentTask.workspace_id == ws_filter
        )
    result = await db.execute(trends_query)
    rows = result.all()
    trends_data = [
        {
            "date": str(row.date),
            "avg_overall": round(row.avg_overall or 0, 1),
            "avg_planning": round(row.avg_planning or 0, 1),
            "avg_tactical": round(row.avg_tactical or 0, 1),
            "avg_tool_use": round(row.avg_tool_use or 0, 1),
            "avg_memory": round(row.avg_memory or 0, 1),
            "avg_replan": round(row.avg_replan or 0, 1),
            "avg_retrieval": round(row.avg_retrieval or 0, 1),
            "count": row.count,
        }
        for row in reversed(rows)
    ]

    await cache_set(cache_key, trends_data, ttl=settings.CACHE_TRENDS_TTL)
    return trends_data


@router.get("/export/{task_id}")
async def export_report(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """导出单次评估报告为 Markdown 格式。"""
    require_role(ctx, WorkspaceRole.VIEWER)
    ws_filter = ctx.filter_workspace_id()
    task = await _get_task_scoped(db, task_id, ws_filter)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    from sqlalchemy import select as sa_select

    result = await db.execute(
        sa_select(Evaluation)
        .where(
            Evaluation.task_id == task_id,
            Evaluation.status == EvaluationStatus.COMPLETED,
        )
        .order_by(Evaluation.created_at.desc())
        .limit(1)
    )
    eval_row = result.scalar_one_or_none()
    if not eval_row:
        raise HTTPException(status_code=404, detail="No completed evaluation found")

    md = f"""# Agent Evaluation Report

**Task ID**: {task_id}
**Evaluated**: {eval_row.created_at.isoformat()}

## Overall Score: {eval_row.overall_score or 0:.1f}/100

## Dimension Scores

| Dimension | Score | Weight | Feedback |
|-----------|-------|--------|----------|
| Planning  | {eval_row.planning_score or 0:.1f} | 20% | {eval_row.planning_feedback or "-"} |
| Tactical  | {eval_row.tactical_score or 0:.1f} | 20% | {eval_row.tactical_feedback or "-"} |
| Tool Use  | {eval_row.tool_use_score or 0:.1f} | 15% | {eval_row.tool_use_feedback or "-"} |
| Memory    | {eval_row.memory_score or 0:.1f} | 15% | {eval_row.memory_feedback or "-"} |
| Replan    | {eval_row.replan_score or 0:.1f} | 15% | {eval_row.replan_feedback or "-"} |
| Retrieval | {eval_row.retrieval_score or 0:.1f} | 15% | {eval_row.retrieval_feedback or "-"} |

---
*Generated by Agent Runtime Evaluation Platform v0.1.0*
"""
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=eval-{task_id[:8]}.md"},
    )


@router.get("/compare/{task_id}")
async def compare_evaluations(
    task_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """对比同一任务的多轮评估结果。"""
    require_role(ctx, WorkspaceRole.VIEWER)
    ws_filter = ctx.filter_workspace_id()
    task = await _get_task_scoped(db, task_id, ws_filter)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    compare_cache_key = f"report:compare:{task_id}:{limit}:{_ws_suffix(ws_filter)}"
    cached = await cache_get(compare_cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import select as sa_select

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
            "retrieval": e.retrieval_score,
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

    compare_result = {
        "task_id": task_id,
        "total_evaluations": len(scores_history),
        "trend": trend,
        "score_delta": round(delta, 1),
        "history": scores_history,
    }

    await cache_set(compare_cache_key, compare_result, ttl=settings.CACHE_REPORTS_TTL)
    return compare_result
