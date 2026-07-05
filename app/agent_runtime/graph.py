"""
Agent Graph — LangGraph-based ReAct agent loop.

The agent alternates between thinking (LLM reasoning) and acting (tool execution)
until the goal is achieved or max_steps is reached.

Flow:
  START → think_and_act → (done? → END : → think_and_act)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.graph import END, StateGraph
from pydantic import create_model

from app.agent_runtime.prompts import FINAL_ANSWER_INSTRUCTION, build_system_prompt
from app.agent_runtime.state import AgentState
from app.agent_runtime.tools.base import ToolProxy
from sdk.collector import ActionType
from app.core.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


def create_agent_graph(
    llm: BaseChatModel,
    tool_proxy: ToolProxy,
    recorder: TrajectoryRecorder,
    goal: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: int = 20,
) -> StateGraph:
    """
    Create and compile a LangGraph agent graph.

    Args:
        llm: The language model to use for reasoning
        tool_proxy: Proxy for executing tool calls in the sandbox
        recorder: Trajectory recorder for capturing agent activity
        goal: The agent's goal
        context: Optional additional context
        max_steps: Maximum number of agent steps

    Returns:
        Compiled LangGraph StateGraph
    """
    # Build LangChain tool definitions from the proxy's available tools
    lc_tools = _build_langchain_tools(tool_proxy)

    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(lc_tools) if lc_tools else llm

    # Build system prompt
    system_prompt = build_system_prompt(
        goal=goal,
        tool_descriptions=tool_proxy.get_tool_descriptions(),
        context=json.dumps(context, ensure_ascii=False) if context else "",
    )

    # Define the think_and_act node
    async def think_and_act(state: AgentState) -> Dict[str, Any]:
        """LLM thinks and decides next action; tools are executed if called."""
        current_step = state["current_step"]
        max_s = state["max_steps"]
        messages = list(state["messages"])

        # Check if we've hit max steps
        if current_step >= max_s:
            recorder.record_failure(
                error_type="MaxStepsReached",
                error_message=f"Agent reached maximum steps ({max_s})",
                context=f"Goal: {goal}",
                recoverable=False,
                node_name="think_and_act",
            )
            return {
                "done": True,
                "final_answer": f"Task incomplete: reached maximum {max_s} steps.",
                "error": "max_steps_reached",
                "current_step": current_step,
            }

        span_name = f"step_{current_step}_think_and_act"
        with tracer.start_as_current_span(span_name) as step_span:
            step_span.set_attribute("step_number", current_step)

            # Add system message on first step
            if current_step == 0:
                messages.insert(0, SystemMessage(content=system_prompt))

            # Prompt the LLM to consider final answer (only near step limit to avoid context bloat)
            if current_step > 0 and max_s > 3 and current_step >= max_s - 3:
                messages.append(HumanMessage(content=FINAL_ANSWER_INSTRUCTION))

            # Call LLM
            with tracer.start_as_current_span("llm_call") as llm_span:
                llm_span.set_attribute("provider", getattr(llm, "_llm_type", "unknown"))
                llm_span.set_attribute("model", getattr(llm, "model_name", "unknown"))
                import time as _time

                llm_start = _time.monotonic()
                try:
                    response = await llm_with_tools.ainvoke(messages)
                    llm_latency_ms = (_time.monotonic() - llm_start) * 1000
                    llm_span.set_attribute("response_length", len(response.content or ""))
                except Exception as e:
                    llm_latency_ms = (_time.monotonic() - llm_start) * 1000
                    llm_span.set_attribute("error", str(e))
                    logger.error("LLM call failed at step %d: %s", current_step, e)
                    recorder.record_failure(
                        error_type=type(e).__name__,
                        error_message=f"LLM call failed: {e}",
                        context=f"Step {current_step}, goal: {goal}",
                        recoverable=True,
                        node_name="think_and_act",
                    )
                    return {
                        "done": True,
                        "final_answer": f"Agent failed: LLM error - {e}",
                        "error": str(e),
                        "current_step": current_step + 1,
                    }

            # Build LLM trace for Replay Debugger
            llm_model = getattr(llm, "model_name", "unknown")
            # Serialize the prompt messages to a readable string
            prompt_text = _serialize_messages(messages)
            llm_trace = {
                "prompt": prompt_text,
                "response": response.content or "",
                "model": llm_model,
                "latency_ms": llm_latency_ms,
            }

            # Record the LLM's thinking with LLM trace
            ai_content = response.content or ""
            if ai_content:
                recorder.record_think(ai_content[:2000], llm_trace=llm_trace)

            # Check for tool calls
            tool_calls = getattr(response, "tool_calls", None)
            if tool_calls:
                step_span.set_attribute("has_tool_call", True)
                step_span.set_attribute("tool_count", len(tool_calls))

                # 记录 TOOL_DECISION（LLM 决定调用哪些工具）
                for tc in tool_calls:
                    recorder.record(
                        ActionType.TOOL_DECISION,
                        {
                            "node_name": "think_and_act",
                            "tool_name": tc.get("name", ""),
                            "input": tc.get("args", {}),
                            "step": current_step,
                        },
                    )

                # Execute each tool call through the proxy
                new_messages = [response]
                for tc in tool_calls:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("args", {})
                    tool_id = tc.get("id", "")

                    step_span.set_attribute("tool_name", tool_name)

                    # Record planning if the first tool call
                    if current_step == 0:
                        recorder.record_plan(
                            {
                                "goal": goal,
                                "first_action": tool_name,
                                "args": {k: str(v)[:100] for k, v in tool_args.items()},
                            }
                        )

                    # Execute through proxy (validates, audits, records)
                    result = await tool_proxy.execute(tool_name, tool_args)

                    # 记录 PLAN_UPDATE（每步执行后更新进度）
                    recorder.record(
                        ActionType.PLAN_UPDATE,
                        {
                            "milestone_status": {"current_step": current_step + 1, "max_steps": max_s},
                            "next_action": f"continue after {tool_name}",
                            "reason": f"Tool {tool_name} executed",
                        },
                    )

                    # Add tool result to messages
                    new_messages.append(ToolMessage(content=result, tool_call_id=tool_id))

                return {
                    "messages": new_messages,
                    "current_step": current_step + 1,
                }

            # No tool calls — check if this is a final answer
            step_span.set_attribute("has_tool_call", False)
            if ai_content:
                is_final = _is_final_answer(ai_content)
                if is_final or current_step >= max_s - 1:
                    final = _extract_final_answer(ai_content)
                    recorder.record_node_execute("final_answer", final)
                    step_span.set_attribute("is_final_answer", True)
                    return {
                        "messages": [response],
                        "done": True,
                        "final_answer": final,
                        "current_step": current_step + 1,
                    }
                else:
                    # LLM responded without tools — treat as thinking, prompt again
                    recorder.record_think("Agent responded without tool call or final answer")
                    # 记录 REPLAN（Agent 重新考虑策略）
                    if current_step > 0:
                        recorder.record(
                            ActionType.REPLAN,
                            {
                                "reason": "Agent responded without tool call, reconsidering approach",
                                "trigger": "no_tool_call",
                            },
                        )
                    return {
                        "messages": [response],
                        "current_step": current_step + 1,
                    }

        # Empty response — force completion
        return {
            "done": True,
            "final_answer": "Agent produced no output.",
            "error": "empty_response",
            "current_step": current_step + 1,
        }

    # Build the graph
    graph = StateGraph(AgentState)
    graph.add_node("think_and_act", think_and_act)
    graph.set_entry_point("think_and_act")
    graph.add_conditional_edges(
        "think_and_act",
        lambda state: END if state.get("done", False) else "think_and_act",
    )

    return graph.compile()


# ── Helpers ───────────────────────────────────────────────────


def _build_langchain_tools(proxy: ToolProxy) -> List[BaseTool]:
    """Convert SandboxTool instances to LangChain StructuredTool definitions."""
    tools = []
    for sandbox_tool in proxy.get_available_tools():
        # Build a Pydantic model from the tool's parameters
        fields = {}
        for param_name, param_desc in sandbox_tool.parameters_schema.items():
            # Parse "type — description" format
            parts = param_desc.split("—", 1) if "—" in param_desc else param_desc.split("-", 1)
            param_type_str = parts[0].strip().lower() if parts else "str"

            # Map type strings to Python types
            type_map = {
                "str": str,
                "string": str,
                "int": int,
                "integer": int,
                "float": float,
                "bool": bool,
                "boolean": bool,
                "dict": dict,
                "list": list,
            }
            param_type = type_map.get(param_type_str, str)
            fields[param_name] = (param_type, ...)

        input_model = create_model(f"{sandbox_tool.name}_Input", **fields)

        tool = StructuredTool(
            name=sandbox_tool.name,
            description=sandbox_tool.description,
            args_schema=input_model,
            func=lambda **kwargs: "Use coroutine instead",
            coroutine=None,  # Will be handled by our graph directly
        )
        tools.append(tool)
    return tools


def _is_final_answer(content: str) -> bool:
    """Check if the LLM response indicates task completion."""
    lower = content.lower().strip()
    indicators = [
        "final answer:",
        "task complete",
        "task completed",
        "i have completed",
        "i've completed",
        "done.",
        "finished.",
        "the goal has been achieved",
        "here is the result",
        "here are the results",
    ]
    return any(ind in lower for ind in indicators)


def _extract_final_answer(content: str) -> str:
    """Extract the final answer from the LLM response."""
    # Try to extract after "FINAL ANSWER:" prefix
    lower = content.lower()
    for prefix in ["final answer:", "final answer\n"]:
        idx = lower.find(prefix)
        if idx != -1:
            return content[idx + len(prefix) :].strip()
    return content.strip()


def _serialize_messages(messages: List[Any]) -> str:
    """Serialize LangChain message list to a readable prompt string.

    Used by the Replay Debugger to capture what the LLM saw.
    Truncated to 10_000 chars to avoid oversized payloads.
    """
    parts = []
    for msg in messages:
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", "") or ""
        # Truncate each message's content
        if isinstance(content, str) and len(content) > 2000:
            content = content[:2000] + "... [truncated]"
        parts.append(f"[{role}]\n{content}")
    result = "\n\n---\n\n".join(parts)
    return result[:10000]
