"""
规划质量评估器

评估 Agent 规划的质量：
- 覆盖率 (Coverage)：是否包含了关键里程碑？
- 顺序性 (Ordering)：步骤顺序是否合理？
- 粒度 (Granularity)：细节程度是否适当？
- 完整性 (Completeness)：计划是否完整？
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.evaluators.eval_schemas import PlanningEvaluationResult
from app.models.schemas import PlanningScore, TrajectoryStep

# 尝试从 YAML 加载 Prompt，失败则使用硬编码 fallback
try:
    from prompts import get_prompt
    PLANNING_EVALUATION_PROMPT = get_prompt("evaluators/planning")
except Exception:
    PLANNING_EVALUATION_PROMPT = """你必须用中文输出所有内容（包括 feedback、missing_milestones、suggestions）。你是一位 AI Agent 规划质量评估专家。

## 用户目标
{goal}

## Agent 的计划
{plan}

## 上下文
{context}

## 评估标准

请从以下维度评分（0-100 分），严格按照锚点评分：

### 1. 覆盖率 (Coverage, 0-100)
计划是否覆盖了所有必要里程碑？是否遗漏了关键步骤？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 完全没有规划，或计划与目标毫无关系 |
| 25   | 仅覆盖了目标的 1-2 个方面，遗漏了超过一半的关键步骤 |
| 50   | 覆盖了主要步骤，但遗漏了 2-3 个关键里程碑（如缺少测试、缺少错误处理） |
| 75   | 覆盖了绝大部分里程碑，仅遗漏 1 个次要步骤 |
| 100  | 完整覆盖所有必要里程碑，包括分析、实现、测试、文档、边界情况 |

### 2. 顺序性 (Ordering, 0-100)
步骤顺序是否合理？依赖关系是否正确？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 步骤顺序完全混乱，后续步骤依赖的前置条件未先完成 |
| 25   | 多处依赖关系错误（≥3 处），如先部署再测试 |
| 50   | 大致有序但有 1-2 处依赖颠倒，如先写代码再分析需求 |
| 75   | 顺序基本正确，仅 1 处可优化的顺序调整 |
| 100  | 严格的依赖拓扑排序，每一步的前置条件都已满足 |

### 3. 粒度 (Granularity, 0-100)
计划的细化程度是否适当？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 无粒度可言，只有一个笼统目标（如"完成任务"） |
| 25   | 过粗：步骤描述模糊（如"实现所有功能"、"修复 bug"），无法指导执行 |
| 50   | 粒度参差不齐：部分步骤细化到函数级，部分仍是笼统描述 |
| 75   | 粒度整体适当，仅 1-2 步过细（如"读取第 20 行"）或过粗 |
| 100  | 每步粒度一致且适当（如"实现 OAuth 回调处理"、"编写认证模块单测"） |

### 4. 完整性 (Completeness, 0-100)
计划是否覆盖了目标的所有方面？是否考虑边界情况？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 计划严重不完整，缺少核心部分，无明确完成状态 |
| 25   | 仅覆盖了 happy path，完全未考虑错误处理、边界情况、回退方案 |
| 50   | 覆盖了主要流程，但缺少错误处理或边界情况中的 1-2 项 |
| 75   | 考虑了大部分边界情况，仅缺少 1 个次要的异常处理 |
| 100  | 完整覆盖所有方面：happy path + 错误处理 + 边界情况 + 明确的完成标准 |

feedback 字段请用中文。missing_milestones 列出缺失的关键步骤，suggestions 列出改进建议。

{format_instructions}
"""


class PlanningEvaluator(BaseEvaluator):
    """评估 Agent 执行过程中的规划质量。"""

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
        评估规划质量。

        Args:
            goal: 用户的原始目标
            trajectory: Agent 执行步骤列表
            context: 附加上下文

        Returns:
            包含详细评估结果的 PlanningScore
        """
        # 从轨迹中提取计划和计划更新
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

        # 格式化计划用于评估（包含计划更新）
        plan_text = self._format_plan(plans)
        if plan_updates:
            plan_text += "\n\n## Plan Updates (Dynamic Adjustments)\n"
            plan_text += self._format_plan_updates(plan_updates)

        # 创建提示词 + 结构化输出链
        prompt = ChatPromptTemplate.from_template(PLANNING_EVALUATION_PROMPT)
        structured_llm = self.llm.with_structured_output(PlanningEvaluationResult)
        chain = prompt | structured_llm

        # 获取 LLM 评估结果（结构化输出 + 重试机制）
        result = await self._invoke_structured_llm(
            chain,
            {
                "goal": goal,
                "plan": plan_text,
                "context": context or "No additional context provided.",
                "format_instructions": "",  # PydanticOutputParser 降级时会覆盖
            },
            schema_class=PlanningEvaluationResult,
            max_retries=3,
            prompt=prompt,
        )

        # Pydantic model 直接使用
        scores = result.model_dump() if isinstance(result, PlanningEvaluationResult) else result

        # 计算加权总分
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        # 提取 LLM 建议（无建议时返回空列表）
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
        """将计划步骤格式化为可读文本。"""
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
                    # 没有结构化步骤，直接格式化计划的目标/内容
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
        """将计划更新格式化为可读文本。"""
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
        """将 LLM 响应解析为评分字典（仅用于 fallback 场景）。"""
        parsed = self._parse_json_from_llm(content)
        if parsed is not None:
            return parsed

        return {
            "coverage": 50,
            "ordering": 50,
            "granularity": 50,
            "completeness": 50,
            "feedback": content,
        }
