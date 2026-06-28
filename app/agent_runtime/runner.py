"""
AgentRunner — top-level orchestrator for Agent in Sandbox.

Coordinates:
  1. Sandbox session acquisition (SessionPool)
  2. Workspace setup (WorkspaceManager)
  3. Agent loop execution (LangGraph graph)
  4. Trajectory capture (TrajectoryRecorder)
  5. Workspace state capture
  6. Session cleanup

The runner is the single entry point for running an agent evaluation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from app.agent_runtime.graph import create_agent_graph
from app.agent_runtime.llm_factory import create_llm
from app.agent_runtime.sandbox.session_pool import (
    SandboxSession,
    get_session_pool,
    is_session_pool_available,
)
from app.agent_runtime.sandbox.workspace import WorkspaceManager
from app.agent_runtime.state import AgentState
from app.agent_runtime.tools.base import ToolProxy
from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
from app.core.config import settings
from app.core.tracing import get_tracer
from app.core.metrics import AGENT_RUN_DURATION, AGENT_STEPS, SANDBOX_SESSIONS_ACTIVE

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


@dataclass
class AgentRunResult:
    """Result of an agent sandbox run."""
    success: bool
    trajectory: List[Dict[str, Any]]
    final_answer: str
    workspace_state: Dict[str, Any] = field(default_factory=dict)
    workspace_files: Dict[str, str] = field(default_factory=dict)
    steps_taken: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None


class AgentRunner:
    """
    Orchestrates a full agent run inside a sandbox container.

    Usage:
        runner = AgentRunner()
        result = await runner.run(
            goal="Analyze sales.csv and create a report",
            workspace_files={"sales.csv": "..."},
            tools=["python_execute", "file_read", "file_write"],
        )
    """

    def __init__(self) -> None:
        self.workspace_manager = WorkspaceManager()

    async def run(
        self,
        goal: str,
        workspace_files: Optional[Dict[str, str]] = None,
        tools: Optional[List[str]] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        max_steps: Optional[int] = None,
        temperature: float = 0.0,
    ) -> AgentRunResult:
        """
        Run the agent in a sandbox container.

        Args:
            goal: The task goal for the agent
            workspace_files: Initial files to set up in /workspace {path: content}
            tools: List of allowed tool names (defaults to AGENT_DEFAULT_TOOLS)
            model: LLM model name (defaults to DEFAULT_LLM_MODEL)
            provider: LLM provider name (defaults to DEFAULT_LLM_PROVIDER)
            context: Additional context for the agent
            max_steps: Maximum agent steps (defaults to AGENT_MAX_STEPS)
            temperature: LLM sampling temperature

        Returns:
            AgentRunResult with trajectory, workspace state, and final answer
        """
        if not is_session_pool_available():
            return AgentRunResult(
                success=False,
                trajectory=[],
                final_answer="",
                error="Session pool unavailable (Docker not running or image missing)",
            )

        effective_max_steps = max_steps or settings.AGENT_MAX_STEPS
        effective_tools = tools or settings.AGENT_DEFAULT_TOOLS
        start_time = time.monotonic()

        with tracer.start_as_current_span("agent_run") as root_span:
            root_span.set_attribute("goal", goal[:200])
            root_span.set_attribute("model", model or settings.DEFAULT_LLM_MODEL)
            root_span.set_attribute("provider", provider or settings.DEFAULT_LLM_PROVIDER)
            root_span.set_attribute("max_steps", effective_max_steps)
            root_span.set_attribute("tools", ",".join(effective_tools))

            # ── 1. Acquire sandbox session ──
            pool = get_session_pool()
            with tracer.start_as_current_span("session_acquire") as span:
                session = await pool.acquire_session()
                if session is None:
                    root_span.set_attribute("error", "pool_exhausted")
                    return AgentRunResult(
                        success=False,
                        trajectory=[],
                        final_answer="",
                        error="Could not acquire sandbox session (pool exhausted)",
                    )
                span.set_attribute("container_id", session.container_id[:12])

            try:
                # ── 2. Set up workspace ──
                with tracer.start_as_current_span("workspace_setup") as span:
                    file_count = len(workspace_files) if workspace_files else 0
                    span.set_attribute("file_count", file_count)
                    if workspace_files:
                        await self.workspace_manager.setup(session.container, workspace_files)
                        logger.info("Workspace initialized with %d files", file_count)

                # ── 3. Create components ──
                recorder = TrajectoryRecorder()
                tool_proxy = ToolProxy(
                    container=session.container,
                    allowed_tools=effective_tools,
                    recorder=recorder,
                )

                try:
                    llm = create_llm(provider=provider, model=model, temperature=temperature)
                except ValueError as e:
                    root_span.set_attribute("error", str(e))
                    return AgentRunResult(
                        success=False,
                        trajectory=[],
                        final_answer="",
                        error=f"LLM creation failed: {e}",
                    )

                # ── 4. Build and run agent graph ──
                graph = create_agent_graph(
                    llm=llm,
                    tool_proxy=tool_proxy,
                    recorder=recorder,
                    goal=goal,
                    context=context,
                    max_steps=effective_max_steps,
                )

                initial_state: AgentState = {
                    "goal": goal,
                    "context": context,
                    "messages": [HumanMessage(content=f"Goal: {goal}\n\nStart working on this task now.")],
                    "current_step": 0,
                    "max_steps": effective_max_steps,
                    "done": False,
                    "final_answer": "",
                    "error": None,
                }

                # Run with overall timeout
                agent_timeout = settings.AGENT_TIMEOUT
                with tracer.start_as_current_span("agent_loop") as loop_span:
                    try:
                        final_state = await asyncio.wait_for(
                            graph.ainvoke(initial_state),
                            timeout=agent_timeout,
                        )
                    except asyncio.TimeoutError:
                        recorder.record_failure(
                            f"Agent timed out after {agent_timeout}s",
                            context={"goal": goal},
                        )
                        loop_span.set_attribute("timed_out", True)
                        final_state = {
                            "done": True,
                            "final_answer": f"Agent timed out after {agent_timeout}s",
                            "error": "agent_timeout",
                            "current_step": effective_max_steps,
                        }

                # ── 5. Capture workspace state ──
                with tracer.start_as_current_span("workspace_capture"):
                    workspace_state = await self.workspace_manager.capture_workspace_state(
                        session.container
                    )
                    workspace_contents = await self.workspace_manager.capture_file_contents(
                        session.container
                    )

                # ── 6. Build result ──
                duration_ms = (time.monotonic() - start_time) * 1000
                trajectory = recorder.get_trajectory()
                final_answer = final_state.get("final_answer", "")
                error = final_state.get("error")
                success = error is None

                root_span.set_attribute("steps_taken", final_state.get("current_step", 0))
                root_span.set_attribute("trajectory_steps", len(trajectory))
                root_span.set_attribute("duration_ms", round(duration_ms, 1))
                root_span.set_attribute("success", success)
                if error:
                    root_span.set_attribute("error", error)

                # Record Prometheus metrics
                AGENT_RUN_DURATION.observe(duration_ms / 1000)
                AGENT_STEPS.observe(final_state.get("current_step", 0))

                logger.info(
                    "Agent run completed: %s in %.1fs, %d steps, %d trajectory entries",
                    "success" if success else f"error={error}",
                    duration_ms / 1000,
                    final_state.get("current_step", 0),
                    len(trajectory),
                )

                return AgentRunResult(
                    success=success,
                    trajectory=trajectory,
                    final_answer=final_answer,
                    workspace_state=workspace_state,
                    workspace_files=workspace_contents,
                    steps_taken=final_state.get("current_step", 0),
                    duration_ms=duration_ms,
                    error=error,
                )

            except Exception as e:
                duration_ms = (time.monotonic() - start_time) * 1000
                root_span.set_attribute("error", str(e))
                logger.error("Agent run failed: %s", e, exc_info=True)
                return AgentRunResult(
                    success=False,
                    trajectory=[],
                    final_answer="",
                    duration_ms=duration_ms,
                    error=f"Agent run error: {e}",
                )

            finally:
                # ── 7. Release session ──
                with tracer.start_as_current_span("session_release"):
                    await pool.release_session(session)
