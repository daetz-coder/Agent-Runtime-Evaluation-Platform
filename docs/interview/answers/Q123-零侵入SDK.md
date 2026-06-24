# Q123: 「零侵入 SDK 接入」的具体含义是什么？开发者最少需要改几行代码？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q123 |
| 分类 | SDK 与零侵入接入 |
| 难度 | ★★ |

## 问题

「零侵入 SDK 接入」的具体含义是什么？开发者最少需要改几行代码？

## 参考答案

问题「「零侵入 SDK 接入」的具体含义是什么？开发者最少需要改几行代码？」考察 零侵入 SDK。import adapter 包装即可；最少数行 sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。 首要读 sdk/collector.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `sdk/collector.py`
- `sdk/adapters/langgraph.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- 零侵入 SDK：import adapter 包装即可
- 代码入口：sdk/collector.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「零侵入 SDK」最先看哪段代码？**

A: 打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 零侵入 SDK？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q122](../answers/Q122-EVAL_AUTO_RUN.md)
- [Q124](../answers/Q124-adapter路径.md)
