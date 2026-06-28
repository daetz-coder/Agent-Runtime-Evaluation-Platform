"""
Memory Evaluator

Evaluates the quality of agent memory:
- Retention: Are key facts retained?
- Relevance: Is recalled information relevant?
- Consistency: Is memory consistent with context?
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.models.schemas import MemoryScore, TrajectoryStep

MEMORY_EVALUATION_PROMPT = """You are an expert at evaluating AI agent memory quality.

## Goal
{goal}

## Trajectory (showing memory usage)
{trajectory}

## Key Facts That Should Be Remembered
{key_facts}

## Context
{context}

## Evaluation Criteria

Evaluate the agent's memory on:

1. **Retention** (0-100):
   - Does the agent remember key facts throughout execution?
   - Example: If the project uses JWT, the agent should remember this when working on auth.
   - Critical: Forgetting key facts that affect the solution is a major issue.

2. **Relevance** (0-100):
   - When the agent recalls information, is it relevant?
   - Does it use recalled information appropriately?
   - Example: Recalling JWT usage when fixing auth bugs is relevant.

3. **Consistency** (0-100):
   - Is the agent's memory consistent throughout execution?
   - Are there contradictions in what the agent "remembers"?
   - Example: Saying "project uses JWT" then later "project uses sessions" is inconsistent.

## Output Format
Return a JSON object:
{{
    "retention": <score>,
    "relevance": <score>,
    "consistency": <score>,
    "overall": <weighted average>,
    "feedback": "<detailed feedback>",
    "forgotten_facts": ["list of important facts that were forgotten"],
    "inconsistencies": ["list of memory inconsistencies"]
}}
"""


class MemoryEvaluator(BaseEvaluator):
    """Evaluates memory quality of agent execution."""

    WEIGHTS = {
        "retention": 0.45,
        "relevance": 0.30,
        "consistency": 0.25,
    }

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> MemoryScore:
        """
        Evaluate memory quality.

        Args:
            goal: The original goal/objective
            trajectory: List of agent execution steps
            context: Additional context (should include key_facts)

        Returns:
            MemoryScore with detailed evaluation
        """
        if not trajectory:
            return MemoryScore(
                retention=0,
                relevance=0,
                consistency=0,
                overall=0,
                feedback="No trajectory steps provided for memory evaluation.",
            )

        # Extract key facts from context
        key_facts = context.get("key_facts", []) if context else []
        if not key_facts:
            key_facts = self._infer_key_facts(goal, trajectory)

        # Extract memory events (explicit reads/writes)
        memory_events = self._extract_memory_events(trajectory)

        # Format trajectory for evaluation
        trajectory_text = self._format_trajectory(trajectory)
        key_facts_text = self._format_key_facts(key_facts)

        # Append explicit memory events if available
        if memory_events:
            trajectory_text += "\n\n## Explicit Memory Events\n"
            trajectory_text += self._format_memory_events(memory_events)

        # Create prompt
        prompt = ChatPromptTemplate.from_template(MEMORY_EVALUATION_PROMPT)

        # Get LLM evaluation (with Redis caching)
        chain = prompt | self.llm
        response = await self._invoke_llm_cached(
            chain,
            {
                "goal": goal,
                "trajectory": trajectory_text,
                "key_facts": key_facts_text,
                "context": context or "No additional context provided.",
            },
        )

        # Parse response
        scores = self._parse_scores(response.content)

        # Calculate weighted overall score
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        return MemoryScore(
            retention=scores.get("retention", 0),
            relevance=scores.get("relevance", 0),
            consistency=scores.get("consistency", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
        )

    def _infer_key_facts(self, goal: str, trajectory: List[TrajectoryStep]) -> List[str]:
        """Infer key facts that should be remembered from trajectory."""
        key_facts = []

        # Look for facts mentioned in early steps
        for step in trajectory[:10]:
            if step.observation:
                # Extract potential key facts from observations
                obs = step.observation.lower()
                if "jwt" in obs:
                    key_facts.append("Project uses JWT for authentication")
                if "react" in obs:
                    key_facts.append("Frontend uses React")
                if "python" in obs or "fastapi" in obs:
                    key_facts.append("Backend uses Python/FastAPI")
                if "database" in obs or "postgres" in obs:
                    key_facts.append("Uses PostgreSQL database")

        # Add goal-related facts
        goal_lower = goal.lower()
        if "auth" in goal_lower or "login" in goal_lower:
            key_facts.append("Task involves authentication")
        if "bug" in goal_lower or "fix" in goal_lower:
            key_facts.append("Task is bug-fixing")

        return key_facts if key_facts else ["No specific key facts identified"]

    def _format_key_facts(self, key_facts: List[str]) -> str:
        """Format key facts into readable text."""
        if not key_facts:
            return "No key facts provided"

        lines = []
        for i, fact in enumerate(key_facts, 1):
            lines.append(f"{i}. {fact}")

        return "\n".join(lines)

    def _format_memory_events(self, memory_events: List[Dict[str, Any]]) -> str:
        """Format memory events into readable text."""
        lines = []
        for event in memory_events:
            step = event.get("step", "?")
            event_type = event.get("type", "unknown")
            key = event.get("key", "")
            value = event.get("value", "")
            source = event.get("source", "")
            context = event.get("context", "")
            hit = event.get("hit", True)
            memory_type = event.get("memory_type", "")

            if event_type == "memory_write":
                lines.append(f"Step {step}: WRITE [{memory_type}] {key} = {str(value)[:200]}")
                if source:
                    lines.append(f"  Source: {source}")
            elif event_type == "memory_read":
                status = "HIT" if hit else "MISS"
                lines.append(f"Step {step}: READ [{status}] {key}")
                if value:
                    lines.append(f"  Value: {str(value)[:200]}")
                if context:
                    lines.append(f"  Context: {context}")
            lines.append("")

        return "\n".join(lines) if lines else "No memory events recorded"

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
            "retention": 50,
            "relevance": 50,
            "consistency": 50,
            "feedback": content,
        }
