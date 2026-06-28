"""
TrajectoryRecorder — capture agent activity as TrajectoryStep records.

Maps agent runtime events (LLM calls, tool calls, thinking, planning, failures)
to the existing 14 ActionType constants used by the evaluation pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.action_types import ActionType

logger = logging.getLogger(__name__)


class TrajectoryRecorder:
    """
    Records agent runtime activity as a list of trajectory steps.

    Each step follows the existing TrajectoryStep schema:
      - step_number: auto-incrementing counter
      - action_type: one of the 14 ActionType values
      - action_detail: dict with structured data
      - observation: optional text observation
      - timestamp: UTC datetime
    """

    def __init__(self) -> None:
        self._steps: List[Dict[str, Any]] = []
        self._step_counter = 0

    # ── Recording Methods ─────────────────────────────────────

    def record_plan(self, plan: Dict[str, Any]) -> None:
        """Record an initial planning step."""
        self._record(
            action_type=ActionType.PLAN,
            action_detail=plan,
        )

    def record_think(self, thought: str, llm_trace: Optional[Dict[str, Any]] = None) -> None:
        """Record a thinking/reasoning step.

        Args:
            thought: The LLM's reasoning text.
            llm_trace: Optional dict with keys prompt, response, model, latency_ms
                       for the Replay Debugger.
        """
        detail = {"thought": thought}
        self._record(
            action_type=ActionType.THINK,
            action_detail=detail,
            llm_trace=llm_trace,
        )

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: str,
        success: bool = True,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Record a tool call and its result."""
        # Record the tool_call action
        self._record(
            action_type=ActionType.TOOL_CALL,
            action_detail={
                "tool_name": tool_name,
                "input": self._truncate(tool_input),
            },
            observation=tool_output[:3000] if tool_output else None,
        )

        # Record the tool_result action
        self._record(
            action_type=ActionType.TOOL_RESULT,
            action_detail={
                "tool_name": tool_name,
                "success": success,
                "duration_ms": duration_ms,
                "output": tool_output[:3000] if tool_output else "",
            },
        )

    def record_replan(self, reason: str, new_plan: Dict[str, Any]) -> None:
        """Record a replanning step."""
        self._record(
            action_type=ActionType.REPLAN,
            action_detail={
                "reason": reason,
                "new_plan": new_plan,
            },
        )

    def record_failure(self, error: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Record a failure/error event."""
        detail: Dict[str, Any] = {"error": error}
        if context:
            detail["context"] = context
        self._record(
            action_type=ActionType.FAILURE,
            action_detail=detail,
        )

    def record_state_change(
        self, description: str, before: Optional[Dict] = None, after: Optional[Dict] = None
    ) -> None:
        """Record a state change event."""
        self._record(
            action_type=ActionType.STATE_CHANGE,
            action_detail={
                "description": description,
                "before": before,
                "after": after,
            },
        )

    def record_node_execute(self, node_name: str, result: Optional[str] = None) -> None:
        """Record a node execution (e.g., LangGraph node)."""
        self._record(
            action_type=ActionType.NODE_EXECUTE,
            action_detail={"node": node_name},
            observation=result,
        )

    # ── Output ────────────────────────────────────────────────

    def get_trajectory(self) -> List[Dict[str, Any]]:
        """Get all recorded trajectory steps as a list of dicts."""
        return list(self._steps)

    def get_step_count(self) -> int:
        """Get the number of recorded steps."""
        return len(self._steps)

    def reset(self) -> None:
        """Clear all recorded steps."""
        self._steps.clear()
        self._step_counter = 0

    # ── Internal ──────────────────────────────────────────────

    def _record(
        self,
        action_type: str,
        action_detail: Dict[str, Any],
        observation: Optional[str] = None,
        llm_trace: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a single trajectory step.

        If llm_trace is provided, it is injected into action_detail as
        ``_llm_trace`` for the Replay Debugger.
        """
        self._step_counter += 1
        if llm_trace:
            # Store LLM trace in action_detail for the replay debugger
            action_detail["_llm_trace"] = {
                "prompt": llm_trace.get("prompt", "")[:10000],
                "response": llm_trace.get("response", "")[:10000],
                "model": llm_trace.get("model", "unknown"),
                "latency_ms": llm_trace.get("latency_ms", 0),
            }
        step = {
            "step_number": self._step_counter,
            "action_type": action_type,
            "action_detail": action_detail,
            "observation": observation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._steps.append(step)
        logger.debug("Trajectory step %d: %s", self._step_counter, action_type)

    @staticmethod
    def _truncate(data: Any, max_str_len: int = 500) -> Any:
        """Truncate long string values in a dict for trajectory storage."""
        if isinstance(data, dict):
            return {k: TrajectoryRecorder._truncate(v, max_str_len) for k, v in data.items()}
        if isinstance(data, str) and len(data) > max_str_len:
            return data[:max_str_len] + "... [truncated]"
        return data
