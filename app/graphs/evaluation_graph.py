"""
LangGraph evaluation workflow graph.

This module defines the evaluation workflow using LangGraph:
1. Validate input
2. Run parallel evaluations (Planning, Tactical, Tool Use, Memory, Replan, Retrieval)
3. Aggregate results
4. Generate final report
"""

import functools
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph

from app.models.schemas import (
    MemoryScore,
    OverallEvaluation,
    PlanningScore,
    ReplanScore,
    RetrievalScore,
    TacticalScore,
    ToolUseScore,
    TrajectoryStep,
)

logger = logging.getLogger(__name__)

DIMENSION_LABELS = {
    "planning": "规划质量",
    "tactical": "战术决策",
    "tool_use": "工具使用",
    "memory": "记忆保持",
    "replan": "重规划",
    "retrieval": "检索质量",
}

from app.evaluators import (
    MemoryEvaluator,
    PlanningEvaluator,
    ReplanEvaluator,
    RetrievalEvaluator,
    TacticalEvaluator,
    ToolUseEvaluator,
)
from app.evaluators.scoring import score_values, weighted_overall


class EvaluationState(TypedDict):
    """State for the evaluation graph."""

    # Input
    task_id: str
    goal: str
    trajectory: List[Dict[str, Any]]
    context: Optional[Dict[str, Any]]

    # Intermediate results
    planning_score: Optional[Dict[str, Any]]
    tactical_score: Optional[Dict[str, Any]]
    tool_use_score: Optional[Dict[str, Any]]
    memory_score: Optional[Dict[str, Any]]
    replan_score: Optional[Dict[str, Any]]
    retrieval_score: Optional[Dict[str, Any]]

    # Output
    overall_evaluation: Optional[Dict[str, Any]]
    error: Optional[str]


def _convert_trajectory_steps(raw_steps: List[Dict[str, Any]]) -> List[TrajectoryStep]:
    """Convert raw trajectory data to TrajectoryStep objects."""
    from datetime import datetime, timezone

    steps = []
    for step in raw_steps:
        steps.append(
            TrajectoryStep(
                step_number=step.get("step_number", 0),
                action_type=step.get("action_type", "unknown"),
                action_detail=step.get("action_detail", {}),
                observation=step.get("observation"),
                timestamp=step.get("timestamp", datetime.now(timezone.utc)),
            )
        )
    return steps


def _with_defaults(score: Dict[str, Any], defaults: Dict[str, float]) -> Dict[str, Any]:
    """Fill required score fields when an evaluator returns partial data after an error."""
    result: Dict[str, Any] = {key: float(score.get(key, value)) for key, value in defaults.items()}
    result["overall"] = float(score.get("overall", 0))
    result["feedback"] = str(score.get("feedback", "Not evaluated"))
    if "applicable" in score:
        result["applicable"] = bool(score.get("applicable"))
    if score.get("not_applicable_reason"):
        result["not_applicable_reason"] = str(score.get("not_applicable_reason"))
    return result


async def validate_input(state: EvaluationState) -> EvaluationState:
    """Validate input state."""
    if not state.get("goal"):
        return {**state, "error": "Goal is required"}
    if not state.get("trajectory"):
        return {**state, "error": "Trajectory is required"}
    if not state.get("task_id"):
        return {**state, "error": "Task ID is required"}
    return state


async def evaluate_planning(state: EvaluationState, llm=None) -> EvaluationState:
    """Evaluate planning quality."""
    try:
        evaluator = PlanningEvaluator(llm=llm)
        trajectory = _convert_trajectory_steps(state["trajectory"])

        score = await evaluator.evaluate(
            goal=state["goal"],
            trajectory=trajectory,
            context=state.get("context"),
        )

        return {**state, "planning_score": score.model_dump()}
    except Exception as e:
        logger.error("Evaluation node failed: %s", e, exc_info=True)
        return {**state, "planning_score": {"overall": 0, "feedback": f"Error: {str(e)}"}}


async def evaluate_tactical(state: EvaluationState, llm=None) -> EvaluationState:
    """Evaluate tactical decisions."""
    try:
        evaluator = TacticalEvaluator(llm=llm)
        trajectory = _convert_trajectory_steps(state["trajectory"])

        score = await evaluator.evaluate(
            goal=state["goal"],
            trajectory=trajectory,
            context=state.get("context"),
        )

        return {**state, "tactical_score": score.model_dump()}
    except Exception as e:
        logger.error("Evaluation node failed: %s", e, exc_info=True)
        return {**state, "tactical_score": {"overall": 0, "feedback": f"Error: {str(e)}"}}


