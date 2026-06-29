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

PLANNING_EVALUATION_PROMPT = """你必须用中文输出所有内容（包括 feedback、missing_milestones、suggestions）。你是一位 AI Agent 规划质量评估专家。

## 用户目标
{goal}

## Agent 的计划
{plan}

## 上下文
{context}

## 评估标准

请从以下维度评分（0-100 分）：

1. **覆盖率** (Coverage, 0-100):
   - 计划是否覆盖了所有必要里程碑？
   - 是否遗漏了关键步骤？
   - 考虑：分析、实现、测试、文档等阶段

2. **顺序性** (Ordering, 0-100):
   - 步骤顺序是否合理？
   - 依赖关系是否正确？
   - 是否有步骤应该调整前后顺序？

3. **粒度** (Granularity, 0-100):
   - 计划的细化程度是否适当？
   - 过细（如"阅读第20行"）不好
   - 过粗（如"实现所有功能"）也不好
   - 好的粒度如"实现 OAuth 流程"、"编写单元测试"

4. **完整性** (Completeness, 0-100):
   - 计划是否覆盖了目标的所有方面？
   - 是否考虑了边界情况？
   - 是否有明确的完成状态？

## 输出格式
返回 JSON 对象，feedback 字段请用中文：
{{
    "coverage": <分数>,
    "ordering": <分数>,
    "granularity": <分数>,
    "completeness": <分数>,
    "overall": <加权平均>,
    "feedback": "<详细的评估反馈（中文）>",
    "missing_milestones": ["缺失的关键步骤列表"],
    "suggestions": ["改进建议列表"]
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

        # Extract LLM suggestions (falls back to hardcoded if not present)
        llm_suggestions = scores.get("suggestions") or []

        return PlanningScore(
            coverage=scores.get("coverage", 0),
            ordering=scores.get("ordering", 0),
            granularity=scores.get("granularity", 0),
            completeness=scores.get("completeness", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
            llm_suggestions=llm_suggestions,
        )

    def _format_plan(self, plans: List[Dict[str, Any]]) -> str:
        """Format plan steps into readable text."""
        if not plans:
            return "No plan provided"

        lines = []
        for i, plan in enumerate(plans, 1):
            if isinstance(plan, dict):
                steps = plan.get("steps", plan.get("milestones", []))
                if isinstance(steps, list) and steps:
                    for j, step in enumerate(steps, 1):
                        if isinstance(step, dict):
                            lines.append(f"{j}. {step.get('description', step.get('name', str(step)))}")
                        else:
                            lines.append(f"{j}. {step}")
                else:
                    # No structured steps — format the plan goal/content directly
                    goal_text = plan.get("goal", "") or plan.get("plan", "") or plan.get("content", "")
                    if goal_text:
                        if plan.get("plan") and plan.get("plan") != goal_text:
                            lines.append(f"Plan: {plan['plan']}")
                        lines.append(f"Goal: {goal_text}")
                        context = plan.get("context")
                        if context and isinstance(context, dict):
                            lines.append(f"Context: {context}")
                    else:
                        lines.append(f"{i}. {plan}")
            else:
                lines.append(f"{i}. {plan}")

        return "\n".join(lines) if lines else "No structured plan data found"

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
