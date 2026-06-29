"""
Tactical Evaluator

Evaluates the quality of next-action decisions:
- Relevance: Is the action relevant to current state?
- Efficiency: Is the action efficient?
- Correctness: Is the action correct?
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.models.schemas import TacticalScore, TrajectoryStep

TACTICAL_EVALUATION_PROMPT = """你必须用中文输出所有内容（包括 feedback、problematic_actions）。你是一位 AI Agent 战术决策评估专家。

## 用户目标
{goal}

## 当前状态
{current_state}

## Agent 的行动
{actions}

## 上下文
{context}

## 评估标准

请从以下维度评估 Agent 的战术决策（下一步行动，0-100 分）：

1. **相关性** (Relevance, 0-100):
   - 行动是否与当前状态和目标相关？
   - 是否朝着目标推进？
   - 例如：分析认证代码时读取 auth.py 是相关的，运行测试则无关。

2. **效率** (Efficiency, 0-100):
   - 行动在当前情况下是否高效？
   - 是否有不必要的绕路？
   - 例如：在根因分析之前就创建 PR 是低效的。

3. **正确性** (Correctness, 0-100):
   - 行动是否在给定上下文中正确？
   - 专家会做同样的事吗？
   - 例如：修复前先阅读代码是正确的，修复前不阅读是错误的。

