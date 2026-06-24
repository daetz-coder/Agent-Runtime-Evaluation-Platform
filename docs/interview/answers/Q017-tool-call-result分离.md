# Q17: `tool_call` 和 `tool_result` 为什么要分开记录？对 Tool Use 评估有什么影响？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q017 |
| 分类 | Agent 架构与设计理念 |
| 难度 | ★★★ |

## 问题

`tool_call` 和 `tool_result` 为什么要分开记录？对 Tool Use 评估有什么影响？

## 参考答案

tool_call 记录工具名与参数，tool_result 独立记录返回体与 latency；BaseEvaluator._extract_tool_calls 按 step 顺序配对。分离原因：异步工具、多步调用、失败时可能只有 call 无 result；Tool Use Evaluator 的 selection_quality/parameter_accuracy 看 call，result_utilization 看 Agent 是否使用 result。轨迹不完整时 utilization 低或 Judge 给保守分。

## 代码依据

- `app/evaluators/base.py`
- `app/evaluators/tool_use_evaluator.py`
- `app/models/action_types.py`

## 回答要点

- call/result 分离支持异步与失败场景
- _extract_tool_calls 顺序配对
- result_utilization 依赖 result 步骤
- 缺 result 是常见数据质量问题

## 常见追问

**Q: 合并成一个行吗？**

A: 会丢失 utilization 与错误归因能力。

**Q: Callback adapter 怎么映射？**

A: on_tool_end→tool_result。

## 相关题目

- [Q016](../answers/Q016-ActionType粒度.md)
- [Q018](../answers/Q018-think-node-decision.md)
