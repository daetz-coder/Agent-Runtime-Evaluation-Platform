"""
Example agent for testing and demonstration.

This agent demonstrates how to structure an agent that produces
trajectory data suitable for evaluation.
"""

from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool, tool

from app.agents.base import BaseAgent


# Example tools
@tool
def search_code(query: str) -> str:
    """Search for code files matching the query."""
    # Simulated search results
    results = {
        "auth": "Found: auth.py, login.py, jwt_handler.py",
        "database": "Found: db.py, models.py, migrations/",
        "api": "Found: routes.py, endpoints/, middleware.py",
    }
    for key, value in results.items():
        if key in query.lower():
            return value
    return f"No results found for: {query}"


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file."""
    # Simulated file reading
    files = {
        "auth.py": "def authenticate(user, password):\n    # JWT authentication logic\n    token = generate_jwt(user)\n    return token",
        "login.py": "from auth import authenticate\n\ndef login(username, password):\n    return authenticate(username, password)",
    }
    return files.get(file_path, f"File not found: {file_path}")


@tool
def run_tests(test_path: str) -> str:
    """Run tests in the specified path."""
    return f"Running tests in {test_path}...\n3 passed, 1 failed"


PLANNING_PROMPT = """You are a helpful planning assistant.

## Goal
{goal}

## Available Tools
{tools}

Create a step-by-step plan to achieve this goal.
Return the plan as a numbered list.

Example:
1. Search for relevant code files
2. Read and analyze the code
3. Identify the issue
4. Implement the fix
5. Run tests to verify
"""


class ExampleAgent(BaseAgent):
    """
    Example agent that demonstrates proper trajectory recording.

    This agent can be used to test the evaluation platform.
    """

    def __init__(self, llm: BaseChatModel):
        tools = [search_code, read_file, run_tests]
        super().__init__(llm=llm, tools=tools)

    async def run(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run the agent to achieve a goal.

        This demonstrates how an agent records its trajectory
        for evaluation.
        """
        self.reset()

        # Step 1: Create initial plan
        plan = await self._create_plan(goal)
        self._record_plan(plan)

        # Step 2: Execute plan steps
        result = await self._execute_plan(goal, plan)

        return {
            "goal": goal,
            "result": result,
            "trajectory": self.get_trajectory(),
            "steps_taken": self.step_counter,
        }

    async def _create_plan(self, goal: str) -> Dict[str, Any]:
        """Create a plan for achieving the goal."""
        tools_desc = "\n".join([f"- {t.name}: {t.description}" for t in self.tools])

        prompt = ChatPromptTemplate.from_template(PLANNING_PROMPT)
        chain = prompt | self.llm

        response = await chain.ainvoke({
            "goal": goal,
            "tools": tools_desc,
        })

        # Parse plan
        steps = self._parse_plan_steps(response.content)

        return {
            "goal": goal,
            "steps": steps,
            "raw_plan": response.content,
        }

    def _parse_plan_steps(self, plan_text: str) -> List[Dict[str, str]]:
        """Parse plan text into structured steps."""
        steps = []
        lines = plan_text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove numbering
                step_desc = line.lstrip("0123456789.-) ").strip()
                if step_desc:
                    steps.append({"description": step_desc})

        return steps if steps else [{"description": "Execute task"}]

    async def _execute_plan(
        self,
        goal: str,
        plan: Dict[str, Any],
    ) -> str:
        """Execute the plan steps."""
        steps = plan.get("steps", [])

        for i, step in enumerate(steps):
            desc = step.get("description", "")

            # Determine action based on step description
            if "search" in desc.lower() or "find" in desc.lower():
                # Search for code
                query = self._extract_search_query(goal, desc)
                tool_output = search_code.invoke({"query": query})
                self._record_tool_call("search_code", {"query": query}, tool_output)

            elif "read" in desc.lower() or "analyze" in desc.lower():
                # Read a file
                file_path = self._extract_file_path(goal, desc)
                tool_output = read_file.invoke({"file_path": file_path})
                self._record_tool_call("read_file", {"file_path": file_path}, tool_output)

            elif "test" in desc.lower():
                # Run tests
                test_path = "tests/"
                tool_output = run_tests.invoke({"test_path": test_path})
                self._record_tool_call("run_tests", {"test_path": test_path}, tool_output)

            else:
                # Record as thinking step
                self._record_think(f"Executing step {i+1}: {desc}")

        return "Task completed"

    def _extract_search_query(self, goal: str, step_desc: str) -> str:
        """Extract search query from goal and step description."""
        goal_lower = goal.lower()
        if "auth" in goal_lower or "login" in goal_lower:
            return "authentication"
        elif "database" in goal_lower or "db" in goal_lower:
            return "database"
        elif "api" in goal_lower:
            return "api"
        return goal[:50]

    def _extract_file_path(self, goal: str, step_desc: str) -> str:
        """Extract file path from goal and step description."""
        goal_lower = goal.lower()
        if "auth" in goal_lower:
            return "auth.py"
        elif "login" in goal_lower:
            return "login.py"
        return "main.py"
