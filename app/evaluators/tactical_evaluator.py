"""
战术决策评估器

评估 Agent 下一步行动决策的质量：
- 相关性 (Relevance)：行动是否与当前状态相关？
- 效率 (Efficiency)：行动是否高效？
- 正确性 (Correctness)：行动是否正确？
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.evaluators.eval_schemas import TacticalEvaluationResult
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

请从以下维度评估 Agent 的战术决策（下一步行动，0-100 分），严格按照锚点评分：

### 1. 相关性 (Relevance, 0-100)
行动是否与当前状态和目标相关？是否朝着目标推进？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 行动与目标完全无关（如目标是修认证 bug，Agent 去优化数据库查询） |
| 25   | 大部分行动偏离目标，仅偶尔碰巧相关（如频繁执行无关的文件搜索） |
| 50   | 约一半行动相关，另一半是无关操作（如分析认证时顺便跑了一次全量测试） |
| 75   | 大部分行动直接推进目标，仅 1-2 步略显多余 |
| 100  | 每一步都直接服务于当前状态和最终目标，零无关操作 |

### 2. 效率 (Efficiency, 0-100)
行动在当前情况下是否高效？是否有不必要的绕路？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 完全低效：大量重复操作、死循环、或用最复杂的方式做简单事 |
| 25   | 明显绕路：做了 3+ 步不必要的中间步骤（如先写完整代码再全部删除重写） |
| 50   | 有效率意识但有 1-2 处明显浪费（如读了不需要的文件、重复查询同一信息） |
| 75   | 整体高效，仅 1 处可优化（如可以用一步完成的事分了两步） |
| 100  | 最短路径执行：每步都是当前最优选择，零冗余操作 |

### 3. 正确性 (Correctness, 0-100)
行动是否在给定上下文中正确？专家会做同样的事吗？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 行动完全错误（如在未理解代码的情况下直接修改、用错误的命令） |
| 25   | 多处行动不正确（≥3 处），如读错文件、用错 API、误解错误信息 |
| 50   | 大致正确但有 1-2 处错误判断（如误读了错误信息导致错误的修复方向） |
| 75   | 行动基本正确，仅 1 处小瑕疵（如修复方向对但方法不是最优） |
| 100  | 每步行动都符合专家判断：先分析再行动、正确解读错误信息、选择最优方案 |

feedback 字段请用中文。problematic_actions 列出有问题的行动（含 step、issue、suggestion）。

{format_instructions}
"""


class TacticalEvaluator(BaseEvaluator):
    """评估 Agent 执行过程中的战术决策质量。"""

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
        评估战术决策质量。

        Args:
            goal: 用户的原始目标
            trajectory: Agent 执行步骤列表
            context: 附加上下文

        Returns:
            包含详细评估结果的 TacticalScore
        """
        if not trajectory:
            return TacticalScore(
                relevance=0,
                efficiency=0,
                correctness=0,
                overall=0,
                feedback="No trajectory steps provided for evaluation.",
            )

        # 提取行动步骤（排除计划步骤）
        actions = self._extract_actions(trajectory)
        current_state = self._determine_current_state(trajectory)

        # 格式化行动步骤用于评估
        actions_text = self._format_actions(actions)

        # 创建提示词 + 结构化输出链
        prompt = ChatPromptTemplate.from_template(TACTICAL_EVALUATION_PROMPT)
        structured_llm = self.llm.with_structured_output(TacticalEvaluationResult)
        chain = prompt | structured_llm

        # 获取 LLM 评估结果（结构化输出 + 重试机制）
        result = await self._invoke_structured_llm(
            chain,
            {
                "goal": goal,
                "current_state": current_state,
                "actions": actions_text,
                "context": context or "No additional context provided.",
                "format_instructions": "",  # PydanticOutputParser 降级时会覆盖
            },
            schema_class=TacticalEvaluationResult,
            max_retries=3,
            prompt=prompt,
        )

        # Pydantic model 直接使用
        scores = result.model_dump() if isinstance(result, TacticalEvaluationResult) else result

        # 计算加权总分
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        # 从有问题的行动中提取 LLM 建议
        llm_suggestions = []
        problematic = scores.get("problematic_actions") or []
        if isinstance(problematic, list):
            for action in problematic:
                if isinstance(action, dict) and action.get("suggestion"):
                    llm_suggestions.append(action["suggestion"])

        return TacticalScore(
            relevance=scores.get("relevance", 0),
            efficiency=scores.get("efficiency", 0),
            correctness=scores.get("correctness", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
            llm_suggestions=llm_suggestions,
        )

    def _extract_actions(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """提取行动步骤（排除计划步骤）。"""
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
        """根据轨迹确定当前状态。"""
        if not trajectory:
            return "Initial state"

        # 查看最近的步骤以确定状态
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
        """将行动步骤格式化为可读文本。"""
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
        """将 LLM 响应解析为评分字典。"""
        parsed = self._parse_json_from_llm(content)
        if parsed is not None:
            return parsed

        return {
            "relevance": 50,
            "efficiency": 50,
            "correctness": 50,
            "feedback": content,
        }
