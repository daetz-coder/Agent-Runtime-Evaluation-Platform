# Q171: 请阅读 `BaseEvaluator._extract_tool_calls`，说明它如何从 trajectory 提取工具调用对。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q171 |
| 分类 | 编码与现场设计题 |
| 难度 | ★★ |

## 问题

请阅读 `BaseEvaluator._extract_tool_calls`，说明它如何从 trajectory 提取工具调用对。

## 参考答案

`_extract_tool_calls` 定义在 `app/evaluators/base.py:159-170`，是一个简洁的列表推导式，从完整的 trajectory 中筛选出所有工具调用步骤并标准化为统一结构。

核心逻辑分两部分：**过滤**和**提取**。

过滤条件是 `step.action_type == "tool_call"`，对应 `ActionType.TOOL_CALL` 常量（action_types.py:16）。这确保只选取实际的工具调用步骤，跳过思考、规划、记忆读写等其他动作类型。

提取阶段将每个匹配步骤映射为一个包含四个标准字段的字典：
- `step`：来自 `step.step_number`，标识该调用在 trajectory 中的序号位置，用于排序和定位。
- `tool`：来自 `step.action_detail.get("tool_name")`，即被调用的工具名称。action_detail 是一个灵活的 dict，tool_name 由上游录制逻辑写入。
- `input`：来自 `step.action_detail.get("input")`，即传给工具的参数。注意这里 key 是 `"input"` 而非 `"tool_input"`，与某些文档描述不同，需以代码为准。
- `output`：来自 `step.observation`，即工具执行后的返回结果。observation 是 TrajectoryStep 的顶层字段，不是嵌套在 action_detail 中的。

与其配对的 `_extract_tool_results`（base.py:198-211）提取 `action_type == ActionType.TOOL_RESULT` 的步骤，返回包含 `success`、`error_type`、`duration_ms` 等字段的字典。两者的分离设计使得上层 evaluator 可以独立分析工具选择质量（call）和工具执行效果（result）。例如 ToolUseEvaluator（tool_use_evaluator.py:78-154）使用 tool_calls 评估 selection_quality 和 parameter_accuracy，使用 tool_results 评估 result_utilization。

这种设计的工程优势在于：BaseEvaluator 负责数据提取的标准化，子类 evaluator 只需调用提取方法并关注评分逻辑，无需重复解析 trajectory 的原始结构。

## 代码依据

- `app/evaluators/base.py:159-170` — `_extract_tool_calls` 实现，列表推导式过滤 TOOL_CALL 并提取四字段
- `app/evaluators/base.py:198-211` — `_extract_tool_results` 实现，提取 TOOL_RESULT 的 success/error_type/duration_ms
- `app/models/action_types.py:16-17` — TOOL_CALL 和 TOOL_RESULT 常量定义
- `app/evaluators/tool_use_evaluator.py:78-154` — ToolUseEvaluator 如何消费 tool_calls 和 tool_results

## 回答要点

- 列表推导式以 `action_type == "tool_call"` 为过滤条件，只选取工具调用步骤
- 提取四个标准字段：step（序号）、tool（工具名）、input（参数）、output（observation）
- tool_name 和 input 从 action_detail dict 中获取，output 从顶层 observation 字段获取
- 配对的 `_extract_tool_results` 提取 success/error_type/duration_ms，与 tool_calls 分离设计
- 分离设计允许 evaluator 独立分析工具选择质量和执行效果

## 常见追问

**Q: 为什么 tool_calls 和 tool_results 要分成两个方法，而不是合并提取？**

A: 因为分析维度不同。tool_calls 关注 "选了什么工具、传了什么参数"（selection_quality, parameter_accuracy），tool_results 关注 "工具执行是否成功、结果是否被利用"（result_utilization）。合并会耦合两个独立的评估视角。此外，并非所有 tool_call 都有对应的 tool_result（如超时、中断场景），分离处理更健壮。

**Q: 如果 trajectory 中 tool_call 和 tool_result 的 step_number 不连续怎么办？**

A: 当前实现不依赖配对关系——tool_calls 和 tool_results 是独立提取的列表。如果需要配对，上层 evaluator 需要根据 step_number 顺序或 tool_name 进行匹配。这是一个潜在的改进点，可以在 BaseEvaluator 中增加 `_pair_calls_with_results` 方法。

## 相关题目

- [Q162](../answers/Q162-Planning低分排查.md)
- [Q175](../answers/Q175-新增Safety维.md)
