# Q33: LLM Proxy adapter 的「幂等包装」是什么意思？为什么需要 idempotent？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q033 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★ |

## 问题

LLM Proxy adapter 的「幂等包装」是什么意思？为什么需要 idempotent？

## 参考答案

问题「LLM Proxy adapter 的「幂等包装」是什么意思？为什么需要 idempotent？」考察 LLM Proxy 幂等。idempotent 防重复 record 同一 call_id；_seen_events 去重 轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。 首要读 sdk/adapters/llm_proxy.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `sdk/adapters/llm_proxy.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- LLM Proxy 幂等：idempotent 防重复 record 同一 call_id
- 代码入口：sdk/adapters/llm_proxy.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「LLM Proxy 幂等」最先看哪段代码？**

A: 打开 sdk/adapters/llm_proxy.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 LLM Proxy 幂等？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q032](../answers/Q032-Callback映射.md)
- [Q034](../answers/Q034-手动collector上报.md)
