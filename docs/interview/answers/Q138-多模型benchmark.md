# Q138: 多模型 benchmark（`benchmark_multimodel.py`）结论是什么？不同 Judge 模型排序是否一致？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q138 |
| 分类 | Benchmark 与评估校准 |
| 难度 | ★ |

## 问题

多模型 benchmark（`benchmark_multimodel.py`）结论是什么？不同 Judge 模型排序是否一致？

## 参考答案

问题「多模型 benchmark（`benchmark_multimodel.py`）结论是什么？不同 Judge 模型排序是否一致？」考察 benchmark_multimodel。多 Judge 模型排序一致性 monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。 首要读 app/benchmarks/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/benchmarks/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- benchmark_multimodel：多 Judge 模型排序一致性
- 代码入口：app/benchmarks/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「benchmark_multimodel」最先看哪段代码？**

A: 打开 app/benchmarks/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 benchmark_multimodel？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q137](../answers/Q137-评估准确率.md)
- [Q139](../answers/Q139-POST-evaluations-202.md)
