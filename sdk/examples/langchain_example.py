"""
LangChain Integration Example

This example demonstrates how to integrate the SDK with LangChain agents
for automatic trajectory collection.
"""

from agent_eval_sdk import AgentTracker, AgentEvalCallbackHandler, SDKConfig


def run_langchain_agent(query: str):
    """
    Run a LangChain agent with automatic trajectory tracking.

    This example shows how to:
    1. Create an AgentTracker
    2. Create an AgentEvalCallbackHandler
    3. Pass the handler to LangChain components
    4. Automatically collect trajectory during agent execution
    """
    # Note: This is a conceptual example
    # In real usage, you would import actual LangChain classes:
    # from langchain_openai import ChatOpenAI
    # from langchain.agents import create_react_agent

    print(f"Running LangChain agent for: {query}")

    # 1. Create SDK config
    config = SDKConfig(
        api_base_url="http://localhost:8000",
        auto_run_evaluation=True,  # Auto-run evaluation after completion
    )

    # 2. Create tracker
    tracker = AgentTracker(config, goal=query, context={"framework": "langchain"})
    tracker.start_task()

    # 3. Create callback handler
    handler = AgentEvalCallbackHandler(
        tracker,
        collect_llm_calls=True,   # Auto-capture LLM calls
        collect_tool_calls=True,  # Auto-capture tool calls
    )

    # 4. Create LangChain components with callback
    # (In real usage, these would be actual LangChain objects)
    # llm = ChatOpenAI(callbacks=[handler])
    # tools = [search_tool, read_tool, write_tool]
    # agent = create_react_agent(llm, tools, callbacks=[handler])

    # 5. Run agent - trajectory is automatically collected!
    # result = agent.invoke({"input": query})

    # For demo, manually record some steps
    tracker.record_plan({
        "agent_type": "react",
        "steps": ["search", "analyze", "implement"]
    })

    tracker.record_tool_call(
        name="search",
        input={"query": query},
        output="Found relevant code in main.py"
    )

    tracker.record_think("Analyzing the search results...")

    tracker.record_tool_call(
        name="read_file",
        input={"path": "main.py"},
        output="def main(): ... # 50 lines of code"
    )

    tracker.record_think("Found the issue, implementing fix...")

    tracker.record_tool_call(
        name="write_file",
        input={"path": "main.py", "content": "fixed code..."},
        observation="File written successfully"
    )

    # 6. Complete task - this will:
    # - Flush all remaining data
    # - Trigger evaluation (if auto_run_evaluation=True)
    eval_id = tracker.complete_task()

    print(f"Task completed!")
    print(f"Evaluation ID: {eval_id}")

    return "Agent completed successfully"


def run_with_context_manager(query: str):
    """
    Simplified version using context manager.

    The context manager automatically handles:
    - Starting the task
    - Flushing data on exit
    - Running evaluation (if configured)
    """
    config = SDKConfig(
        api_base_url="http://localhost:8000",
        auto_run_evaluation=True,
    )

    with AgentTracker(config, goal=query) as tracker:
        handler = AgentEvalCallbackHandler(tracker)

        # In real usage:
        # llm = ChatOpenAI(callbacks=[handler])
        # agent = create_agent(llm, tools, callbacks=[handler])
        # result = agent.invoke({"input": query})

        # For demo:
        tracker.record_plan({"steps": ["search", "analyze", "fix"]})
        tracker.record_tool_call("search", {"q": query}, output="found it")
        tracker.record_think("Found the issue")
        tracker.record_tool_call("fix", {"file": "main.py"}, output="fixed")

    # Automatically completed here!


if __name__ == "__main__":
    print("=" * 60)
    print("LangChain Integration Example")
    print("=" * 60)

    print("\n[1] Full Example")
    result = run_langchain_agent("Find and fix the authentication bug")
    print(f"Result: {result}")

    print("\n[2] Context Manager Example")
    run_with_context_manager("Search for database connection code")

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("Check http://localhost:3000 for evaluation results.")
    print("=" * 60)
