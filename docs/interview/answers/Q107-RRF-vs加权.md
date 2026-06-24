# Q107: 为什么用 RRF 而不是加权分数融合（如 0.7×semantic + 0.3×BM25）？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q107 |
| 分类 | RAG 与检索质量 |
| 难度 | ★ |

## 问题

为什么用 RRF 而不是加权分数融合（如 0.7×semantic + 0.3×BM25）？

## 参考答案

Q107 与 RRF vs 加权 相关。RRF 无分数标定问题；不同量纲融合 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- RRF vs 加权：RRF 无分数标定问题
- 代码入口：app/wiki_agent/agent/tools/search_tools.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「RRF vs 加权」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 RRF vs 加权？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q106](../answers/Q106-RRF公式.md)
- [Q108](../answers/Q108-jieba-BM25.md)
