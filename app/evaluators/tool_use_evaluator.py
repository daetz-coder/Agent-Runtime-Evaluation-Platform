"""
Tool Use Evaluator

Evaluates the quality of tool selection and usage:
- Selection Quality: Was the right tool chosen?
- Parameter Accuracy: Were the parameters correct?
- Result Utilization: Were tool results used effectively?
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.models.schemas import ToolUseScore, TrajectoryStep

TOOL_USE_EVALUATION_PROMPT = """You are an expert at evaluating AI agent tool usage.

## Goal
{goal}

## Tool Calls
{tool_calls}

## Context
{context}

## Execution Results
The tool results below are real execution results from a sandboxed environment.
They reflect what actually happened when the agent ran each tool.

{execution_results}

## Evaluation Criteria

Evaluate the agent's tool usage on:

1. **Selection Quality** (0-100):
   - Was the right tool chosen for the task?
   - Example: Using `python_execute` to analyze data is good; using `bash_execute` for complex math is wasteful.
   - Consider: Are there better tools available that weren't used?

2. **Parameter Accuracy** (0-100):
   - Were the tool parameters correct and complete?
   - Example: Correct file paths, appropriate code syntax
   - Consider: Were there errors due to wrong parameters?
   - If tool execution failed, check if the agent diagnosed and corrected the issue.

3. **Result Utilization** (0-100):
   - Were tool results used effectively?
   - Did the agent act on the information received?
   - Example: After reading a file, did the agent analyze it properly?
   - Did the agent iterate on failures or give up prematurely?

## Output Format
Return a JSON object:
{{
    "selection_quality": <score>,
    "parameter_accuracy": <score>,
    "result_utilization": <score>,
    "overall": <weighted average>,
    "feedback": "<detailed feedback>",
    "inefficient_calls": [
        {{"tool": "<name>", "issue": "<description>", "suggestion": "<improvement>"}}
    ]
}}
"""


class ToolUseEvaluator(BaseEvaluator):
    """Evaluates tool usage quality of agent execution."""

    WEIGHTS = {
        "selection_quality": 0.40,
        "parameter_accuracy": 0.30,
        "result_utilization": 0.30,
    }

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolUseScore:
        """
        Evaluate tool usage quality.

        Args:
            goal: The original goal/objective
            trajectory: List of agent execution steps
            context: Additional context

        Returns:
            ToolUseScore with detailed evaluation
        """
        # Extract tool calls and tool results from trajectory
        tool_calls = self._extract_tool_calls(trajectory)
        tool_results = self._extract_tool_results(trajectory)

        if not tool_calls:
            return ToolUseScore(
                selection_quality=0,
                parameter_accuracy=0,
                result_utilization=0,
                overall=0,
                feedback="No tool calls found in trajectory. Agent did not use any tools.",
            )

        # Format tool calls for evaluation (including tool results)
        tool_calls_text = self._format_tool_calls(tool_calls)

        # Format execution results from trajectory (real sandbox results)
        execution_results_text = "No tool results recorded"
        if tool_results:
            execution_results_text = self._format_tool_results(tool_results)

        # Create prompt
        prompt = ChatPromptTemplate.from_template(TOOL_USE_EVALUATION_PROMPT)

        # Get LLM evaluation (with Redis caching)
        chain = prompt | self.llm
        response = await self._invoke_llm_cached(
            chain,
            {
                "goal": goal,
                "tool_calls": tool_calls_text,
                "context": context or "No additional context provided.",
                "execution_results": execution_results_text,
            },
        )

        # Parse response
        scores = self._parse_scores(response.content)

        # Calculate weighted overall score
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        return ToolUseScore(
            selection_quality=scores.get("selection_quality", 0),
            parameter_accuracy=scores.get("parameter_accuracy", 0),
            result_utilization=scores.get("result_utilization", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
        )

    def _format_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> str:
        """Format tool calls into readable text."""
        lines = []
        for call in tool_calls:
            step = call.get("step", "?")
            tool = call.get("tool", "unknown")
            inp = call.get("input", {})
            output = call.get("output", "No output recorded")

            lines.append(f"Step {step}:")
            lines.append(f"  Tool: {tool}")
            lines.append(f"  Input: {inp}")
            lines.append(f"  Output: {output[:300] if output else 'None'}")
            lines.append("")

        return "\n".join(lines)

    def _format_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        """Format tool results into readable text."""
        lines = []
        for result in tool_results:
            step = result.get("step", "?")
            tool = result.get("tool_name", "unknown")
            success = result.get("success", True)
            duration = result.get("duration_ms")
            error = result.get("error_type")
            output = result.get("output", "No output")

            status = "SUCCESS" if success else f"FAILED ({error})"
            duration_str = f" ({duration:.0f}ms)" if duration else ""
            lines.append(f"Step {step}: {tool} -> {status}{duration_str}")
            if output:
                lines.append(f"  Output: {str(output)[:300]}")
            lines.append("")

        return "\n".join(lines) if lines else "No tool results recorded"

    def _parse_scores(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into scores dictionary."""
        import json

        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end != -1:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        return {
            "selection_quality": 50,
            "parameter_accuracy": 50,
            "result_utilization": 50,
            "feedback": content,
        }
