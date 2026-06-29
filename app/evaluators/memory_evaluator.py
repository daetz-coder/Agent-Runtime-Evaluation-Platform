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

MEMORY_EVALUATION_PROMPT = """你必须用中文输出所有内容（包括 feedback、forgotten_facts、inconsistencies）。你是一位 AI Agent 记忆质量评估专家。

## 用户目标
{goal}

## 轨迹（展示记忆使用情况）
{trajectory}

## 应记住的关键事实
{key_facts}

## 上下文
{context}

## 评估标准

请从以下维度评估 Agent 的记忆能力（0-100 分）：

1. **保持力** (Retention, 0-100):
   - Agent 是否在整个执行过程中记住关键事实？
   - 例如：如果项目使用 JWT，Agent 在处理认证时应记住这一点。
   - 关键：忘记影响解决方案的关键事实是重大问题。

2. **相关性** (Relevance, 0-100):
   - Agent 回忆的信息是否相关？
   - 是否恰当地使用了回忆的信息？
   - 例如：修复认证 bug 时回忆 JWT 使用情况是相关的。

3. **一致性** (Consistency, 0-100):
   - Agent 的记忆在整个执行过程中是否一致？
   - Agent "记住"的信息是否存在矛盾？
   - 例如：先说"项目使用 JWT"后来又说"项目使用 sessions"是不一致的。

## 输出格式
返回 JSON 对象，feedback 字段请用中文：
{{
    "retention": <分数>,
    "relevance": <分数>,
    "consistency": <分数>,
    "overall": <加权平均>,
    "feedback": "<详细评估反馈（中文）>",
    "forgotten_facts": ["被遗忘的重要事实列表"],
    "inconsistencies": ["记忆不一致列表"]
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
