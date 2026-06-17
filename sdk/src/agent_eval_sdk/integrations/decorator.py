"""
@track_agent decorator - Simplest integration method.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Dict, Optional, TypeVar

from agent_eval_sdk.config import SDKConfig
from agent_eval_sdk.core.tracker import AgentTracker

F = TypeVar("F", bound=Callable[..., Any])


def track_agent(
    goal: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    config: Optional[SDKConfig] = None,
    auto_goal_from_args: bool = True,
) -> Callable[[F], F]:
    """
    Decorator: Automatically create tracking context for Agent function.

    Usage:
        @track_agent(goal="Search codebase")
        def my_agent(query: str, tracker=None):
            ...

        @track_agent(config=SDKConfig(api_base_url="http://localhost:8000"))
        async def my_agent(query: str, tracker=None):
            ...

    Decorator behavior:
    1. Create AgentTracker and start_task before function call
    2. Inject tracker as function parameter (if function signature has tracker)
    3. Auto complete_task on function return
    4. Support both sync and async functions
    """

    def decorator(func: F) -> F:
        # Check if function accepts tracker parameter
        sig = inspect.signature(func)
        accepts_tracker = "tracker" in sig.parameters

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            resolved_goal = goal or _extract_goal(func, args, kwargs, auto_goal_from_args)
            resolved_context = context or _extract_context(kwargs)

            tracker = AgentTracker(
                config=config,
                goal=resolved_goal,
                context=resolved_context,
            )

            with tracker as t:
                if accepts_tracker:
                    kwargs["tracker"] = t
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            resolved_goal = goal or _extract_goal(func, args, kwargs, auto_goal_from_args)
            resolved_context = context or _extract_context(kwargs)

            tracker = AgentTracker(
                config=config,
                goal=resolved_goal,
                context=resolved_context,
            )

            async with tracker as t:
                if accepts_tracker:
                    kwargs["tracker"] = t
                return await func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def _extract_goal(func, args, kwargs, auto: bool) -> Optional[str]:
    """Try to extract goal from function arguments."""
    if not auto:
        return func.__name__

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Try to find "goal", "query", "prompt", "task" parameters
    for candidate in ("goal", "query", "prompt", "task", "input"):
        if candidate in kwargs:
            val = kwargs[candidate]
            return str(val)[:200] if val else None
        if candidate in params:
            idx = params.index(candidate)
            if idx < len(args):
                return str(args[idx])[:200]

    return func.__name__


def _extract_context(kwargs: dict) -> Optional[Dict[str, Any]]:
    """Try to extract context from kwargs."""
    return kwargs.get("context")