async def evaluate_tool_use(state: EvaluationState, llm=None) -> EvaluationState:
    """Evaluate tool usage."""
    try:
        evaluator = ToolUseEvaluator(llm=llm)
        trajectory = _convert_trajectory_steps(state["trajectory"])

        score = await evaluator.evaluate(
            goal=state["goal"],
            trajectory=trajectory,
            context=state.get("context"),
        )

        return {**state, "tool_use_score": score.model_dump()}
    except Exception as e:
        logger.error("Evaluation node failed: %s", e, exc_info=True)
        return {**state, "tool_use_score": {"overall": 0, "feedback": f"Error: {str(e)}"}}


async def evaluate_memory(state: EvaluationState, llm=None) -> EvaluationState:
    """Evaluate memory quality."""
    try:
        evaluator = MemoryEvaluator(llm=llm)
        trajectory = _convert_trajectory_steps(state["trajectory"])

        score = await evaluator.evaluate(
            goal=state["goal"],
            trajectory=trajectory,
            context=state.get("context"),
        )

        return {**state, "memory_score": score.model_dump()}
    except Exception as e:
        logger.error("Evaluation node failed: %s", e, exc_info=True)
        return {**state, "memory_score": {"overall": 0, "feedback": f"Error: {str(e)}"}}


async def evaluate_replan(state: EvaluationState, llm=None) -> EvaluationState:
    """Evaluate replanning quality."""
    try:
        evaluator = ReplanEvaluator(llm=llm)
        trajectory = _convert_trajectory_steps(state["trajectory"])

        score = await evaluator.evaluate(
            goal=state["goal"],
            trajectory=trajectory,
            context=state.get("context"),
        )

        return {**state, "replan_score": score.model_dump()}
    except Exception as e:
        logger.error("Evaluation node failed: %s", e, exc_info=True)
        return {**state, "replan_score": {"overall": 0, "feedback": f"Error: {str(e)}"}}


async def evaluate_retrieval(state: EvaluationState, llm=None) -> EvaluationState:
    """Evaluate retrieval / RAG quality."""
    try:
        evaluator = RetrievalEvaluator(llm=llm)
        trajectory = _convert_trajectory_steps(state["trajectory"])

        score = await evaluator.evaluate(
            goal=state["goal"],
            trajectory=trajectory,
            context=state.get("context"),
        )

        return {**state, "retrieval_score": score.model_dump()}
    except Exception as e:
        logger.error("Evaluation node failed: %s", e, exc_info=True)
        return {**state, "retrieval_score": {"overall": 0, "feedback": f"Error: {str(e)}"}}


async def aggregate_results(state: EvaluationState) -> EvaluationState:
    """Aggregate all evaluation results."""
    from app.core.config import settings as _cfg

    weights = _cfg.EVAL_DIMENSION_WEIGHTS

    # Extract scores
    planning = state.get("planning_score", {})
    tactical = state.get("tactical_score", {})
    tool_use = state.get("tool_use_score", {})
    memory = state.get("memory_score", {})
    replan = state.get("replan_score", {})
    retrieval = state.get("retrieval_score", {})

    dimension_results = {
        "planning": planning,
        "tactical": tactical,
        "tool_use": tool_use,
        "memory": memory,
        "replan": replan,
        "retrieval": retrieval,
    }
    scores = score_values(dimension_results, weights)
    overall_score = weighted_overall(dimension_results, weights)

    # Generate summary
    summary = _generate_summary(scores)

    # Generate recommendations
    recommendations = _generate_recommendations(planning, tactical, tool_use, memory, replan, retrieval)

    planning = _with_defaults(
        planning,
        {"coverage": 0, "ordering": 0, "granularity": 0, "completeness": 0},
    )
    tactical = _with_defaults(
        tactical,
        {"relevance": 0, "efficiency": 0, "correctness": 0},
    )
    tool_use = _with_defaults(
        tool_use,
        {"selection_quality": 0, "parameter_accuracy": 0, "result_utilization": 0},
    )
    memory = _with_defaults(
        memory,
        {"retention": 0, "relevance": 0, "consistency": 0},
    )
    replan = _with_defaults(
        replan,
        {"trigger_appropriateness": 0, "adaptation_quality": 0, "learning_from_failure": 0},
    )
    retrieval = _with_defaults(
        retrieval,
        {"relevance": 0, "evidence_accuracy": 0, "coverage": 0},
    )

    # Create overall evaluation
    overall_evaluation = OverallEvaluation(
        planning=PlanningScore(**planning),
        tactical=TacticalScore(**tactical),
        tool_use=ToolUseScore(**tool_use),
        memory=MemoryScore(**memory),
        replan=ReplanScore(**replan),
        retrieval=RetrievalScore(**retrieval),
        overall_score=overall_score,
        summary=summary,
        recommendations=recommendations,
    )

    return {**state, "overall_evaluation": overall_evaluation.model_dump()}


