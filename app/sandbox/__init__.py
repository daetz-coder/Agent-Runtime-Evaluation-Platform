"""
Docker-based code execution sandbox for agent trajectory evaluation.

Provides isolated, resource-limited execution of code snippets found
in agent trajectories. Falls back gracefully when Docker is unavailable.
"""

from app.sandbox.models import ExecutionResult, SandboxLanguage

__all__ = ["ExecutionResult", "SandboxLanguage"]
