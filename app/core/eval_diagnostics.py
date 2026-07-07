"""
Evaluation pipeline diagnostics — structured logs to trace empty-score / fast-fail issues.

Look for log prefix ``[EvalDiag]`` in server output.

Typical failure signatures:
  - ``EMPTY trajectory`` — evaluators short-circuit without LLM (~1s, all zeros)
  - ``flush FAILED`` — collector could not POST trajectory before auto_run
  - ``SSE replay`` — stream returned cached scores, LLM not re-run
  - ``llm_calls=0`` on a dimension — short-circuit or parse failure, not a real Judge score
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Mapping, Sequence

logger = logging.getLogger("app.eval.diagnostics")

_PLAN_STRUCTURE_KEYS = ("steps", "milestones", "plan", "content")


def _action_type(step: Any) -> str:
    if isinstance(step, Mapping):
        return str(step.get("action_type") or "unknown")
    return str(getattr(step, "action_type", None) or "unknown")


def _action_detail(step: Any) -> dict:
    if isinstance(step, Mapping):
        detail = step.get("action_detail") or {}
    else:
        detail = getattr(step, "action_detail", None) or {}
    return detail if isinstance(detail, dict) else {}


def _is_real_plan_step(step: Any) -> bool:
    if _action_type(step) != "plan":
        return False
    detail = _action_detail(step)
    has_structure = any(detail.get(k) for k in _PLAN_STRUCTURE_KEYS)
    if not has_structure and set(detail.keys()).issubset({"goal", "context"}):
        return False
    return has_structure


def summarize_trajectory(steps: Sequence[Any]) -> dict[str, Any]:
    """Build a compact trajectory summary for logs."""
    types = Counter(_action_type(s) for s in steps)
    real_plans = sum(1 for s in steps if _is_real_plan_step(s))
    ghost_plans = types.get("plan", 0) - real_plans
    return {
        "step_count": len(steps),
        "action_types": dict(types),
        "real_plan_steps": real_plans,
        "ghost_plan_steps": max(ghost_plans, 0),
        "tool_call_steps": types.get("tool_call", 0),
        "retrieval_steps": types.get("retrieval", 0),
        "node_execute_steps": types.get("node_execute", 0),
    }


def log_trajectory(task_id: str, steps: Sequence[Any], *, source: str) -> None:
    """Log trajectory shape before evaluation runs."""
    summary = summarize_trajectory(steps)
    if summary["step_count"] == 0:
        logger.warning(
            "[EvalDiag] %s task_id=%s EMPTY trajectory — evaluators will return 0 without calling Judge LLM",
            source,
            task_id,
        )
        return

    logger.info(
        "[EvalDiag] %s task_id=%s steps=%d types=%s real_plans=%d ghost_plans=%d "
        "tool_calls=%d retrieval=%d node_execute=%d",
        source,
        task_id,
        summary["step_count"],
        summary["action_types"],
        summary["real_plan_steps"],
        summary["ghost_plan_steps"],
        summary["tool_call_steps"],
        summary["retrieval_steps"],
        summary["node_execute_steps"],
    )

    if summary["real_plan_steps"] == 0 and summary["ghost_plan_steps"] > 0:
        logger.info(
            "[EvalDiag] %s task_id=%s planning likely 0: only ghost plan (goal/context, no steps/milestones)",
            source,
            task_id,
        )


def log_evaluator_result(
    task_id: str,
    dimension: str,
    dim_data: Mapping[str, Any] | None,
    *,
    elapsed_ms: float,
    judge_calls: int,
) -> None:
    """Log one dimension result and whether Judge LLM was actually invoked."""
    data = dim_data or {}
    score = data.get("overall")
    applicable = data.get("applicable", True)
    feedback = str(data.get("feedback") or "")[:240]
    llm_used = judge_calls > 0

    if not llm_used and applicable is not False:
        logger.warning(
            "[EvalDiag] evaluator task_id=%s dim=%s score=%s applicable=%s llm_calls=0 "
            "elapsed_ms=%.0f — short-circuit or LLM/parse failure (not a real Judge score). feedback=%r",
            task_id,
            dimension,
            score,
            applicable,
            elapsed_ms,
            feedback,
        )
    else:
        logger.info(
            "[EvalDiag] evaluator task_id=%s dim=%s score=%s applicable=%s llm_calls=%d elapsed_ms=%.0f feedback=%r",
            task_id,
            dimension,
            score,
            applicable,
            judge_calls,
            elapsed_ms,
            feedback,
        )


def log_stream_replay(evaluation_id: str, task_id: str, overall: float | None) -> None:
    logger.warning(
        "[EvalDiag] SSE replay (Judge LLM NOT re-run) evaluation_id=%s task_id=%s cached_overall=%s",
        evaluation_id,
        task_id,
        overall,
    )


def log_stream_start(task_id: str, evaluation_id: str | None, step_count: int) -> None:
    logger.info(
        "[EvalDiag] SSE stream start task_id=%s evaluation_id=%s trajectory_steps=%d",
        task_id,
        evaluation_id or "-",
        step_count,
    )


def log_collector_finish(
    task_id: str,
    *,
    steps_buffered: int,
    flush_succeeded: bool,
    unflushed: int,
    auto_run: bool,
    eval_triggered: bool,
) -> None:
    if flush_succeeded:
        logger.info(
            "[EvalDiag] collector.finish task_id=%s flushed=%d flush_ok=true auto_run=%s eval_triggered=%s",
            task_id,
            steps_buffered,
            auto_run,
            eval_triggered,
        )
    else:
        logger.warning(
            "[EvalDiag] collector.finish task_id=%s flush FAILED — unflushed=%d (of %d buffered) "
            "auto_run=%s eval_triggered=%s — evaluation may run on EMPTY trajectory",
            task_id,
            unflushed,
            steps_buffered,
            auto_run,
            eval_triggered,
        )

    if auto_run and eval_triggered and not flush_succeeded:
        logger.error(
            "[EvalDiag] collector.finish task_id=%s BUG PATH: auto_run triggered AFTER flush failure — "
            "expect all-zero evaluation scores",
            task_id,
        )


def log_trajectory_persisted(task_id: str, added: int, total: int) -> None:
    logger.info(
        "[EvalDiag] trajectory persisted task_id=%s added=%d total_in_db=%d",
        task_id,
        added,
        total,
    )
