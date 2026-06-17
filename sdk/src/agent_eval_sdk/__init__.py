"""
agent-eval-sdk -- Agent Evaluation Trajectory Auto-Collection SDK.

Quick Start:
    pip install agent-eval-sdk

    from agent_eval_sdk import AgentTracker, SDKConfig, track_agent

    # Method 1: Decorator
    @track_agent(config=SDKConfig(api_base_url="http://localhost:8000"))
    def my_agent(query, tracker=None):
        tracker.record_plan({"steps": ["search", "analyze"]})
        ...

    # Method 2: Context Manager
    with AgentTracker(SDKConfig(), goal="...") as tracker:
        tracker.record_plan(...)
        ...

    # Method 3: LangChain Callback
    from agent_eval_sdk import AgentEvalCallbackHandler
    handler = AgentEvalCallbackHandler(tracker)
    llm = ChatOpenAI(callbacks=[handler])

    # Method 4: Manual API
    tracker = AgentTracker(config)
    tracker.start_task(goal="...")
    tracker.record_tool_call("search", {"q": "..."}, output="...")
    tracker.complete_task()
"""

from agent_eval_sdk.config import SDKConfig
from agent_eval_sdk.core.tracker import AgentTracker
from agent_eval_sdk.core.collector import TrajectoryCollector
from agent_eval_sdk.core.reporter import AsyncReporter
from agent_eval_sdk.models import (
    ActionType,
    EvaluationResponse,
    TaskResponse,
    TrajectoryStep,
)
from agent_eval_sdk.integrations.decorator import track_agent
from agent_eval_sdk.exceptions import (
    SDKError,
    TaskNotCreatedError,
    ReportingError,
    ConfigError,
)

# Try to import LangChain integration (optional dependency)
try:
    from agent_eval_sdk.integrations.langchain_callback import AgentEvalCallbackHandler
    _has_langchain = True
except ImportError:
    _has_langchain = False

__version__ = "0.1.0"

__all__ = [
    # Core
    "AgentTracker",
    "TrajectoryCollector",
    "AsyncReporter",
    "SDKConfig",
    # Integrations
    "track_agent",
    # Models
    "ActionType",
    "TrajectoryStep",
    "TaskResponse",
    "EvaluationResponse",
    # Exceptions
    "SDKError",
    "TaskNotCreatedError",
    "ReportingError",
    "ConfigError",
]

# Add LangChain handler to __all__ if available
if _has_langchain:
    __all__.append("AgentEvalCallbackHandler")
