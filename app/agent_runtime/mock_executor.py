"""
Mock Execution Environment — replaces Docker sandbox for local development.

When SANDBOX_MOCK_MODE=True, the AgentRunner and SandboxExecutor return
predefined mock results instead of launching Docker containers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.action_types import ActionType


def get_mock_trajectory(goal: str) -> List[Dict[str, Any]]:
    """Return a fixed mock trajectory for rapid local iteration.

    The mock agent:
    1. Plans a simple approach
    2. Runs a python tool
    3. Thinks about the result
    4. Provides a final answer
    """
    ts = datetime.now(timezone.utc).isoformat()
    return [
        {
            "step_number": 1,
            "action_type": ActionType.PLAN,
            "action_detail": {
                "goal": goal,
                "steps": [
                    {"description": "理解需求"},
                    {"description": "执行关键操作"},
                    {"description": "返回结果"},
                ],
            },
            "observation": None,
            "timestamp": ts,
        },
        {
            "step_number": 2,
            "action_type": ActionType.THINK,
            "action_detail": {
                "thought": "用户的目标是：{goal}。我计划先理解需求，然后执行操作。".format(goal=goal),
                "_llm_trace": {
                    "prompt": "[MOCK] System: You are a helpful agent...\nHuman: {goal}".format(goal=goal),
                    "response": "[MOCK] I'll plan and execute this task.",
                    "model": settings.DEFAULT_LLM_MODEL,
                    "latency_ms": 150,
                },
            },
            "observation": None,
            "timestamp": ts,
        },
        {
            "step_number": 3,
            "action_type": ActionType.TOOL_CALL,
            "action_detail": {
                "tool_name": "python_execute",
                "input": {"code": "print('[MOCK] Executing task')"},
            },
            "observation": "[MOCK] Task executed successfully",
            "timestamp": ts,
        },
        {
            "step_number": 4,
            "action_type": ActionType.THINK,
            "action_detail": {
                "thought": "操作完成，准备输出最终答案。",
                "_llm_trace": {
                    "prompt": "[MOCK] Continue with final answer...",
                    "response": "[MOCK] Final answer: Task completed.",
                    "model": settings.DEFAULT_LLM_MODEL,
                    "latency_ms": 100,
                },
            },
            "observation": None,
            "timestamp": ts,
        },
        {
            "step_number": 5,
            "action_type": ActionType.NODE_EXECUTE,
            "action_detail": {"node": "final_answer"},
            "observation": f"[MOCK] Successfully completed: {goal}",
            "timestamp": ts,
        },
    ]


class MockToolProxy:
    """Mock tool proxy that returns fixed results without Docker.

    Drop-in replacement for ``ToolProxy`` when ``SANDBOX_MOCK_MODE`` is enabled.
    Records tool calls for trajectory generation.
    """

    def __init__(self):
        self._tool_calls: list[dict] = []

    def get_available_tools(self) -> list:
        """Return a minimal tool list."""
        from app.agent_runtime.tools.base import SandboxTool

        # Return empty list — tools are mocked at the trajectory level
        return []

    def get_tool_descriptions(self) -> str:
        return "Mock tool descriptions (no actual tools available in mock mode)"

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool call and return mock result."""
        self._tool_calls.append({"name": tool_name, "input": tool_input})
        return f"[MOCK] {tool_name} executed with {tool_input}"

    def get_tool_calls(self) -> list:
        return list(self._tool_calls)
