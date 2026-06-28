"""Monotonicity benchmark — score should decrease as trajectory quality drops."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List

from app.benchmarks.monotonicity_data import (
    ALL_TRAJECTORIES,
    GOAL_BY_LEVEL,
    QUALITY_ORDER,
    REFERENCE_SCORES,
)
from app.graphs.evaluation_graph import evaluate_parallel
from app.models.schemas import TrajectoryStep


def get_monotonicity_metadata() -> Dict[str, Any]:
    """Return static benchmark metadata and reference scores."""
    return {
        "description": "6 synthetic trajectories × 6 evaluators — overall score should decrease monotonically.",
        "quality_order": QUALITY_ORDER,
        "reference_scores": [
            {"level": level, "overall": REFERENCE_SCORES[level], "steps": len(ALL_TRAJECTORIES[level])}
            for level in QUALITY_ORDER
        ],
        "dimensions": ["planning", "tactical", "tool_use", "memory", "replan", "retrieval"],
    }


def _to_steps(raw_steps: List[Dict[str, Any]]) -> List[TrajectoryStep]:
    return [TrajectoryStep(**step) for step in raw_steps]


def check_monotonicity(results: List[Dict[str, Any]]) -> bool:
    """Return True when overall scores are non-increasing along quality order."""
    prev: float | None = None
    for item in results:
        score = float(item.get("overall", 0))
        if prev is not None and score > prev + 0.05:
            return False
        prev = score
    return True


async def run_monotonicity_benchmark_stream() -> AsyncIterator[Dict[str, str]]:
    """SSE event generator for live monotonicity benchmark."""
    results: List[Dict[str, Any]] = []
    total = len(QUALITY_ORDER)

    yield {
        "event": "start",
        "data": json.dumps({"total": total, "quality_order": QUALITY_ORDER}),
    }

    for index, level in enumerate(QUALITY_ORDER, start=1):
        yield {
            "event": "progress",
            "data": json.dumps(
                {
                    "level": level,
                    "index": index,
                    "total": total,
                    "status": "running",
                }
            ),
        }

        try:
            steps = _to_steps(ALL_TRAJECTORIES[level])
            goal = GOAL_BY_LEVEL[level]
            parallel = await evaluate_parallel(goal, steps, context=None)
            overall = float((parallel.get("overall") or {}).get("overall_score", 0))

            dim_scores = {
                dim: (parallel.get(dim) or {}).get("overall", 0)
                for dim in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval")
            }
            item = {
                "level": level,
                "overall": overall,
                "reference": REFERENCE_SCORES[level],
                "steps": len(steps),
                "dimensions": dim_scores,
            }
            results.append(item)

            yield {
                "event": "result",
                "data": json.dumps(
                    {
                        **item,
                        "index": index,
                        "total": total,
                    }
                ),
            }
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"level": level, "message": str(exc)}),
            }

    monotonic = check_monotonicity(results)
    yield {
        "event": "complete",
        "data": json.dumps(
            {
                "results": results,
                "monotonic": monotonic,
                "reference_scores": REFERENCE_SCORES,
            }
        ),
    }
    yield {"event": "done", "data": "{}"}