## 输出格式
返回 JSON 对象，feedback 字段请用中文：
{{
    "relevance": <分数>,
    "efficiency": <分数>,
    "correctness": <分数>,
    "overall": <加权平均>,
    "feedback": "<详细评估反馈（中文）>",
    "problematic_actions": [
        {{"step": <步骤号>, "issue": "<问题描述>", "suggestion": "<改进建议>"}}
    ]
}}
"""


class TacticalEvaluator(BaseEvaluator):
    """Evaluates tactical decision quality of agent execution."""

    WEIGHTS = {
        "relevance": 0.35,
        "efficiency": 0.30,
        "correctness": 0.35,
    }

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> TacticalScore:
        """
        Evaluate tactical decisions.

        Args:
            goal: The original goal/objective
            trajectory: List of agent execution steps
            context: Additional context

        Returns:
            TacticalScore with detailed evaluation
        """
        if not trajectory:
            return TacticalScore(
                relevance=0,
                efficiency=0,
                correctness=0,
                overall=0,
                feedback="No trajectory steps provided for evaluation.",
            )

        # Extract actions (non-plan steps)
        actions = self._extract_actions(trajectory)
        current_state = self._determine_current_state(trajectory)

        # Format actions for evaluation
        actions_text = self._format_actions(actions)

        # Create prompt
        prompt = ChatPromptTemplate.from_template(TACTICAL_EVALUATION_PROMPT)

        # Get LLM evaluation (with Redis caching)
        chain = prompt | self.llm
        response = await self._invoke_llm_cached(
            chain,
            {
                "goal": goal,
                "current_state": current_state,
                "actions": actions_text,
                "context": context or "No additional context provided.",
            },
        )

        # Parse response
        scores = self._parse_scores(response.content)

        # Calculate weighted overall score
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        return TacticalScore(
            relevance=scores.get("relevance", 0),
            efficiency=scores.get("efficiency", 0),
            correctness=scores.get("correctness", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
        )

    def _extract_actions(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract action steps (excluding plans)."""
        return [
            {
                "step": step.step_number,
                "type": step.action_type,
                "detail": step.action_detail,
                "observation": step.observation,
            }
            for step in trajectory
            if step.action_type != "plan"
        ]

    def _determine_current_state(self, trajectory: List[TrajectoryStep]) -> str:
        """Determine the current state from trajectory."""
        if not trajectory:
            return "Initial state"

        # Look at recent steps to determine state
        recent_steps = trajectory[-3:] if len(trajectory) >= 3 else trajectory
        state_parts = []

        for step in recent_steps:
            if step.action_type == "tool_call":
                tool_name = step.action_detail.get("tool_name", "unknown")
                state_parts.append(f"Used tool: {tool_name}")
            elif step.action_type == "tool_result":
                success = step.action_detail.get("success", True)
                tool_name = step.action_detail.get("tool_name", "unknown")
                state_parts.append(f"Tool result: {tool_name} ({'OK' if success else 'FAIL'})")
            elif step.action_type == "think":
                state_parts.append(f"Thinking: {step.action_detail.get('thought', '')[:100]}")
            elif step.action_type == "replan":
                state_parts.append("Triggered replan")
            elif step.action_type == "plan_update":
                state_parts.append(f"Plan update: {step.action_detail.get('next_action', '')}")
            elif step.action_type == "failure":
                state_parts.append(f"Failure: {step.action_detail.get('error_type', '')}")
            elif step.action_type == "memory_write":
                state_parts.append(f"Memory write: {step.action_detail.get('key', '')}")
            elif step.action_type == "memory_read":
                state_parts.append(f"Memory read: {step.action_detail.get('key', '')}")
            elif step.action_type == "retrieval":
                state_parts.append(f"Retrieved {step.action_detail.get('result_count', 0)} docs")
            elif step.action_type == "evidence":
                state_parts.append(f"Evidence pool: {step.action_detail.get('evidence_type', '')}")
            elif step.action_type == "state_change":
                state_parts.append(f"State changed: {step.action_detail.get('trigger', '')}")

        return " -> ".join(state_parts) if state_parts else "In progress"

    def _format_actions(self, actions: List[Dict[str, Any]]) -> str:
        """Format actions into readable text."""
        lines = []
        for action in actions:
            step_num = action["step"]
            action_type = action["type"]
            detail = action["detail"]

            if action_type == "tool_call":
                tool = detail.get("tool_name", "unknown")
                inp = detail.get("input", {})
                lines.append(f"Step {step_num}: Call tool '{tool}' with input: {inp}")
            elif action_type == "tool_result":
                tool = detail.get("tool_name", "unknown")
                success = detail.get("success", True)
                error = detail.get("error_type")
                status = "SUCCESS" if success else f"FAILED ({error})"
                lines.append(f"Step {step_num}: Tool result '{tool}' -> {status}")
            elif action_type == "think":
                thought = detail.get("thought", "")[:200]
                lines.append(f"Step {step_num}: Think - {thought}")
            elif action_type == "plan_update":
                next_action = detail.get("next_action", "")
                reason = detail.get("reason", "")
                lines.append(f"Step {step_num}: Plan update -> {next_action} ({reason})")
            elif action_type == "failure":
                error_type = detail.get("error_type", "Unknown")
                error_msg = detail.get("error_message", "")[:150]
                lines.append(f"Step {step_num}: FAILURE [{error_type}] - {error_msg}")
            elif action_type == "memory_write":
                key = detail.get("key", "")
                lines.append(f"Step {step_num}: Memory WRITE '{key}'")
            elif action_type == "memory_read":
                key = detail.get("key", "")
                hit = detail.get("hit", True)
                lines.append(f"Step {step_num}: Memory READ '{key}' ({'HIT' if hit else 'MISS'})")
            elif action_type == "replan":
                reason = detail.get("reason", "")[:150]
                lines.append(f"Step {step_num}: REPLAN - {reason}")
            elif action_type == "retrieval":
                query = detail.get("query", "")[:100]
                count = detail.get("result_count", 0)
                source = detail.get("source", "")
                lines.append(f"Step {step_num}: RETRIEVAL [{source}] query='{query}' -> {count} docs")
            elif action_type == "evidence":
                etype = detail.get("evidence_type", "")
                sources = detail.get("sources", {})
                docs_count = sources.get("retrieved_docs_count", 0)
                tools_count = sources.get("tool_results_count", 0)
                mem_count = sources.get("memory_results_count", 0)
                lines.append(
                    f"Step {step_num}: EVIDENCE [{etype}] docs={docs_count} tools={tools_count} memory={mem_count}"
                )
            elif action_type == "state_change":
                trigger = detail.get("trigger", "")
                lines.append(f"Step {step_num}: State changed by '{trigger}'")
            else:
                lines.append(f"Step {step_num}: {action_type} - {detail}")

            if action.get("observation"):
                lines.append(f"  Result: {action['observation'][:200]}")

        return "\n".join(lines) if lines else "No actions recorded"

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
            "relevance": 50,
            "efficiency": 50,
            "correctness": 50,
            "feedback": content,
        }
