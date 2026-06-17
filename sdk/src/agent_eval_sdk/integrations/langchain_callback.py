"""
LangChain Callback Integration - Auto-capture LLM and tool calls.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from agent_eval_sdk.core.tracker import AgentTracker

logger = logging.getLogger("agent_eval_sdk.langchain")


class AgentEvalCallbackHandler:
    """
    LangChain Callback Handler - Auto-collect trajectory.

    Auto-captures:
    - on_llm_start: LLM call start -> record as "think" step
    - on_llm_end: LLM call end -> update observation
    - on_tool_start: Tool call start -> record as "tool_call" step
    - on_tool_end: Tool call end -> record tool output

    Usage:
        tracker = AgentTracker(config, goal="...")
        tracker.start_task()

        handler = AgentEvalCallbackHandler(tracker)
        llm = ChatOpenAI(callbacks=[handler])
        agent = create_react_agent(llm, tools, callbacks=[handler])

        result = agent.invoke({"input": "..."})
        tracker.complete_task()
    """

    def __init__(
        self,
        tracker: AgentTracker,
        collect_llm_calls: bool = True,
        collect_tool_calls: bool = True,
    ):
        self._tracker = tracker
        self._collect_llm = collect_llm_calls
        self._collect_tool = collect_tool_calls

        # For correlating start/end events
        self._pending_llm: Dict[str, Dict[str, Any]] = {}
        self._pending_tools: Dict[str, Dict[str, Any]] = {}

    # ---- LLM Callbacks ----

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if not self._collect_llm:
            return

        self._pending_llm[str(run_id)] = {
            "model": serialized.get("name", "unknown"),
            "prompts": prompts[:3],
            "start_time": time.time(),
        }

        self._tracker.record_think(
            f"LLM call to {serialized.get('name', 'unknown')}"
        )

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if not self._collect_llm:
            return

        last_msg = ""
        if messages and messages[-1]:
            last_msg = str(messages[-1][-1].content)[:200]

        self._pending_llm[str(run_id)] = {
            "model": serialized.get("name", "unknown"),
            "last_message": last_msg,
            "start_time": time.time(),
        }

        self._tracker.record_think(f"LLM call: {last_msg}")

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if not self._collect_llm:
            return

        rid = str(run_id)
        pending = self._pending_llm.pop(rid, {})

        # Extract LLM output
        output = ""
        if hasattr(response, "generations") and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    output = gen.text[:500]
                    break
                break

        if output:
            self._tracker.record_step(
                action_type="llm_response",
                action_detail={
                    "model": pending.get("model", "unknown"),
                    "output": output,
                },
                observation=output,
            )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        self._pending_llm.pop(rid, None)
        logger.warning("LLM error: %s", error)

    # ---- Tool Callbacks ----

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if not self._collect_tool:
            return

        tool_name = serialized.get("name", "unknown")
        self._pending_tools[str(run_id)] = {
            "name": tool_name,
            "input": input_str,
        }

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if not self._collect_tool:
            return

        rid = str(run_id)
        pending = self._pending_tools.pop(rid, {})

        self._tracker.record_tool_call(
            name=pending.get("name", "unknown"),
            input={"raw": pending.get("input", "")},
            output=output[:1000] if output else None,
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        self._pending_tools.pop(rid, None)
        logger.warning("Tool error: %s", error)

    # ---- Reset ----

    def reset(self) -> None:
        """Reset callback state (does not affect tracker)."""
        self._pending_llm.clear()
        self._pending_tools.clear()
