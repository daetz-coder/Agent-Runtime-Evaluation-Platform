"""
Agent Runtime — Platform built-in agent that runs inside sandbox containers.

The agent's workspace and tool execution happen inside Docker containers,
while the LLM reasoning loop runs in the platform backend.
"""

from app.agent_runtime.runner import AgentRunner, AgentRunResult
from app.agent_runtime.trajectory_recorder import TrajectoryRecorder

__all__ = ["AgentRunner", "AgentRunResult", "TrajectoryRecorder"]
