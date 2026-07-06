"""
Reports and analytics endpoints.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.db.database import get_db
from app.db.models import AgentTask, Evaluation, EvaluationStatus
from app.models.schemas import EvaluationSummary

router = APIRouter()


async def _get_task_by_id(
    db: AsyncSession,
    task_id: str,
) -> Optional[AgentTask]:
    query = select(AgentTask).where(AgentTask.id == task_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _evaluations_base_query():
    query = select(Evaluation).where(Evaluation.status == EvaluationStatus.COMPLETED)
    return query


@router.get("/summary", response_model=EvaluationSummary)
async def get_evaluation_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary of all evaluations.
    """
    cache_key = "report:summary:all"
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
            top_issues=["No completed evaluations"],
            recommendations=["Complete an evaluation to get improvement recommendations."],
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
):
    """Get evaluation history for a specific task."""
    task = await _get_task_by_id(db, task_id)
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
):
    """Get statistics for a specific evaluation dimension."""
    valid_dimensions = ["planning", "tactical", "tool_use", "memory", "replan", "retrieval"]

    if dimension not in valid_dimensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dimension. Must be one of: {', '.join(valid_dimensions)}",
        )

    dim_cache_key = f"report:dim:{dimension}:all"
    cached = await cache_get(dim_cache_key)
    if cached is not None:
        return cached

    result = await db.execute(_evaluations_base_query())
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
                issues.append("规划质量需要改进：计划覆盖度、步骤粒度或完整性不足。")
            elif dimension == "tactical":
                issues.append("战术决策存在不足：部分行动与当前目标的相关性或效率不够。")
            elif dimension == "tool_use":
                issues.append("工具使用效率偏低：工具选择、参数准确性或结果利用不足。")
            elif dimension == "memory":
                issues.append("记忆保持较弱：关键事实记录或跨步骤复用不足。")
            elif dimension == "retrieval":
                issues.append("检索质量需要改进：证据准确性、相关性或覆盖度偏低。")
            elif dimension == "replan":
                issues.append("重规划能力需要改进：遇到失败或新信息时调整不够及时。")

    if not issues:
        issues.append("未发现显著问题")

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
        recommendations.append("整体表现优秀，建议重点保持稳定性和一致性。")
    elif overall >= 60:
        recommendations.append("整体表现良好，可优先优化相对薄弱的评估维度。")
    else:
        recommendations.append("整体表现需要明显改进，建议从 Agent 基础流程设计入手。")

    # Specific recommendations based on scores
    if avg_scores.get("planning", 0) < 60:
        recommendations.append("建立结构化规划：将目标拆成清晰里程碑，并标注依赖关系。")

    if avg_scores.get("tactical", 0) < 60:
        recommendations.append("改进行动选择：执行前校验每个动作是否匹配当前状态和目标。")

    if avg_scores.get("tool_use", 0) < 60:
        recommendations.append("增强工具选择：制定工具选择规则，并在调用前校验参数。")

    if avg_scores.get("memory", 0) < 60:
        recommendations.append("加强记忆管理：显式追踪关键事实，并在后续步骤中检索复用。")

    if avg_scores.get("replan", 0) < 60:
        recommendations.append("增加重规划触发机制：监控失败模式，并主动调整执行计划。")

    return recommendations


@router.get("/trends")
async def get_trends(
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation trend data (Dashboard trend chart)."""
    cache_key = "report:trends:all"
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
):
    """Export a single evaluation report as Markdown."""
    task = await _get_task_by_id(db, task_id)
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
):
    """Compare multiple evaluation results for the same task."""
    task = await _get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    compare_cache_key = f"report:compare:{task_id}:{limit}"
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

    # Trend calculation
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
