"""
AgentState — TypedDict for the LangGraph agent graph state.

Defines the state that flows through the agent's ReAct loop.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State for the agent runtime ReAct loop."""

    # The goal the agent is trying to achieve
    goal: str

    # Additional context for the task
    context: Optional[Dict[str, Any]]

    # Message history (accumulated via add_messages reducer)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Current step number (incremented each loop iteration)
    current_step: int

    # Maximum number of steps before forced termination
    max_steps: int

    # Whether the agent has completed its task
    done: bool

    # Final answer from the agent (set when done=True)
    final_answer: str

    # Error message if something went wrong
    error: Optional[str]