def _generate_summary(scores: Dict[str, float]) -> str:
    """Generate a summary based on scores."""
    applicable_scores = {name: score for name, score in scores.items() if score is not None}
    if not applicable_scores:
        return "没有可用于计算综合评分的评估维度。"

    avg_score = sum(applicable_scores.values()) / len(applicable_scores)

    if avg_score >= 80:
        quality = "优秀"
    elif avg_score >= 60:
        quality = "良好"
    elif avg_score >= 40:
        quality = "一般"
    else:
        quality = "较弱"

    # Find weakest dimension
    weakest = min(applicable_scores, key=applicable_scores.get)
    strongest = max(applicable_scores, key=applicable_scores.get)

    return (
        f"Agent 综合表现{quality}（综合得分：{avg_score:.1f}/100）。"
        f"最强维度：{DIMENSION_LABELS.get(strongest, strongest)}（{applicable_scores[strongest]:.1f}）。"
        f"待改进维度：{DIMENSION_LABELS.get(weakest, weakest)}（{applicable_scores[weakest]:.1f}）。"
    )


def _generate_recommendations(
    planning: Dict,
    tactical: Dict,
    tool_use: Dict,
    memory: Dict,
    replan: Dict,
    retrieval: Dict,
) -> List[str]:
    """Generate improvement recommendations from LLM suggestions (with hardcoded fallback)."""
    recommendations = []

    # Collect all LLM-generated suggestions first
    llm_suggestions = []
    for dim in (planning, tactical, tool_use, memory, replan, retrieval):
        dim_suggestions = dim.get("llm_suggestions") or []
        if isinstance(dim_suggestions, list):
            llm_suggestions.extend(dim_suggestions)

    if llm_suggestions:
        return llm_suggestions[:6]  # cap at 6 recommendations

    # ── Hardcoded fallback (used when LLM didn't return suggestions) ──

    # Planning recommendations
    if planning.get("overall", 0) < 60:
        recommendations.append("改进规划：执行前拆解更清晰的里程碑、依赖关系和验收标准。")

    # Tactical recommendations
    if tactical.get("overall", 0) < 60:
        recommendations.append("改进战术决策：每一步行动前校验其与当前状态和任务目标的相关性。")

    # Tool use recommendations
    if tool_use.get("applicable", True) is not False and tool_use.get("overall", 0) < 60:
        recommendations.append("改进工具使用：调用前明确工具选择依据，并校验参数、路径和输入格式。")

    # Memory recommendations
    if memory.get("overall", 0) < 60:
        recommendations.append("改进记忆管理：显式记录关键事实，并在后续步骤中保持一致引用。")

    # Replan recommendations
    if replan.get("applicable", True) is not False and replan.get("overall", 0) < 60:
        recommendations.append("改进重规划：遇到连续失败、路径受阻或新信息出现时及时调整计划。")

    # Retrieval recommendations
    if retrieval.get("overall", 0) < 60:
        recommendations.append("改进检索质量：提高证据相关性与引用准确性，确保最终回答基于检索内容。")

    if not recommendations:
        recommendations.append("继续保持当前表现，并持续监控各维度是否出现波动。")

    return recommendations


