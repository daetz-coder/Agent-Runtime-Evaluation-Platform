# Q105: Milvus 不可用时 semantic search 降级为 BM25——用户体验上如何感知？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q105 |
| 分类 | RAG 与检索质量 |
| 难度 | ★ |

## 问题

Milvus 不可用时 semantic search 降级为 BM25——用户体验上如何感知？

## 参考答案

问题「Milvus 不可用时 semantic search 降级为 BM25——用户体验上如何感知？」考察 Milvus 降级 BM25。available false 时仅 keyword_search Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。 首要读 app/wiki_agent/agent/tools/search_tools.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Milvus 降级 BM25：available false 时仅 keyword_search
- 代码入口：app/wiki_agent/agent/tools/search_tools.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Milvus 降级 BM25」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Milvus 降级 BM25？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q104](../answers/Q104-Milvus-schema.md)
- [Q106](../answers/Q106-RRF公式.md)
