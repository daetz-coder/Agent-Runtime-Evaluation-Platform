"""
Replan Evaluator

Evaluates the quality of replanning decisions:
- Trigger Appropriateness: Was replan triggered at the right time?
- Adaptation Quality: How well was the plan adapted?
- Learning from Failure: Did the agent learn from failures?
"""

from typing import Any, Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.models.schemas import TrajectoryStep, ReplanScore


REPLAN_EVALUATION_PROMPT = You are an expert at evaluating AI agent replanning decisions.

## Goal
{goal}

## Trajectory (including replans)
{trajectory}

## Replan Events
{replan_events}

## Context
{context}

## Evaluation Criteria

Evaluate the agent's replanning on:

1. **Trigger Appropriateness** (0-100):
   - Was replanning triggered at the right time?
   - Good triggers: Repeated failures, new information, blocked paths
   - Bad triggers: Too early, too late, unnecessary replans
   - Example: After 5 consecutive failures, replan is appropriate (score: 100)
   - Example: After 1 failure, replan is premature (score: 30)
   - Example: Never replanning despite repeated failures (score: 0)

2. **Adaptation Quality** (0-100):
   - How well was the plan adapted?
   - Did the new plan address the issues that caused replanning?
   - Example: After failing to find auth code, trying a different search strategy is good adaptation.

3. **Learning from Failure** (0-100):
   - Did the agent learn from previous failures?
   - Does the new plan avoid previous mistakes?
   - Example: After wrong file path, checking file existence first shows learning.

## Output Format
Return a JSON object:
{{
    "trigger_appropriateness": <score>,
    "adaptation_quality": <score>,
    "learning_from_failure": <score>,
    "overall": <weighted average>,
    "feedback": "<detailed feedback>",
    "missed_replan_opportunities": [
        {{"step": <step_number>, "reason": "<why replan should have happened>"}}
    ],
    "unnecessary_replans": [
        {{"step": <step_number>, "reason": "<why replan was unnecessary>"}}
    ]
}}


class ReplanEvaluator(BaseEvaluator):
    """Evaluates replanning quality of agent execution."""

    WEIGHTS = {
        "trigger_appropriateness": 0.35,
        "adaptation_quality": 0.35,
        "learning_from_failure": 0.30,
    }

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> ReplanScore:
        """
        Evaluate replanning quality.

        Args:
            goal: The original goal/objective
            trajectory: List of agent execution steps
            context: Additional context

        Returns:
            ReplanScore with detailed evaluation
        """
        # Extract replan events
        replan_events = self._extract_replans(trajectory)

        # Detect potential replan opportunities
        missed_opportunities = self._detect_missed_replans(trajectory)

        # Format trajectory for evaluation
        trajectory_text = self._format_trajectory_for_replan(trajectory)
        replan_events_text = self._format_replan_events(replan_events)

        # If no replans and no missed opportunities, return default score
        if not replan_events and not missed_opportunities:
            return ReplanScore(
                trigger_appropriateness=100,
                adaptation_quality=100,
                learning_from_failure=100,
                overall=100,
                feedback="No replanning needed. Agent completed task without requiring replan.",
            )

        # Create prompt
        prompt = ChatPromptTemplate.from_template(REPLAN_EVALUATION_PROMPT)

        # Get LLM evaluation
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "goal": goal,
            "trajectory": trajectory_text,
            "replan_events": replan_events_text,
            "context": context or "No additional context provided.",
        })

        # Parse response
        scores = self._parse_scores(response.content)

        # Calculate weighted overall score
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        return ReplanScore(
            trigger_appropriateness=scores.get("trigger_appropriateness", 0),
            adaptation_quality=scores.get("adaptation_quality", 0),
            learning_from_failure=scores.get("learning_from_failure", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
        )

    def _detect_missed_replans(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Detect situations where replanning should have occurred but didn't."""
        missed = []
        consecutive_failures = 0
        replan_count = 0

        for i, step in enumerate(trajectory):
            # Track consecutive failures
            if step.action_type == "tool_call":
                obs = (step.observation or "").lower()
                if any(keyword in obs for keyword in ["error", "failed", "not found", "exception"]):
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0

            # Track replans
            if step.action_type == "replan":
                replan_count += 1
                consecutive_failures = 0  # Reset after replan

            # Detect missed replan opportunity
            if consecutive_failures >= 5 and replan_count == 0:
                missed.append({
                    "step": step.step_number,
                    "reason": f"Agent had {consecutive_failures} consecutive failures without replanning",
                })

        return missed

    def _format_trajectory_for_replan(self, trajectory: List[TrajectoryStep]) -> str:
        """Format trajectory focusing on replan-relevant information."""
        lines = []
        consecutive_failures = 0

        for step in trajectory:
            if step.action_type == "tool_call":
                obs = (step.observation or "").lower()
                is_failure = any(kw in obs for kw in ["error", "failed", "not found"])

                if is_failure:
                    consecutive_failures += 1
                    lines.append(f"Step {step.step_number}: TOOL CALL - FAILED (consecutive failures: {consecutive_failures})")
                    lines.append(f"  Tool: {step.action_detail.get('tool_name')}")
                    lines.append(f"  Error: {step.observation[:200] if step.observation else 'Unknown error'}")
                else:
                    consecutive_failures = 0
                    lines.append(f"Step {step.step_number}: TOOL CALL - Success")
                    lines.append(f"  Tool: {step.action_detail.get('tool_name')}")

            elif step.action_type == "replan":
                lines.append(f"Step {step.step_number}: REPLAN TRIGGERED")
                lines.append(f"  Reason: {step.action_detail.get('reason', 'Not specified')}")
                if step.action_detail.get("new_plan"):
                    lines.append(f"  New Plan: {step.action_detail['new_plan'][:200]}")

            elif step.action_type == "think":
                lines.append(f"Step {step.step_number}: THINK - {step.action_detail.get('thought', '')[:150]}")

        return "\n".join(lines)

    def _format_replan_events(self, replan_events: List[Dict[str, Any]]) -> str:
        """Format replan events for evaluation."""
        if not replan_events:
            return "No replan events detected."

        lines = []
        for event in replan_events:
            lines.append(f"- Step {event.get('step')}: Replan triggered")
            lines.append(f"  Reason: {event.get('reason', 'Not specified')}")
            if event.get("new_plan"):
                lines.append(f"  New Plan: {event['new_plan'][:200]}")

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
            "trigger_appropriateness": 50,
            "adaptation_quality": 50,
            "learning_from_failure": 50,
            "feedback": content,
        }
