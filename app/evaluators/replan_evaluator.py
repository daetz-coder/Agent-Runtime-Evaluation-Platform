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
from app.models.schemas import ReplanScore, TrajectoryStep

REPLAN_EVALUATION_PROMPT = """你是一位 AI Agent 重规划决策评估专家。

## 用户目标
{goal}

## 轨迹（包含重规划）
{trajectory}

## 重规划事件
{replan_events}

## 上下文
{context}

## 评估标准

请从以下维度评估 Agent 的重规划能力（0-100 分）：

1. **触发适当性** (Trigger Appropriateness, 0-100):
   - 重规划是否在合适的时间触发？
   - 好的触发时机：连续失败、出现新信息、路径受阻
   - 差的触发时机：触发太早、太晚、不必要的重规划
   - 例如：连续 5 次失败后重规划是适当的（100 分）
   - 例如：1 次失败后就重规划为时过早（30 分）
   - 例如：尽管连续失败但从未重规划（0 分）

2. **适应质量** (Adaptation Quality, 0-100):
   - 计划调整得如何？
   - 新计划是否解决了导致重规划的问题？
   - 例如：找不到认证代码后尝试不同的搜索策略是好的适应。

3. **失败中学习** (Learning from Failure, 0-100):
   - Agent 是否从之前的失败中学习？
   - 新计划是否避免了之前的错误？
   - 例如：文件路径错误后，先检查文件是否存在表明有学习。

## 输出格式
返回 JSON 对象，feedback 字段请用中文：
{{
    "trigger_appropriateness": <分数>,
    "adaptation_quality": <分数>,
    "learning_from_failure": <分数>,
    "overall": <加权平均>,
    "feedback": "<详细评估反馈（中文）>",
    "missed_replan_opportunities": [
        {{"step": <步骤号>, "reason": "<应触发重规划的原因>"}}
    ],
    "unnecessary_replans": [
        {{"step": <步骤号>, "reason": "<重规划不必要的原因>"}}
    ]
}}
"""


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
        # Extract replan events and failures
        replan_events = self._extract_replans(trajectory)
        failures = self._extract_failures(trajectory)

        # Detect potential replan opportunities
        missed_opportunities = self._detect_missed_replans(trajectory)

        # Format trajectory for evaluation (including failure events)
        trajectory_text = self._format_trajectory_for_replan(trajectory)
        if failures:
            trajectory_text += "\n\n## Failure Events (Independent Records)\n"
            trajectory_text += self._format_failure_events(failures)
        replan_events_text = self._format_replan_events(replan_events)

        # If no replans and no missed opportunities, return default score
        if not replan_events and not missed_opportunities:
            return ReplanScore(
                applicable=False,
                not_applicable_reason="No replanning was needed and no missed replan opportunities were detected.",
                trigger_appropriateness=0,
                adaptation_quality=0,
                learning_from_failure=0,
                overall=0,
                feedback="Not applicable: agent completed the task without requiring replanning.",
            )

        # Create prompt
        prompt = ChatPromptTemplate.from_template(REPLAN_EVALUATION_PROMPT)

        # Get LLM evaluation (with Redis caching)
        chain = prompt | self.llm
        response = await self._invoke_llm_cached(
            chain,
            {
                "goal": goal,
                "trajectory": trajectory_text,
                "replan_events": replan_events_text,
                "context": context or "No additional context provided.",
            },
        )

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
            # Track consecutive failures from tool_call observations
            if step.action_type == "tool_call":
                obs = (step.observation or "").lower()
                if any(keyword in obs for keyword in ["error", "failed", "not found", "exception"]):
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0

            # Track failures from dedicated failure events
            if step.action_type == "failure":
                consecutive_failures += 1

            # Track replans
            if step.action_type == "replan":
                replan_count += 1
                consecutive_failures = 0  # Reset after replan

            # Detect missed replan opportunity
            if consecutive_failures >= 5 and replan_count == 0:
                missed.append(
                    {
                        "step": step.step_number,
                        "reason": f"Agent had {consecutive_failures} consecutive failures without replanning",
                    }
                )

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
                    lines.append(
                        f"Step {step.step_number}: TOOL CALL - FAILED (consecutive failures: {consecutive_failures})"
                    )
                    lines.append(f"  Tool: {step.action_detail.get('tool_name')}")
                    lines.append(f"  Error: {step.observation[:200] if step.observation else 'Unknown error'}")
                else:
                    consecutive_failures = 0
                    lines.append(f"Step {step.step_number}: TOOL CALL - Success")
                    lines.append(f"  Tool: {step.action_detail.get('tool_name')}")

            elif step.action_type == "failure":
                consecutive_failures += 1
                lines.append(f"Step {step.step_number}: FAILURE (consecutive failures: {consecutive_failures})")
                lines.append(
                    f"  Error: {step.action_detail.get('error_type', '')}: {step.action_detail.get('error_message', '')[:200]}"
                )
                lines.append(f"  Context: {step.action_detail.get('context', '')}")
                lines.append(f"  Recoverable: {step.action_detail.get('recoverable', True)}")

            elif step.action_type == "replan":
                consecutive_failures = 0
                lines.append(f"Step {step.step_number}: REPLAN TRIGGERED")
                lines.append(f"  Reason: {step.action_detail.get('reason', 'Not specified')}")
                if step.action_detail.get("new_plan"):
                    lines.append(f"  New Plan: {step.action_detail['new_plan'][:200]}")

            elif step.action_type == "retrieval":
                query = step.action_detail.get("query", "")[:100]
                count = step.action_detail.get("result_count", 0)
                lines.append(f"Step {step.step_number}: RETRIEVAL query='{query}' -> {count} docs")

            elif step.action_type == "evidence":
                etype = step.action_detail.get("evidence_type", "")
                lines.append(f"Step {step.step_number}: EVIDENCE [{etype}]")

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

    def _format_failure_events(self, failures: List[Dict[str, Any]]) -> str:
        """Format failure events for evaluation."""
        if not failures:
            return "No failure events recorded."

        lines = []
        for failure in failures:
            step = failure.get("step", "?")
            error_type = failure.get("error_type", "Unknown")
            error_msg = failure.get("error_message", "")[:200]
            context = failure.get("context", "")
            recoverable = failure.get("recoverable", True)
            node = failure.get("node_name", "")

            lines.append(f"Step {step}: FAILURE")
            lines.append(f"  Type: {error_type}")
            lines.append(f"  Message: {error_msg}")
            if context:
                lines.append(f"  Context: {context}")
            if node:
                lines.append(f"  Node: {node}")
            lines.append(f"  Recoverable: {recoverable}")
            lines.append("")

        return "\n".join(lines) if lines else "No failure events recorded"

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
