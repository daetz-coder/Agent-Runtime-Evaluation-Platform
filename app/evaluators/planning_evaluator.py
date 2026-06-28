"""
Planning Quality Evaluator

Evaluates the quality of agent planning:
- Coverage: Are key milestones included?
- Ordering: Is the sequence logical?
- Granularity: Is the level of detail appropriate?
- Completeness: Is the plan complete?
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.models.schemas import PlanningScore, TrajectoryStep

PLANNING_EVALUATION_PROMPT = """You are an expert at evaluating AI agent planning quality.

## Goal
{goal}

## Agent's Plan
{plan}

## Context
{context}

## Evaluation Criteria

Evaluate the plan on the following dimensions (0-100 scale):

1. **Coverage** (0-100):
   - Does the plan cover all necessary milestones?
   - Are there any critical steps missing?
   - Consider: analysis, implementation, testing, documentation, etc.

2. **Ordering** (0-100):
   - Is the sequence of steps logical?
   - Do dependencies flow correctly?
   - Are there any steps that should come before/after others?

3. **Granularity** (0-100):
   - Is the level of detail appropriate?
   - Too fine-grained (e.g., "read line 20") is bad
   - Too coarse (e.g., "implement everything") is also bad
   - Good granularity: "Implement OAuth flow", "Write unit tests"

4. **Completeness** (0-100):
   - Does the plan address all aspects of the goal?
   - Are edge cases considered?
   - Is there a clear end state?

## Output Format
Return a JSON object with these fields:
{{
    "coverage": <score>,
    "ordering": <score>,
    "granularity": <score>,
    "completeness": <score>,
    "overall": <weighted average>,
    "feedback": "<detailed feedback explaining scores>",
    "missing_milestones": ["list of missing key steps"],
    "suggestions": ["list of improvement suggestions"]
}}
"""


class PlanningEvaluator(BaseEvaluator):
    """Evaluates planning quality of agent execution."""

    WEIGHTS = {
        "coverage": 0.3,
        "ordering": 0.2,
        "granularity": 0.2,
        "completeness": 0.3,
    }

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> PlanningScore:
        """
        Evaluate planning quality.

        Args:
            goal: The original goal/objective
            trajectory: List of agent execution steps
            context: Additional context

        Returns:
            PlanningScore with detailed evaluation
        """
        # Extract plan and plan_update from trajectory
        plans = self._extract_plans(trajectory)
        plan_updates = self._extract_plan_updates(trajectory)

        if not plans and not plan_updates:
            return PlanningScore(
                coverage=0,
                ordering=0,
                granularity=0,
                completeness=0,
                overall=0,
                feedback="No planning steps found in trajectory. Agent did not create an explicit plan.",
            )

        # Format plan for evaluation (including plan updates)
        plan_text = self._format_plan(plans)
        if plan_updates:
            plan_text += "\n\n## Plan Updates (Dynamic Adjustments)\n"
            plan_text += self._format_plan_updates(plan_updates)

        # Create prompt
        prompt = ChatPromptTemplate.from_template(PLANNING_EVALUATION_PROMPT)

        # Get LLM evaluation (with Redis caching)
        chain = prompt | self.llm
        response = await self._invoke_llm_cached(
            chain,
            {
                "goal": goal,
                "plan": plan_text,
                "context": context or "No additional context provided.",
            },
        )

        # Parse response
        scores = self._parse_scores(response.content)

        # Calculate weighted overall score
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        return PlanningScore(
            coverage=scores.get("coverage", 0),
            ordering=scores.get("ordering", 0),
            granularity=scores.get("granularity", 0),
            completeness=scores.get("completeness", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
        )

    def _format_plan(self, plans: List[Dict[str, Any]]) -> str:
        """Format plan steps into readable text."""
        if not plans:
            return "No plan provided"

        lines = []
        for i, plan in enumerate(plans, 1):
            if isinstance(plan, dict):
                steps = plan.get("steps", plan.get("milestones", []))
                if isinstance(steps, list):
                    for j, step in enumerate(steps, 1):
                        if isinstance(step, dict):
                            lines.append(f"{j}. {step.get('description', step.get('name', str(step)))}")
                        else:
                            lines.append(f"{j}. {step}")
                else:
                    lines.append(f"{i}. {plan}")
            else:
                lines.append(f"{i}. {plan}")

        return "\n".join(lines) if lines else "Plan format not recognized"

    def _format_plan_updates(self, plan_updates: List[Dict[str, Any]]) -> str:
        """Format plan updates into readable text."""
        lines = []
        for update in plan_updates:
            step = update.get("step", "?")
            next_action = update.get("next_action", "")
            reason = update.get("reason", "")
            status = update.get("milestone_status", {})
            remaining = update.get("remaining_steps", [])

            lines.append(f"Step {step}: Plan Update")
            lines.append(f"  Next Action: {next_action}")
            if reason:
                lines.append(f"  Reason: {reason}")
            if status:
                status_str = ", ".join(f"{k}={v}" for k, v in status.items())
                lines.append(f"  Milestone Status: {status_str}")
            if remaining:
                lines.append(f"  Remaining: {', '.join(remaining)}")
            lines.append("")

        return "\n".join(lines) if lines else "No plan updates"

    def _parse_scores(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into scores dictionary."""
        import json

        try:
            # Try to extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end != -1:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Fallback: return default scores with feedback
        return {
            "coverage": 50,
            "ordering": 50,
            "granularity": 50,
            "completeness": 50,
            "feedback": content,
        }
