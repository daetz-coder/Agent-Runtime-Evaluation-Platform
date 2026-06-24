# Q16: `ActionType` 定义了 14 种动作类型（plan、tool_call、retrieval、evidence 等），为什么要这么细？能否合并成更少的类型？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q016 |
| 分类 | Agent 架构与设计理念 |
| 难度 | ★ |

## 问题

`ActionType` 定义了 14 种动作类型（plan、tool_call、retrieval、evidence 等），为什么要这么细？能否合并成更少的类型？

## 参考答案

ActionType 14 种在 app/models/action_types.py：plan/plan_update/tool_call/tool_result/memory_write/memory_read/state_change/think/replan/failure/node_execute/tool_decision/retrieval/evidence。细分是为让各 Evaluator _extract_* 精确过滤：Planning 看 plan，Tool Use 配对 tool_call+tool_result，Retrieval 看 retrieval 的 retrieved_docs。合并会损失诊断粒度，例如 tool_call 与 tool_result 分离才能评 result_utilization。

>14 种 ActionType 的设计，是为了把 Agent 的运行过程结构化成可评估的信号。它们和六维 Evaluator 是一一对应的输入契约。类型太少会降低埋点复杂度，但会损失诊断粒度；类型太多又会增加接入成本。因此 14 种是一个折中：足够覆盖 Planning、Tool Use、Memory、Replan、Retrieval 等关键能力，同时又不会复杂到难以接入

## 代码依据

- `app/models/action_types.py`
- `app/evaluators/base.py`
- `app/evaluators/tool_use_evaluator.py`

## 回答要点

- 14 类型映射六维评估输入
- ALL_TYPES 集合用于校验
- SDK 与平台常量需同步
- 过粗合并损害 Tool/Retrieval 评估

## 常见追问

**Q: 能只用 5 种吗？**

A: Memory/Replan 等维会无法评估。

**Q: unknown 类型呢？**

A: validate 或 Evaluator 忽略，可能降分。

## 相关题目

- [Q015](../answers/Q015-分布式轨迹汇聚.md)
- [Q017](../answers/Q017-tool-call-result分离.md)
