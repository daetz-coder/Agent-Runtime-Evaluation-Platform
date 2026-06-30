# Q017: `tool_call` 和 `tool_result` 为什么要分开记录？对 Tool Use 评估有什么影响？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q017 |
| 分类 | Agent 架构与设计理念 |
| 难度 | ★★★ |

## 问题

`tool_call` 和 `tool_result` 为什么要分开记录？对 Tool Use 评估有什么影响？

## 参考答案

在本平台的轨迹数据模型中，工具调用被拆分为两个独立的 `ActionType` 常量：`TOOL_CALL` 和 `TOOL_RESULT`（定义于 `app/models/action_types.py:16-17`）。这种分离并非冗余设计，而是支撑评估器对工具使用质量进行多维度细粒度评估的核心基础。

**1. 支撑独立子维度评估**

`ToolUseEvaluator`（`app/evaluators/tool_use_evaluator.py:69`）将工具使用质量拆分为三个子维度：`selection_quality`（选择质量，权重 40%）、`parameter_accuracy`（参数准确性，权重 30%）和 `result_utilization`（结果利用，权重 30%）。这三个子维度的数据来源不同：

- `selection_quality` 和 `parameter_accuracy` 主要依赖 `tool_call` 记录——评估器通过 `_extract_tool_calls`（`app/evaluators/base.py:159-170`）提取工具名、输入参数等信息，判断 Agent 是否选对了工具、参数是否正确。
- `result_utilization` 则需要 `tool_result` 记录——评估器通过 `_extract_tool_results`（`app/evaluators/base.py:198-211`）提取执行成功/失败状态、输出内容，结合后续 actions 判断 Agent 是否有效利用了工具返回。

如果将两者合并为一条记录，评估器无法独立解析"调用了什么"和"结果是什么"，子维度评估的信噪比会显著降低。

**2. 检测不匹配轨迹（Orphaned Calls）**

分离记录使得评估器能够检测异常轨迹模式。例如，如果轨迹中存在 `tool_call` 但缺少对应的 `tool_result`，说明工具执行可能超时、进程崩溃或网络中断。`ToolUseEvaluator` 在 `evaluate()` 方法中（第 96-97 行）分别提取两者：

```python
tool_calls = self._extract_tool_calls(trajectory)
tool_results = self._extract_tool_results(trajectory)
```

当 `tool_results` 为空但 `tool_calls` 非空时，第 114 行会回退到 `"No tool results recorded"`，LLM 评估时会看到工具调用没有结果，从而在 `result_utilization` 维度给出低分。这种检测能力在合并记录的方案中无法实现。

**3. 支撑性能分析**

`tool_result` 独立携带 `duration_ms` 字段（`app/evaluators/base.py:206`），记录工具实际执行耗时。`_format_tool_results`（`app/evaluators/tool_use_evaluator.py:173-191`）在格式化时会展示耗时信息（第 186 行：`f" ({duration:.0f}ms)"`），供 LLM 评估 Agent 是否使用了低效工具。如果耗时信息嵌入 `tool_call`，语义上会产生歧义——调用请求本身不耗时，耗时发生在执行阶段。

**4. 成功/失败状态追踪**

`tool_result` 的 `success` 字段（`app/evaluators/base.py:204`）和 `error_type` 字段（第 205 行）独立记录工具执行的成败。`_format_tool_results` 在格式化时明确标记 `SUCCESS` 或 `FAILED`（第 184 行），让 LLM 评估器能区分"Agent 选对了工具但执行失败"和"Agent 选错了工具"——这是两种完全不同的失败模式，改进策略也不同。

**5. SDK 层面的双写实现**

在 SDK 收集器中，`record_tool_call`（`sdk/collector.py:462-473`）和 `record_tool_result`（`sdk/collector.py:475-492`）是两个独立方法，分别记录调用意图和执行结果。LangChain 回调适配器的 `on_tool_end`（`sdk/adapters/callback.py:184-213`）在工具执行完成时会**同时**写入两条记录——先调用 `record_tool_call`（第 200-205 行），再调用 `record_tool_result`（第 208-213 行）。这种双写确保了轨迹数据的完整性。

**6. 真实场景中的不完整性**

