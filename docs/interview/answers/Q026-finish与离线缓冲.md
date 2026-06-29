# Q26: SDK 的 `finish(auto_run=True)` 做了什么？离线缓冲是如何实现的？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q026 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★ |

## 问题

SDK 的 `finish(auto_run=True)` 做了什么？离线缓冲是如何实现的？

## 参考答案

Q26 与 finish 与离线缓冲 相关。finish flush 剩余 steps；无 EVAL_API_BASE_URL 时纯内存；失败步骤进 _steps 缓冲 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `sdk/collector.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- finish 与离线缓冲：finish flush 剩余 steps
- 代码入口：sdk/collector.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「finish 与离线缓冲」最先看哪段代码？**

A: 打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 finish 与离线缓冲？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q025](../answers/Q025-两套collector对比.md)
- [Q027](../answers/Q027-EVAL_BATCH_SIZE.md)
