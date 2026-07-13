"""
重规划评估器

评估 Agent 重规划决策的质量：
- 触发适当性 (Trigger Appropriateness)：重规划是否在合适的时间触发？
- 适应质量 (Adaptation Quality)：计划调整得如何？
- 失败中学习 (Learning from Failure)：Agent 是否从失败中学习？
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.evaluators.eval_schemas import ReplanEvaluationResult
from app.models.schemas import ReplanScore, TrajectoryStep

# 尝试从 YAML 加载 Prompt，失败则使用硬编码 fallback
try:
    from prompts import get_prompt
    REPLAN_EVALUATION_PROMPT = get_prompt("evaluators/replan")
except Exception:
    REPLAN_EVALUATION_PROMPT = """你必须用中文输出所有内容（包括 feedback、missed_replan_opportunities、unnecessary_replans）。你是一位 AI Agent 重规划决策评估专家。

## 用户目标
{goal}

## 轨迹（包含重规划）
{trajectory}

## 重规划事件
{replan_events}

## 上下文
{context}

## 评估标准

请从以下维度评估 Agent 的重规划能力（0-100 分），严格按照锚点评分：

### 1. 触发适当性 (Trigger Appropriateness, 0-100)
重规划是否在合适的时间触发？好的触发时机：连续失败、出现新信息、路径受阻。

| 分数 | 锚点表现 |
|------|----------|
| 0    | 尽管连续 5+ 次失败或路径明显受阻，Agent 从未重规划，死磕到底 |
| 25   | 重规划触发太晚：连续 3-4 次相同失败后才触发，浪费了大量时间 |
| 50   | 触发时机基本合理但有偏差：要么 1 次失败就触发（太早），要么 3 次后才触发（略晚） |
| 75   | 触发时机恰当，仅 1 次轻微偏差（如可以多试 1 次再触发，或少试 1 次更好） |
| 100  | 精准触发：在连续失败 2-3 次或出现明确的新信息/阻断信号时立即重规划 |

### 2. 适应质量 (Adaptation Quality, 0-100)
新计划是否解决了导致重规划的问题？计划调整得如何？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 重规划后的新计划与旧计划几乎相同，没有实质变化 |
| 25   | 新计划有变化但未针对失败原因：换了步骤但核心问题未解决 |
| 50   | 新计划部分解决了失败原因，但仍有 1-2 处可能重蹈覆辙 |
| 75   | 新计划较好地解决了失败原因，仅 1 处细节可改进 |
| 100  | 新计划精准针对失败原因：换策略、换工具、换路径，从根本上避免同样失败 |

### 3. 失败中学习 (Learning from Failure, 0-100)
Agent 是否从之前的失败中学习？新计划是否避免了之前的错误？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 完全没有学习：重规划后重复同样的错误（如用同样错误的路径、同样的工具） |
| 25   | 学习微弱：避免了 1 个旧错误但引入了同类的新错误 |
| 50   | 部分学习：避免了主要旧错误，但未完全吸取教训（如换了路径但未先验证） |
| 75   | 学习良好：明确避免了旧错误，仅 1 个细节未完全吸取教训 |
| 100  | 深度学习：每条失败经验都被转化为新计划的改进点，错误零重复 |

feedback 字段请用中文。missed_replan_opportunities 列出错过的重规划时机，unnecessary_replans 列出不必要的重规划（各含 step、reason）。

