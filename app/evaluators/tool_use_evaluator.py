"""
Tool Use Evaluator

Evaluates the quality of tool selection and usage:
- Selection Quality: Was the right tool chosen?
- Parameter Accuracy: Were the parameters correct?
- Result Utilization: Were tool results used effectively?
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

请从以下维度评估 Agent 的工具使用（0-100 分）：

1. **选择质量** (Selection Quality, 0-100):
   - 是否为任务选择了正确的工具？
   - 例如：用 `python_execute` 分析数据是好的；用 `bash_execute` 做复杂数学计算是浪费的。
   - 考虑：是否有更好的工具可用但未被使用？

2. **参数准确性** (Parameter Accuracy, 0-100):
   - 工具参数是否正确和完整？
   - 例如：正确的文件路径、合适的代码语法
   - 考虑：是否因参数错误导致执行失败？
   - 如果工具执行失败，检查 Agent 是否诊断并纠正了问题。

3. **结果利用** (Result Utilization, 0-100):
   - 工具结果是否被有效利用？
   - Agent 是否根据收到的信息采取了行动？
   - 例如：读取文件后是否正确分析了内容？
   - Agent 是否在失败后迭代改进，还是过早放弃？

## 输出格式
返回 JSON 对象，feedback 字段请用中文：
{{
    "selection_quality": <分数>,
    "parameter_accuracy": <分数>,
    "result_utilization": <分数>,
    "overall": <加权平均>,
    "feedback": "<详细评估反馈（中文）>",
    "inefficient_calls": [
        {{"tool": "<工具名>", "issue": "<问题描述>", "suggestion": "<改进建议>"}}
    ]
}}
"""


class ToolUseEvaluator(BaseEvaluator):
    """Evaluates tool usage quality of agent execution."""

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
        Evaluate tool usage quality.

        Args:
            goal: The original goal/objective
            trajectory: List of agent execution steps
            context: Additional context

        Returns:
            ToolUseScore with detailed evaluation
        """
        # Extract tool calls and tool results from trajectory
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

        # Format tool calls for evaluation (including tool results)
        tool_calls_text = self._format_tool_calls(tool_calls)

        # Format execution results from trajectory (real sandbox results)
        execution_results_text = "No tool results recorded"
        if tool_results:
            execution_results_text = self._format_tool_results(tool_results)

        # Create prompt + structured output chain
        prompt = ChatPromptTemplate.from_template(TOOL_USE_EVALUATION_PROMPT)
        structured_llm = self.llm.with_structured_output(ToolUseEvaluationResult)
        chain = prompt | structured_llm

        # Get LLM evaluation (with structured output + retry)
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

        # Calculate weighted overall score
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        # Extract LLM suggestions from inefficient_calls
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
        """Format tool calls into readable text."""
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
        """Format tool results into readable text."""
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

    def _parse_scores(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into scores dictionary."""
        parsed = self._parse_json_from_llm(content)
        if parsed is not None:
            return parsed

        return {
            "selection_quality": 50,
            "parameter_accuracy": 50,
            "result_utilization": 50,
            "feedback": content,
        }
