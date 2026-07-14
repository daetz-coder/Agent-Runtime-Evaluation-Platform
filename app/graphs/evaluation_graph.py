"""
Evaluation orchestration — parallel 6-dimension judges via asyncio.gather.

Production path is evaluate_parallel / evaluate_partial (not a LangGraph StateGraph).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.evaluators import (
    MemoryEvaluator,
    PlanningEvaluator,
    ReplanEvaluator,
    RetrievalEvaluator,
    TacticalEvaluator,
    ToolUseEvaluator,
)
from app.evaluators.scoring import weighted_overall
from app.models.schemas import TrajectoryStep

logger = logging.getLogger(__name__)

EVALUATOR_CLASSES = {
    "planning": PlanningEvaluator,
    "tactical": TacticalEvaluator,
    "tool_use": ToolUseEvaluator,
    "memory": MemoryEvaluator,
    "replan": ReplanEvaluator,
    "retrieval": RetrievalEvaluator,
}


async def evaluate_parallel(
    goal: str,
    trajectory: List[TrajectoryStep],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run all six evaluators concurrently and return weighted aggregate scores."""
    import asyncio

    async def _eval(dim_name: str, EvalClass):
        try:
            ev = EvalClass()
            result = await ev.evaluate(goal=goal, trajectory=trajectory, context=context)
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

    scores: Dict[str, Any] = {}
    all_judge_raw: Dict[str, list] = {}
    for dim_name, result, judge_raw in results:
        if result is not None:
            scores[dim_name] = result
            if judge_raw:
                all_judge_raw[dim_name] = judge_raw
        else:
            scores[dim_name] = {"overall": 0, "feedback": "Evaluation failed"}
    scores["_judge_raw_all"] = all_judge_raw

    from app.core.config import settings as _cfg

    weights = _cfg.EVAL_DIMENSION_WEIGHTS
    overall = weighted_overall(scores, weights)
    scores["overall"] = {"overall_score": round(overall, 1)}

    return scores


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
