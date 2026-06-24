# Q18: `think`、`node_execute`、`tool_decision` 分别记录什么？在什么场景下会用到？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q018 |
| 分类 | Agent 架构与设计理念 |
| 难度 | ★ |

## 问题

`think`、`node_execute`、`tool_decision` 分别记录什么？在什么场景下会用到？

## 参考答案

think 记录推理链（action_detail.thought）；node_execute 记录 LangGraph 节点进出（adapter 包装）；tool_decision 记录 LLM 选择工具的决策理由。Tactical Evaluator 评估除 plan 外动作；Replan 格式化时包含 think。Wiki graph 各节点经 instrument 或 EvaluationTrace.record_node 上报 node_execute。

## 代码依据

- `app/models/action_types.py`
- `sdk/adapters/langgraph.py`
- `app/evaluators/tactical_evaluator.py`

## 回答要点

- think：显式 CoT
- node_execute：图节点边界
- tool_decision：选型理由
- Tactical 含这些非 plan 动作

## 常见追问

**Q: think 和 plan 区别？**

A: plan 是结构化里程碑，think 是中间推理。

**Q: 必须录 think 吗？**

A: 可选，但有助于 Tactical 解释性。

## 相关题目

- [Q017](../answers/Q017-tool-call-result分离.md)
- [Q019](../answers/Q019-evidence与retrieval.md)
