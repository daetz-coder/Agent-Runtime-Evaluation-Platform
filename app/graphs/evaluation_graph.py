"""
LangGraph evaluation workflow graph.

This module defines the evaluation workflow using LangGraph:
1. Validate input
2. Run parallel evaluations (Planning, Tactical, Tool Use, Memory, Replan, Retrieval)
3. Aggregate results
4. Generate final report
"""

from typing import Any, Dict, List, Optional, TypedDict
import logging
import traceback
from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

from app.models.schemas import (
    TrajectoryStep,
    OverallEvaluation,
    PlanningScore,
    TacticalScore,
    ToolUseScore,
    MemoryScore,
    ReplanScore,
    RetrievalScore,
)
logger = logging.getLogger(__name__)

from app.evaluators import (
    PlanningEvaluator,
    TacticalEvaluator,
    ToolUseEvaluator,
    MemoryEvaluator,
    ReplanEvaluator,
    RetrievalEvaluator,
)


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
        steps.append(TrajectoryStep(
            step_number=step.get("step_number", 0),
            action_type=step.get("action_type", "unknown"),
            action_detail=step.get("action_detail", {}),
            observation=step.get("observation"),
            timestamp=step.get("timestamp", datetime.now(timezone.utc)),
        ))
    return steps


def _with_defaults(score: Dict[str, Any], defaults: Dict[str, float]) -> Dict[str, Any]:
    """Fill required score fields when an evaluator returns partial data after an error."""
    result: Dict[str, Any] = {key: float(score.get(key, value)) for key, value in defaults.items()}
    result["overall"] = float(score.get("overall", 0))
    result["feedback"] = str(score.get("feedback", "Not evaluated"))
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


async def evaluate_planning(state: EvaluationState) -> EvaluationState:
    """Evaluate planning quality."""
    try:
        evaluator = PlanningEvaluator()
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


async def evaluate_tactical(state: EvaluationState) -> EvaluationState:
    """Evaluate tactical decisions."""
    try:
        evaluator = TacticalEvaluator()
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


async def evaluate_tool_use(state: EvaluationState) -> EvaluationState:
    """Evaluate tool usage."""
    try:
        evaluator = ToolUseEvaluator()
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


async def evaluate_memory(state: EvaluationState) -> EvaluationState:
    """Evaluate memory quality."""
    try:
        evaluator = MemoryEvaluator()
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


async def evaluate_replan(state: EvaluationState) -> EvaluationState:
    """Evaluate replanning quality."""
    try:
        evaluator = ReplanEvaluator()
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


async def evaluate_retrieval(state: EvaluationState) -> EvaluationState:
    """Evaluate retrieval / RAG quality."""
    try:
        evaluator = RetrievalEvaluator()
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
    # Weight configuration for overall score
    WEIGHTS = {
        "planning": 0.20,
        "tactical": 0.20,
        "tool_use": 0.15,
        "memory": 0.15,
        "replan": 0.15,
        "retrieval": 0.15,
    }

    # Extract scores
    planning = state.get("planning_score", {})
    tactical = state.get("tactical_score", {})
    tool_use = state.get("tool_use_score", {})
    memory = state.get("memory_score", {})
    replan = state.get("replan_score", {})
    retrieval = state.get("retrieval_score", {})

    # Calculate overall score
    scores = {
        "planning": planning.get("overall", 0),
        "tactical": tactical.get("overall", 0),
        "tool_use": tool_use.get("overall", 0),
        "memory": memory.get("overall", 0),
        "replan": replan.get("overall", 0),
        "retrieval": retrieval.get("overall", 0),
    }

    overall_score = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

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
    avg_score = sum(scores.values()) / len(scores)

    if avg_score >= 80:
        quality = "excellent"
    elif avg_score >= 60:
        quality = "good"
    elif avg_score >= 40:
        quality = "moderate"
    else:
        quality = "poor"

    # Find weakest dimension
    weakest = min(scores, key=scores.get)
    strongest = max(scores, key=scores.get)

    return (
        f"Agent performance is {quality} (overall: {avg_score:.1f}/100). "
        f"Strongest dimension: {strongest} ({scores[strongest]:.1f}). "
        f"Weakest dimension: {weakest} ({scores[weakest]:.1f})."
    )


def _generate_recommendations(
    planning: Dict,
    tactical: Dict,
    tool_use: Dict,
    memory: Dict,
    replan: Dict,
    retrieval: Dict,
) -> List[str]:
    """Generate improvement recommendations."""
    recommendations = []

    # Planning recommendations
    if planning.get("overall", 0) < 60:
        recommendations.append("Improve planning: Create more detailed plans with clear milestones before execution.")

    # Tactical recommendations
    if tactical.get("overall", 0) < 60:
        recommendations.append("Improve tactical decisions: Ensure each action is relevant to the current state and goal.")

    # Tool use recommendations
    if tool_use.get("overall", 0) < 60:
        recommendations.append("Improve tool usage: Select tools more carefully and verify parameters before calling.")

    # Memory recommendations
    if memory.get("overall", 0) < 60:
        recommendations.append("Improve memory: Maintain key facts throughout execution and avoid contradictions.")

    # Replan recommendations
    if replan.get("overall", 0) < 60:
        recommendations.append("Improve replanning: Trigger replan earlier when facing repeated failures.")

    # Retrieval recommendations
    if retrieval.get("overall", 0) < 60:
        recommendations.append("Improve retrieval: Ground answers in retrieved evidence and reduce hallucinations.")

    if not recommendations:
        recommendations.append("Continue maintaining high performance across all evaluation dimensions.")

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

    # Add nodes
    workflow.add_node("validate_input", validate_input)
    workflow.add_node("evaluate_planning", evaluate_planning)
    workflow.add_node("evaluate_tactical", evaluate_tactical)
    workflow.add_node("evaluate_tool_use", evaluate_tool_use)
    workflow.add_node("evaluate_memory", evaluate_memory)
    workflow.add_node("evaluate_replan", evaluate_replan)
    workflow.add_node("evaluate_retrieval", evaluate_retrieval)
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
            return dim_name, result
        except Exception as e:
            logger.error("Parallel eval [%s] failed: %s", dim_name, e)
            return dim_name, None

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
    for dim_name, result in results:
        if result is not None:
            scores[dim_name] = result.model_dump() if hasattr(result, 'model_dump') else result
        else:
            scores[dim_name] = {"overall": 0, "feedback": "Evaluation failed"}

    # 计算加权总分
    weights = {"planning": 0.20, "tactical": 0.20, "tool_use": 0.15, "memory": 0.15, "replan": 0.15, "retrieval": 0.15}
    overall = sum(
        weights.get(d, 0) * (s.get("overall", 0) if isinstance(s, dict) else 0)
        for d, s in scores.items()
    )
    scores["overall"] = {"overall_score": round(overall, 1)}

    return scores