实际生产环境中，`tool_call` 和 `tool_result` 经常不配对。网络超时、Agent 进程崩溃、沙箱执行异常等都可能导致只有 `tool_call` 没有 `tool_result`。分离设计使得评估器能优雅降级——即使缺少 `tool_result`，仍可从 `tool_call` 评估 `selection_quality` 和 `parameter_accuracy`，只是 `result_utilization` 会受影响（详见 Q036）。

## 代码依据

- `app/models/action_types.py:16-17` — `TOOL_CALL` 和 `TOOL_RESULT` 作为独立常量定义
- `app/evaluators/base.py:159-170` — `_extract_tool_calls` 按 `action_type == "tool_call"` 过滤
- `app/evaluators/base.py:198-211` — `_extract_tool_results` 按 `action_type == "tool_result"` 过滤，提取 `success`、`error_type`、`duration_ms`
- `app/evaluators/tool_use_evaluator.py:96-97` — `evaluate()` 分别提取 tool_calls 和 tool_results
- `app/evaluators/tool_use_evaluator.py:156-171` — `_format_tool_calls` 格式化 step/tool/input/output
- `app/evaluators/tool_use_evaluator.py:173-191` — `_format_tool_results` 格式化 step/tool_name/SUCCESS|FAILED/duration_ms
- `sdk/collector.py:462-473` — `record_tool_call` 记录工具名、输入、输出、耗时
- `sdk/collector.py:475-492` — `record_tool_result` 记录工具名、输出、耗时、成功标志、错误类型
- `sdk/adapters/callback.py:184-213` — `on_tool_end` 同时写入 `record_tool_call` 和 `record_tool_result`

## 回答要点

- `tool_call` 和 `tool_result` 是两个独立的 `ActionType`，分别记录调用意图和执行结果
- 分离设计支撑 `ToolUseEvaluator` 的三个独立子维度：`selection_quality`（来自 tool_call）、`parameter_accuracy`（来自 tool_call）、`result_utilization`（来自 tool_result + 后续 actions）
- `tool_result` 独立携带 `success`、`error_type`、`duration_ms` 等执行阶段元数据，语义上属于执行结果而非调用意图
- 分离使得评估器能检测不匹配轨迹（orphaned tool_call without tool_result），优雅降级而非崩溃
- SDK 的 `on_tool_end` 回调会双写两条记录，确保轨迹完整性
- 真实生产环境中两者经常不配对（超时、崩溃），分离设计使评估器仍可从 tool_call 维度给出部分评分

## 常见追问

**Q: 双写不会增加存储开销吗？**

A: 会，但开销很小。每条轨迹记录只有几百字节（工具名、输入摘要、输出摘要），即使一次 Agent 运行产生 50 次工具调用，额外的 50 条 tool_result 记录也不到 50KB。相比评估精度的提升，这个存储成本可以忽略。而且 SDK 的 `_short` 函数（`sdk/collector.py:90-99`）会截断超长字段到 4000 字符，进一步控制体积。

**Q: 如果 Agent 框架不区分 call 和 result（如某些 ReAct 实现），怎么处理？**

A: SDK 提供了适配层。LangGraph 适配器的 `_extract_tool_calls`（`sdk/adapters/langgraph.py:263-301`）会扫描 AIMessage 中的 tool_calls 并分别记录 `TOOL_DECISION` 和 `TOOL_CALL`。对于完全不区分的框架，可以在回调层将单条记录拆分为两条——`on_tool_end`（`sdk/adapters/callback.py:184-213`）就是这种模式的典型实现。

**Q: `result_utilization` 子维度如何评估？它依赖哪些后续 actions？**

A: LLM 评估 prompt（`app/evaluators/tool_use_evaluator.py:48-52`）会询问"工具结果是否被有效利用"、"Agent 是否根据收到的信息采取了行动"。评估器将 `_format_tool_calls`（含 output 摘要）和 `_format_tool_results`（含 SUCCESS/FAILED 状态）一起传给 LLM，由 LLM 判断 Agent 在获得工具结果后是否做出了合理的后续行动。

## 相关题目

- [Q036](../answers/Q036-轨迹不完整.md)
- [Q079](../answers/Q079-评估器applicable机制.md)
