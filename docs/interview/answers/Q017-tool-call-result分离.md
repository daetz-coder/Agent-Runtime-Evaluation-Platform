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

`tool_call` 和 `tool_result` 分开记录，是为了把“**Agent 想调用什么工具**”和“**工具实际返回了什么**”拆成两个可评估对象。

`tool_call` 主要记录工具名、调用参数、调用时机；`tool_result` 记录返回内容、执行状态、latency 等结果信息。这样 Tool Use Evaluator 才能分别判断：

1. **selection_quality**：工具选得对不对，看 `tool_call`；
2. **parameter_accuracy**：参数传得准不准，看 `tool_call`；
3. **result_utilization**：Agent 有没有正确使用工具返回结果，看 `tool_result` 以及后续回答。

在实现上，`BaseEvaluator._extract_tool_calls` 会按 step 顺序把 `tool_call` 和后面的 `tool_result` 配对。这样可以支持更真实的执行轨迹：例如异步工具调用、多轮工具调用、工具失败、超时，甚至只有 `tool_call` 没有 `tool_result` 的异常情况。

如果把两者合并成一条记录，评估时会丢失很多诊断粒度。比如一次失败到底是“工具选错了”“参数错了”“工具返回异常”，还是“返回结果正确但 Agent 没用好”，就很难区分。因此分离记录能提升 Tool Use 评估的可解释性和错误归因能力。

对于 Callback adapter，通常是：

```
on_tool_start` / 工具调用开始 → `tool_call`
 `on_tool_end` / 工具结束返回 → `tool_result
```

如果轨迹里缺少 `tool_result`，`result_utilization` 往往会被判低，或者 Judge 会给出更保守的评分。



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
