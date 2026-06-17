"""
LangGraph evaluation workflow graph.

This module defines the evaluation workflow using LangGraph:
1. Validate input
2. Run parallel evaluations (Planning, Tactical, Tool Use, Memory, Replan)
3. Aggregate results
4. Generate final report
"""

from typing import Any, Dict, List, Optional, TypedDict
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
)
from app.evaluators import (
    PlanningEvaluator,
    TacticalEvaluator,
    ToolUseEvaluator,
    MemoryEvaluator,
    ReplanEvaluator,
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

    # Output
    overall_evaluation: Optional[Dict[str, Any]]
    error: Optional[str]


def _convert_trajectory_steps(raw_steps: List[Dict[str, Any]]) -> List[TrajectoryStep]:
    """Convert raw trajectory data to TrajectoryStep objects."""
    from datetime import datetime

    steps = []
    for step in raw_steps:
        steps.append(TrajectoryStep(
            step_number=step.get("step_number", 0),
            action_type=step.get("action_type", "unknown"),
            action_detail=step.get("action_detail", {}),
            observation=step.get("observation"),
            timestamp=step.get("timestamp", datetime.utcnow()),
        ))
    return steps


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
        return {**state, "replan_score": {"overall": 0, "feedback": f"Error: {str(e)}"}}


async def aggregate_results(state: EvaluationState) -> EvaluationState:
    """Aggregate all evaluation results."""
    # Weight configuration for overall score
    WEIGHTS = {
        "planning": 0.25,
        "tactical": 0.25,
        "tool_use": 0.20,
        "memory": 0.15,
        "replan": 0.15,
    }

    # Extract scores
    planning = state.get("planning_score", {})
    tactical = state.get("tactical_score", {})
    tool_use = state.get("tool_use_score", {})
    memory = state.get("memory_score", {})
    replan = state.get("replan_score", {})

    # Calculate overall score
    scores = {
        "planning": planning.get("overall", 0),
        "tactical": tactical.get("overall", 0),
        "tool_use": tool_use.get("overall", 0),
        "memory": memory.get("overall", 0),
        "replan": replan.get("overall", 0),
    }

    overall_score = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

    # Generate summary
    summary = _generate_summary(scores)

    # Generate recommendations
    recommendations = _generate_recommendations(planning, tactical, tool_use, memory, replan)

    # Create overall evaluation
    overall_evaluation = OverallEvaluation(
        planning=PlanningScore(**planning) if planning else PlanningScore(overall=0, feedback="Not evaluated"),
        tactical=TacticalScore(**tactical) if tactical else TacticalScore(overall=0, feedback="Not evaluated"),
        tool_use=ToolUseScore(**tool_use) if tool_use else ToolUseScore(overall=0, feedback="Not evaluated"),
        memory=MemoryScore(**memory) if memory else MemoryScore(overall=0, feedback="Not evaluated"),
        replan=ReplanScore(**replan) if replan else ReplanScore(overall=0, feedback="Not evaluated"),
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

    if not recommendations:
        recommendations.append("Continue maintaining high performance across all evaluation dimensions.")

    return recommendations


def create_evaluation_graph(llm: Optional[BaseChatModel] = None) -> StateGraph:
    """
    Create the evaluation workflow graph.

    The graph follows this flow:
    1. validate_input -> Check if input is valid
    2. Parallel evaluation of 5 dimensions
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
    workflow.add_node("aggregate_results", aggregate_results)

    # Define edges
    workflow.set_entry_point("validate_input")

    # After validation, run evaluations sequentially to avoid state conflicts
    workflow.add_edge("validate_input", "evaluate_planning")
    workflow.add_edge("evaluate_planning", "evaluate_tactical")
    workflow.add_edge("evaluate_tactical", "evaluate_tool_use")
    workflow.add_edge("evaluate_tool_use", "evaluate_memory")
    workflow.add_edge("evaluate_memory", "evaluate_replan")
    workflow.add_edge("evaluate_replan", "aggregate_results")

    # After aggregation, end
    workflow.add_edge("aggregate_results", END)

    # Compile graph
    return workflow.compile()
