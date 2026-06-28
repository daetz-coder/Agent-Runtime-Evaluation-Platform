"""
SandboxTool base class and ToolProxy — the unified gateway for all tool calls.

ToolProxy validates, audits, executes, and records every tool call.
All agent tool invocations go through ToolProxy, never directly to the container.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List

from docker.models.containers import Container

from app.core.config import settings
from app.core.metrics import TOOL_CALL_COUNT, TOOL_CALL_DURATION
from app.core.tracing import get_tracer

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from app.agent_runtime.trajectory_recorder import TrajectoryRecorder

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


# ── Base Tool ─────────────────────────────────────────────────


class SandboxTool(ABC):
    """Base class for all tools that execute inside a sandbox container."""

    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, container: Container, **kwargs: Any) -> str:
        """
        Execute the tool inside the sandbox container.

        Args:
            container: Docker container with writable /workspace
            **kwargs: Tool-specific parameters

        Returns:
            Tool output as string
        """
        ...

    def get_langchain_tool(self) -> "BaseTool":
        """Create a LangChain-compatible tool wrapper."""
        from langchain_core.tools import StructuredTool

        return StructuredTool.from_function(
            coroutine=None,
            func=None,
            name=self.name,
            description=self.description,
        )


# ── Tool Proxy ────────────────────────────────────────────────


class ToolProxy:
    """
    Unified gateway for all tool calls from the agent.

    Every tool invocation goes through:
      1. Validation (is the tool in the allowed list?)
      2. Audit logging (who called what with which params?)
      3. Execution (run in sandbox container with timeout)
      4. Trajectory recording (record tool_call + tool_result)
    """

    def __init__(
        self,
        container: Container,
        allowed_tools: List[str],
        recorder: "TrajectoryRecorder",
    ):
        self.container = container
        self.allowed_tools = allowed_tools
        self.recorder = recorder
        self._registry: Dict[str, SandboxTool] = {}
        self._load_tools()

    def _load_tools(self) -> None:
        """Load all registered sandbox tools into the proxy."""
        from app.agent_runtime.tools.bash_execute import BashExecuteTool
        from app.agent_runtime.tools.file_list import FileListTool
        from app.agent_runtime.tools.file_read import FileReadTool
        from app.agent_runtime.tools.file_write import FileWriteTool
        from app.agent_runtime.tools.python_execute import PythonExecuteTool

        all_tools: List[SandboxTool] = [
            PythonExecuteTool(),
            BashExecuteTool(),
            FileReadTool(),
            FileWriteTool(),
            FileListTool(),
        ]

        for tool in all_tools:
            self._registry[tool.name] = tool

    def get_available_tools(self) -> List[SandboxTool]:
        """Get list of tools that are both registered and allowed."""
        return [self._registry[name] for name in self.allowed_tools if name in self._registry]

    def get_tool_descriptions(self) -> str:
        """Get formatted descriptions of available tools for the agent prompt."""
        tools = self.get_available_tools()
        if not tools:
            return "No tools available."

        lines = []
        for tool in tools:
            params = ", ".join(f"{k}: {v}" for k, v in tool.parameters_schema.items())
            lines.append(f"- **{tool.name}**({params}): {tool.description}")
        return "\n".join(lines)

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Execute a tool call through the proxy.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Parameters for the tool

        Returns:
            Tool output string (or error message)
        """
        with tracer.start_as_current_span("tool_execute") as span:
            span.set_attribute("tool_name", tool_name)

            # 1. Validate
            if tool_name not in self.allowed_tools:
                error = f"Tool '{tool_name}' is not allowed. Available: {self.allowed_tools}"
                span.set_attribute("success", False)
                span.set_attribute("error", "not_allowed")
                self.recorder.record_tool_call(tool_name, tool_input, error, success=False)
                return error

            if tool_name not in self._registry:
                error = f"Tool '{tool_name}' not found in registry."
                span.set_attribute("success", False)
                span.set_attribute("error", "not_found")
                self.recorder.record_tool_call(tool_name, tool_input, error, success=False)
                return error

            tool = self._registry[tool_name]

            # 2. Audit log
            logger.info(
                "Tool call: %s(%s) on container %s",
                tool_name,
                {k: str(v)[:50] for k, v in tool_input.items()},
                self.container.id[:12],
            )

            # 3. Execute with timeout
            timeout = settings.SANDBOX_TOOL_TIMEOUT
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    tool.execute(self.container, **tool_input),
                    timeout=timeout,
                )
                duration_ms = (time.monotonic() - start) * 1000
                success = True
                output = result

            except asyncio.TimeoutError:
                duration_ms = (time.monotonic() - start) * 1000
                success = False
                output = f"Tool '{tool_name}' timed out after {timeout}s"
                logger.warning(output)

            except Exception as e:
                duration_ms = (time.monotonic() - start) * 1000
                success = False
                output = f"Tool '{tool_name}' failed: {e}"
                logger.error("Tool execution error: %s", e, exc_info=True)

            span.set_attribute("success", success)
            span.set_attribute("duration_ms", round(duration_ms, 1))

            # Record Prometheus metrics
            status_label = "success" if success else ("timeout" if "timed out" in output else "failed")
            TOOL_CALL_COUNT.labels(tool=tool_name, status=status_label).inc()
            TOOL_CALL_DURATION.labels(tool=tool_name).observe(duration_ms / 1000)

            # 4. Record trajectory
            self.recorder.record_tool_call(tool_name, tool_input, output, success=success, duration_ms=duration_ms)

            # Truncate output for agent context (keep full output in trajectory)
            max_len = 5000
            if len(output) > max_len:
                return output[:max_len] + f"\n... [truncated, {len(output)} chars total]"
            return output
