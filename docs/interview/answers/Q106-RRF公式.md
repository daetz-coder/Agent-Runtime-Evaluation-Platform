# Q106: 请解释 RRF（Reciprocal Rank Fusion）公式，k=60 的含义是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q106 |
| 分类 | RAG 与检索质量 |
| 难度 | ★★★ |

## 问题

请解释 RRF（Reciprocal Rank Fusion）公式，k=60 的含义是什么？

## 参考答案

围绕 RRF k=60：score+=1/(k+rank+1)；k=60 平滑秩次 面试回答应先说业务场景，再落到 app/wiki_agent/agent/tools/search_tools.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- RRF k=60：score+=1/(k+rank+1)
- 代码入口：app/wiki_agent/agent/tools/search_tools.py
- RRF: 1/(k+rank+1)
- k=60 在 search_tools.py
- semantic 与 BM25 各取 limit*2

## 常见追问

**Q: 「RRF k=60」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 RRF k=60？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q105](../answers/Q105-Milvus降级BM25.md)
- [Q107](../answers/Q107-RRF-vs加权.md)
