"""
Basic SDK Usage Example

This example demonstrates how to use the Agent Evaluation SDK
to automatically collect and report agent execution trajectories.
"""

from agent_eval_sdk import AgentTracker, SDKConfig, track_agent


# Example 1: Using the decorator
@track_agent(
    goal="Fix login bug",
    config=SDKConfig(api_base_url="http://localhost:8000"),
)
def my_agent_decorator(query: str, tracker=None):
    """Agent using decorator for automatic tracking."""
    print(f"Processing: {query}")

    # Record plan
    tracker.record_plan({
        "steps": [
            {"description": "Search for login code"},
            {"description": "Analyze the issue"},
            {"description": "Implement fix"},
            {"description": "Run tests"},
        ]
    })

    # Record tool calls
    tracker.record_tool_call(
        name="search_code",
        input={"query": "login authentication"},
        output="Found: auth/login.py, auth/jwt.py"
    )

    tracker.record_tool_call(
        name="read_file",
        input={"path": "auth/login.py"},
        output="def login(user, password): ..."
    )

    # Record thinking
    tracker.record_think("Found the bug in JWT validation logic")

    # Record fix
    tracker.record_tool_call(
        name="edit_file",
        input={"path": "auth/login.py", "change": "Fix JWT validation"},
        observation="File updated successfully"
    )

    # Record test
    tracker.record_tool_call(
        name="run_tests",
        input={"path": "tests/test_auth.py"},
        observation="All 15 tests passed"
    )

    return "Bug fixed!"


# Example 2: Using context manager
def my_agent_context(query: str):
    """Agent using context manager for tracking."""
    config = SDKConfig(api_base_url="http://localhost:8000")

    with AgentTracker(config, goal=query, context={"project": "webapp"}) as tracker:
        # Record plan
        tracker.record_plan({
            "steps": [
                {"description": "Understand the problem"},
                {"description": "Find solution"},
                {"description": "Implement"},
            ]
        })

        # Simulate agent work
        tracker.record_tool_call(
            name="search",
            input={"query": query},
            output="Found relevant code"
        )

        tracker.record_think("Analyzing the issue...")

        tracker.record_tool_call(
            name="implement",
            input={"solution": "..."},
            observation="Implemented successfully"
        )

        return "Done!"


# Example 3: Manual API
def my_agent_manual(query: str):
    """Agent using manual API for tracking."""
    config = SDKConfig(api_base_url="http://localhost:8000")
    tracker = AgentTracker(config)

    # Manually start task
    task_id = tracker.start_task(goal=query, context={"type": "manual"})
    print(f"Task ID: {task_id}")

    # Record steps
    tracker.record_plan({"steps": ["step1", "step2", "step3"]})
    tracker.record_tool_call("tool1", {"param": "value"}, output="result")
    tracker.record_think("Processing...")
    tracker.record_tool_call("tool2", {"data": "..."}, observation="Done")

    # Manually complete task
    eval_id = tracker.complete_task()
    print(f"Evaluation ID: {eval_id}")


if __name__ == "__main__":
    print("=" * 50)
    print("Agent Evaluation SDK - Usage Examples")
    print("=" * 50)

    print("\n[1] Decorator Example")
    result = my_agent_decorator("Fix login bug")
    print(f"Result: {result}")

    print("\n[2] Context Manager Example")
    result = my_agent_context("Search for authentication code")
    print(f"Result: {result}")

    print("\n[3] Manual API Example")
    result = my_agent_manual("Implement user registration")
    print(f"Result: {result}")

    print("\n" + "=" * 50)
    print("All examples completed!")
    print("Check the evaluation platform for results.")
    print("=" * 50)
