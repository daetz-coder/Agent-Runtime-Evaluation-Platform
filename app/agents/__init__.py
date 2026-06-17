"""
Agent modules for the evaluation platform.

Note: These are example agents that can be used for testing.
The platform evaluates external agent trajectories, not these agents directly.
"""

from app.agents.base import BaseAgent
from app.agents.example_agent import ExampleAgent

__all__ = ["BaseAgent", "ExampleAgent"]
