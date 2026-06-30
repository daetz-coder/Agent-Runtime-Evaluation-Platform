# Q079: selection_quality、parameter_accuracy、result_utilization 分别看什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q079 |
| 分类 | 六维评估器深入 |
| 难度 | ★★ |

## 问题

selection_quality、parameter_accuracy、result_utilization 分别看什么？

## 参考答案

ToolUse 评估器从三个子维度衡量 Agent 的工具使用质量，每个维度 0-100 分，按加权平均计算总分。

**Selection Quality（选择质量，权重 0.40）** 是权重最高的维度，评估 Agent 是否为当前任务选择了最合适的工具（`tool_use_evaluator.py:37-40`）。Prompt 中给出了具体示例：用 `python_execute` 分析数据是好的选择，而用 `bash_execute` 做复杂数学计算则是浪费的。评估器还会关注"是否有更好的工具可用但未被使用"。高分示例：需要读取文件内容时选择 `file_read`，需要执行代码时选择 `python_execute`。低分示例：用 `file_write` 读取文件、用 `bash_execute` 运行 Python 脚本（绕过了沙箱限制）。选择质量之所以权重最高，是因为错误的工具选择会导致后续参数和结果利用全部失效。

**Parameter Accuracy（参数准确性，权重 0.30）** 评估工具调用的参数是否正确和完整（`tool_use_evaluator.py:42-46`）。具体检查点包括：文件路径是否正确、代码语法是否有效、必填参数是否缺失。当工具执行失败时，评估器还会检查 Agent 是否诊断了错误原因并纠正了参数——这体现了 Agent 的错误恢复能力。格式化工具结果时，状态标记为 `SUCCESS` 或 `FAILED`（`tool_use_evaluator.py:184`），LLM 评判时会根据失败记录扣分。

**Result Utilization（结果利用，权重 0.30）** 评估 Agent 是否有效利用了工具返回的结果（`tool_use_evaluator.py:48-52`）。高分示例：读取文件后正确分析了内容，根据搜索结果调整了查询策略。低分示例：调用工具后完全忽略输出、重复调用同一个工具产生相同结果、在失败后过早放弃而不尝试修复。评估器在格式化时会截断输出到 300 字符（`tool_use_evaluator.py:168`），防止过长的输出干扰 LLM 评判。

当轨迹中没有任何工具调用时，该维度设置 `applicable=False` 并从综合评分中剔除（`tool_use_evaluator.py:99-108`），避免对纯推理任务产生不公平的零分。

## 代码依据

- `app/evaluators/tool_use_evaluator.py:17-66` — TOOL_USE_EVALUATION_PROMPT 定义三个维度的评分标准
- `app/evaluators/tool_use_evaluator.py:37-40` — Selection Quality 评估标准：工具选择合理性
- `app/evaluators/tool_use_evaluator.py:42-46` — Parameter Accuracy 评估标准：参数正确性与错误诊断
- `app/evaluators/tool_use_evaluator.py:48-52` — Result Utilization 评估标准：结果利用与迭代改进
- `app/evaluators/tool_use_evaluator.py:72-76` — WEIGHTS 字典：selection 0.40, parameter 0.30, result 0.30
- `app/evaluators/tool_use_evaluator.py:99-108` — 无工具调用时 applicable=False
- `app/evaluators/tool_use_evaluator.py:168` — 工具输出截断至 300 字符
- `app/evaluators/tool_use_evaluator.py:184` — 工具结果标记 SUCCESS/FAILED 状态

## 回答要点

- Selection Quality 权重最高（0.40），工具选错则后续环节全部浪费
- Parameter Accuracy 不仅检查参数正确性，还关注 Agent 的错误恢复能力
- Result Utilization 评估 Agent 是否形成"调用-分析-决策"的闭环，而非机械调用
- 无工具调用时标记 applicable=False 而非打零分，保证对纯推理任务的公平性
- 工具输出截断至 300 字符，避免过长输出干扰 LLM 评判效率

## 常见追问

**Q: 为什么 Selection Quality 权重比其他两个高 0.10？**

A: 工具选择是工具使用的起点。如果 Agent 选错了工具（例如用 `file_write` 读取文件），即使参数正确、结果被充分利用，整体效果也会大打折扣。Selection Quality 设为 0.40 体现了"方向正确比执行到位更重要"的设计理念。

**Q: 如果工具执行失败了，Result Utilization 会直接扣分吗？**

A: 不会直接扣分。评估器关注的是 Agent 在失败后的行为：是否诊断了错误、是否调整了参数重试、是否换用了其他工具。如果 Agent 成功从失败中恢复并最终完成任务，Result Utilization 仍可获得高分。这在 Prompt 中明确提到："Agent 是否在失败后迭代改进，还是过早放弃？"（`tool_use_evaluator.py:52`）

## 相关题目

- [Q072](../answers/Q072-Planning四子维.md)
- [Q080](../answers/Q080-ToolUse无工具调用处理.md)
- [Q090](../answers/Q090-Retrieval三子维.md)
