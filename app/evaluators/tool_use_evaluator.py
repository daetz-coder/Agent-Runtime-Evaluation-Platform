"""
工具使用评估器

评估 Agent 工具选择和使用的质量：
- 选择质量 (Selection Quality)：是否选择了正确的工具？
- 参数准确性 (Parameter Accuracy)：工具参数是否正确？
- 结果利用 (Result Utilization)：工具结果是否被有效利用？
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.evaluators.eval_schemas import ToolUseEvaluationResult
from app.models.schemas import ToolUseScore, TrajectoryStep

TOOL_USE_EVALUATION_PROMPT = """你必须用中文输出所有内容（包括 feedback、inefficient_calls）。你是一位 AI Agent 工具使用评估专家。

## 用户目标
{goal}

## 工具调用记录
{tool_calls}

## 上下文
{context}

## 执行结果
以下工具结果来自沙箱环境的真实执行，反映 Agent 运行每个工具时的实际输出。

{execution_results}

## 评估标准

请从以下维度评估 Agent 的工具使用（0-100 分），严格按照锚点评分：

### 1. 选择质量 (Selection Quality, 0-100)
是否为任务选择了正确的工具？是否有更好的工具可用但未被使用？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 完全选错工具（如用文件搜索工具执行代码、用计算器读取文件） |
| 25   | 频繁选错工具（≥3 次），或大量使用低效工具替代专用工具 |
| 50   | 工具选择大致正确，但有 1-2 次次优选择（如用 bash 做本可用专用工具完成的事） |
| 75   | 工具选择基本最优，仅 1 次可改进（如用了通用工具但专用工具更快） |
| 100  | 每次都选择了最合适的工具，充分利用了可用工具集 |

### 2. 参数准确性 (Parameter Accuracy, 0-100)
工具参数是否正确和完整？是否因参数错误导致执行失败？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 参数完全错误：路径不存在、语法错误、格式错误，导致所有工具调用失败 |
| 25   | 大部分参数有误（≥3 次），Agent 未诊断错误原因，反复用错误参数重试 |
| 50   | 有 1-2 次参数错误，但 Agent 在失败后能诊断并纠正 |
| 75   | 参数基本正确，仅 1 次小错误（如路径多了一层目录），快速自行修复 |
| 100  | 所有参数一次正确：路径精确、语法正确、格式匹配、无拼写错误 |

### 3. 结果利用 (Result Utilization, 0-100)
工具结果是否被有效利用？Agent 是否根据收到的信息采取了行动？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 完全忽略工具返回的结果，或误解结果导致错误的后续行动 |
| 25   | 大部分结果未被利用（如读取了文件但未分析内容、获取了数据但未使用） |
| 50   | 利用了部分结果，但有 1-2 次信息浪费（如获取了错误详情但未据此调整策略） |
| 75   | 大部分结果被有效利用，仅 1 次未充分利用（如看到了线索但未深挖） |
| 100  | 每次工具结果都被充分利用：读取后分析、失败后诊断、数据驱动后续决策 |

## 输出要求
请直接调用 output 函数返回评估结果。feedback 字段请用中文。
"""


class ToolUseEvaluator(BaseEvaluator):
    """评估 Agent 执行过程中的工具使用质量。"""

    WEIGHTS = {
        "selection_quality": 0.40,
        "parameter_accuracy": 0.30,
        "result_utilization": 0.30,
    }

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolUseScore:
        """
        评估工具使用质量。

        Args:
            goal: 用户的原始目标
            trajectory: Agent 执行步骤列表
            context: 附加上下文

        Returns:
            包含详细评估结果的 ToolUseScore
        """
        # 从轨迹中提取工具调用和工具结果
        tool_calls = self._extract_tool_calls(trajectory)
        tool_results = self._extract_tool_results(trajectory)

        if not tool_calls:
            return ToolUseScore(
                applicable=False,
                not_applicable_reason="轨迹中未包含工具调用，该维度已从综合评分中剔除。",
                selection_quality=0,
                parameter_accuracy=0,
                result_utilization=0,
                overall=0,
                feedback="不适用：轨迹中没有工具调用记录。",
            )

        # 格式化工具调用用于评估（包含工具结果）
        tool_calls_text = self._format_tool_calls(tool_calls)

        # 格式化轨迹中的执行结果（真实沙箱执行结果）
        execution_results_text = "No tool results recorded"
        if tool_results:
            execution_results_text = self._format_tool_results(tool_results)

        # 创建提示词 + 结构化输出链
        prompt = ChatPromptTemplate.from_template(TOOL_USE_EVALUATION_PROMPT)
        structured_llm = self.llm.with_structured_output(ToolUseEvaluationResult)
        chain = prompt | structured_llm

        # 获取 LLM 评估结果（结构化输出 + 重试机制）
        result = await self._invoke_structured_llm(
            chain,
            {
                "goal": goal,
                "tool_calls": tool_calls_text,
                "context": context or "No additional context provided.",
                "execution_results": execution_results_text,
            },
            schema_class=ToolUseEvaluationResult,
            max_retries=3,
        )

        # Pydantic model 直接使用
        scores = result.model_dump() if isinstance(result, ToolUseEvaluationResult) else result

        # 计算加权总分
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        # 从低效调用中提取 LLM 建议
        llm_suggestions = []
        inefficient = scores.get("inefficient_calls") or []
        if isinstance(inefficient, list):
            for call in inefficient:
                if isinstance(call, dict) and call.get("suggestion"):
                    llm_suggestions.append(call["suggestion"])

        return ToolUseScore(
            selection_quality=scores.get("selection_quality", 0),
            parameter_accuracy=scores.get("parameter_accuracy", 0),
            result_utilization=scores.get("result_utilization", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
            llm_suggestions=llm_suggestions,
        )

    def _format_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> str:
        """将工具调用格式化为可读文本。"""
        lines = []
        for call in tool_calls:
            step = call.get("step", "?")
            tool = call.get("tool", "unknown")
            inp = call.get("input", {})
            output = call.get("output", "No output recorded")

            lines.append(f"Step {step}:")
            lines.append(f"  Tool: {tool}")
            lines.append(f"  Input: {inp}")
            lines.append(f"  Output: {output[:300] if output else 'None'}")
            lines.append("")

        return "\n".join(lines)

    def _format_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        """将工具执行结果格式化为可读文本。"""
        lines = []
        for result in tool_results:
            step = result.get("step", "?")
            tool = result.get("tool_name", "unknown")
            success = result.get("success", True)
            duration = result.get("duration_ms")
            error = result.get("error_type")
            output = result.get("output", "No output")

            status = "SUCCESS" if success else f"FAILED ({error})"
            duration_str = f" ({duration:.0f}ms)" if duration else ""
            lines.append(f"Step {step}: {tool} -> {status}{duration_str}")
            if output:
                lines.append(f"  Output: {str(output)[:300]}")
            lines.append("")

        return "\n".join(lines) if lines else "No tool results recorded"
