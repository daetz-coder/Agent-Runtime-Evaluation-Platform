# Q27: `EVAL_BATCH_SIZE` 批量上报的设计考虑是什么？太小或太大有什么影响？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q027 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★ |

## 问题

`EVAL_BATCH_SIZE` 批量上报的设计考虑是什么？太小或太大有什么影响？

## 参考答案

问题「`EVAL_BATCH_SIZE` 批量上报的设计考虑是什么？太小或太大有什么影响？」考察 EVAL_BATCH_SIZE。默认 10；过小 HTTP 开销大，过大丢 batch 风险增 轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。 首要读 app/core/config.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/core/config.py`
- `sdk/collector.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- EVAL_BATCH_SIZE：默认 10
- 代码入口：app/core/config.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「EVAL_BATCH_SIZE」最先看哪段代码？**

A: 打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 EVAL_BATCH_SIZE？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q026](../answers/Q026-finish与离线缓冲.md)
- [Q028](../answers/Q028-上报失败重试.md)