def create_evaluation_graph(llm: Optional[BaseChatModel] = None) -> StateGraph:
    """
    Create the evaluation workflow graph.

    The graph follows this flow:
    1. validate_input -> Check if input is valid
    2. Parallel evaluation of 6 dimensions
    3. aggregate_results -> Combine all scores
    4. END

    Args:
        llm: Optional LLM override for evaluators

    Returns:
        Compiled StateGraph
    """
    # Create graph
    workflow = StateGraph(EvaluationState)

    # Add nodes — bind llm to each evaluator via partial
    workflow.add_node("validate_input", validate_input)
    workflow.add_node("evaluate_planning", functools.partial(evaluate_planning, llm=llm))
    workflow.add_node("evaluate_tactical", functools.partial(evaluate_tactical, llm=llm))
    workflow.add_node("evaluate_tool_use", functools.partial(evaluate_tool_use, llm=llm))
    workflow.add_node("evaluate_memory", functools.partial(evaluate_memory, llm=llm))
    workflow.add_node("evaluate_replan", functools.partial(evaluate_replan, llm=llm))
    workflow.add_node("evaluate_retrieval", functools.partial(evaluate_retrieval, llm=llm))
    workflow.add_node("aggregate_results", aggregate_results)

    # Define edges
    workflow.set_entry_point("validate_input")

    # After validation, run evaluations sequentially to avoid state conflicts
    workflow.add_edge("validate_input", "evaluate_planning")
    workflow.add_edge("evaluate_planning", "evaluate_tactical")
    workflow.add_edge("evaluate_tactical", "evaluate_tool_use")
    workflow.add_edge("evaluate_tool_use", "evaluate_memory")
    workflow.add_edge("evaluate_memory", "evaluate_replan")
    workflow.add_edge("evaluate_replan", "evaluate_retrieval")
    workflow.add_edge("evaluate_retrieval", "aggregate_results")

    # After aggregation, end
    workflow.add_edge("aggregate_results", END)

    # Compile graph
    return workflow.compile()


async def evaluate_parallel(
    goal: str,
    trajectory: List[TrajectoryStep],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """并行评估 — 6 个评估器同时运行，使用 asyncio.gather。

    比串行快约 5 倍（71s → ~15s）。
    不依赖 LangGraph StateGraph，直接并发调用。
    """
    import asyncio

    async def _eval(dim_name: str, EvalClass):
        try:
            ev = EvalClass()
            result = await ev.evaluate(goal=goal, trajectory=trajectory, context=context)
            # Capture judge raw data for transparency
            judge_raw = ev.get_judge_raw_history()
            result_dict = result.model_dump() if hasattr(result, "model_dump") else result
            if judge_raw:
                result_dict["_judge_raw"] = judge_raw
            return dim_name, result_dict, judge_raw
        except Exception as e:
            logger.error("Parallel eval [%s] failed: %s", dim_name, e)
            return dim_name, None, None

    tasks = [
        _eval("planning", PlanningEvaluator),
        _eval("tactical", TacticalEvaluator),
        _eval("tool_use", ToolUseEvaluator),
        _eval("memory", MemoryEvaluator),
        _eval("replan", ReplanEvaluator),
        _eval("retrieval", RetrievalEvaluator),
    ]
    results = await asyncio.gather(*tasks)

    # 聚合
    scores = {}
    all_judge_raw: Dict[str, list] = {}
    for dim_name, result, judge_raw in results:
        if result is not None:
            scores[dim_name] = result
            if judge_raw:
                all_judge_raw[dim_name] = judge_raw
        else:
            scores[dim_name] = {"overall": 0, "feedback": "Evaluation failed"}
    scores["_judge_raw_all"] = all_judge_raw

    # 计算加权总分（使用配置中共享的权重）
    from app.core.config import settings as _cfg

    weights = _cfg.EVAL_DIMENSION_WEIGHTS
    overall = weighted_overall(scores, weights)
    scores["overall"] = {"overall_score": round(overall, 1)}

    return scores


EVALUATOR_CLASSES = {
    "planning": PlanningEvaluator,
    "tactical": TacticalEvaluator,
    "tool_use": ToolUseEvaluator,
    "memory": MemoryEvaluator,
    "replan": ReplanEvaluator,
    "retrieval": RetrievalEvaluator,
}


async def evaluate_partial(
    goal: str,
    trajectory: List[TrajectoryStep],
    context: Optional[Dict[str, Any]],
    dimensions: List[str],
) -> Dict[str, Any]:
    """Run only the requested evaluators in parallel."""
    import asyncio

    dims = [d for d in dimensions if d in EVALUATOR_CLASSES]
    if not dims:
        return {}

    async def _eval(dim_name: str):
        try:
            ev = EVALUATOR_CLASSES[dim_name]()
            result = await ev.evaluate(goal=goal, trajectory=trajectory, context=context)
            judge_raw = ev.get_judge_raw_history()
            result_dict = result.model_dump() if hasattr(result, "model_dump") else result
            if judge_raw:
                result_dict["_judge_raw"] = judge_raw
            return dim_name, result_dict
        except Exception as e:
            logger.error("Partial eval [%s] failed: %s", dim_name, e)
            return dim_name, {"overall": 0, "feedback": str(e)}

    results = await asyncio.gather(*[_eval(dim) for dim in dims])
    return {dim_name: result_dict for dim_name, result_dict in results}
