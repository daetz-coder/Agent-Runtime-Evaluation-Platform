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
from app.models.schemas import TrajectoryStep, ToolUseScore


TOOL_USE_EVALUATION_PROMPT = """You are an expert at evaluating AI agent tool usage.

## Goal
{goal}

## Tool Calls
{tool_calls}

## Context
{context}

## Evaluation Criteria

Evaluate the agent's tool usage on:

1. **Selection Quality** (0-100):
   - Was the right tool chosen for the task?
   - Example: Using `search_code` to find auth code is good; using `run_tests` is wasteful.
   - Consider: Are there better tools available that weren't used?

2. **Parameter Accuracy** (0-100):
   - Were the tool parameters correct and complete?
   - Example: Correct file paths, appropriate search queries
   - Consider: Were there errors due to wrong parameters?

3. **Result Utilization** (0-100):
   - Were tool results used effectively?
   - Did the agent act on the information received?
   - Example: After finding auth code, did the agent analyze it properly?

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
        # Extract tool calls from trajectory
        tool_calls = self._extract_tool_calls(trajectory)

        if not tool_calls:
            return ToolUseScore(
                selection_quality=0,
                parameter_accuracy=0,
                result_utilization=0,
                overall=0,
                feedback="No tool calls found in trajectory. Agent did not use any tools.",
            )

        # Format tool calls for evaluation
        tool_calls_text = self._format_tool_calls(tool_calls)

        # Create prompt
        prompt = ChatPromptTemplate.from_template(TOOL_USE_EVALUATION_PROMPT)

        # Get LLM evaluation
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "goal": goal,
            "tool_calls": tool_calls_text,
            "context": context or "No additional context provided.",
        })

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