{format_instructions}
"""


class ReplanEvaluator(BaseEvaluator):
    """评估 Agent 执行过程中的重规划质量。"""

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
        评估重规划质量。

        Args:
            goal: 用户的原始目标
            trajectory: Agent 执行步骤列表
            context: 附加上下文

        Returns:
            包含详细评估结果的 ReplanScore
        """
        # 提取重规划事件和失败事件
        replan_events = self._extract_replans(trajectory)
        failures = self._extract_failures(trajectory)

        # 检测潜在的重规划时机
        missed_opportunities = self._detect_missed_replans(trajectory)

        # 格式化轨迹用于评估（包含失败事件）
        trajectory_text = self._format_trajectory_for_replan(trajectory)
        if failures:
            trajectory_text += "\n\n## Failure Events (Independent Records)\n"
            trajectory_text += self._format_failure_events(failures)
        replan_events_text = self._format_replan_events(replan_events)

        # 如果没有重规划且没有错过的时机，返回默认分数
        if not replan_events and not missed_opportunities:
            return ReplanScore(
                applicable=False,
                not_applicable_reason="Agent 顺利完成未触发重规划，该维度已从综合评分中剔除。",
                trigger_appropriateness=0,
                adaptation_quality=0,
                learning_from_failure=0,
                overall=0,
                feedback="不适用：Agent 顺利完成，无需重规划。",
            )

        # 创建提示词 + 结构化输出链
        prompt = ChatPromptTemplate.from_template(REPLAN_EVALUATION_PROMPT)
        structured_llm = self.llm.with_structured_output(ReplanEvaluationResult)
        chain = prompt | structured_llm

        # 获取 LLM 评估结果（结构化输出 + 重试机制）
        result = await self._invoke_structured_llm(
            chain,
            {
                "goal": goal,
                "trajectory": trajectory_text,
                "replan_events": replan_events_text,
                "context": context or "No additional context provided.",
                "format_instructions": "",  # PydanticOutputParser 降级时会覆盖
            },
            schema_class=ReplanEvaluationResult,
            max_retries=3,
            prompt=prompt,
        )

        # Pydantic model 直接使用
        scores = result.model_dump() if isinstance(result, ReplanEvaluationResult) else result

        # 计算加权总分
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        # 从错过的重规划时机中提取 LLM 建议
        llm_suggestions = []
        missed = scores.get("missed_replan_opportunities") or []
        if isinstance(missed, list):
            for opp in missed:
                if isinstance(opp, dict) and opp.get("reason"):
                    llm_suggestions.append(opp["reason"])

        return ReplanScore(
            trigger_appropriateness=scores.get("trigger_appropriateness", 0),
            adaptation_quality=scores.get("adaptation_quality", 0),
            learning_from_failure=scores.get("learning_from_failure", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
            llm_suggestions=llm_suggestions,
        )

    def _detect_missed_replans(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """检测本应触发重规划但未触发的情况。"""
        missed = []
        consecutive_failures = 0
        replan_count = 0

        def _is_tool(step, name):
            return step.action_type == "tool_call" and step.action_detail.get("tool_name") == name

        for step in trajectory:
            # 跟踪工具调用观察结果中的连续失败
            if step.action_type == "tool_call":
                obs = (step.observation or "").lower()
                if any(keyword in obs for keyword in ["error", "failed", "not found", "exception"]):
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0

            # 跟踪专用失败事件中的连续失败
            if step.action_type == "failure":
                consecutive_failures += 1

            # 跟踪重规划事件（统一后的 TOOL_CALL + tool_name="replan"）
            if _is_tool(step, "replan"):
                replan_count += 1
                consecutive_failures = 0

            # 检测错过的重规划时机
            if consecutive_failures >= 5 and replan_count == 0:
                missed.append(
                    {
                        "step": step.step_number,
                        "reason": f"Agent had {consecutive_failures} consecutive failures without replanning",
                    }
                )

        return missed

    def _format_trajectory_for_replan(self, trajectory: List[TrajectoryStep]) -> str:
        """格式化轨迹，重点关注与重规划相关的信息。"""
        lines = []
        consecutive_failures = 0

        def _is_tool(step, name):
            return step.action_type == "tool_call" and step.action_detail.get("tool_name") == name

        def _inp(step):
            return step.action_detail.get("input") or {}

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

            elif _is_tool(step, "replan"):
                consecutive_failures = 0
                inp = _inp(step)
                lines.append(f"Step {step.step_number}: REPLAN TRIGGERED")
                lines.append(f"  Reason: {inp.get('reason', 'Not specified')}")
                if inp.get("new_plan"):
                    lines.append(f"  New Plan: {inp['new_plan'][:200]}")

            elif _is_tool(step, "retrieval"):
                inp = _inp(step)
                query = inp.get("query", "")[:100]
                count = inp.get("result_count", 0)
                lines.append(f"Step {step.step_number}: RETRIEVAL query='{query}' -> {count} docs")

            elif _is_tool(step, "evidence"):
                inp = _inp(step)
                etype = inp.get("evidence_type", "")
                lines.append(f"Step {step.step_number}: EVIDENCE [{etype}]")

            elif step.action_type == "think":
                lines.append(f"Step {step.step_number}: THINK - {step.action_detail.get('thought', '')[:150]}")

        return "\n".join(lines)

    def _format_replan_events(self, replan_events: List[Dict[str, Any]]) -> str:
        """格式化重规划事件用于评估。"""
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
        """格式化失败事件用于评估。"""
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
        """将 LLM 响应解析为评分字典。"""
        parsed = self._parse_json_from_llm(content)
        if parsed is not None:
            return parsed

        return {
            "trigger_appropriateness": 50,
            "adaptation_quality": 50,
            "learning_from_failure": 50,
            "feedback": content,
        }
