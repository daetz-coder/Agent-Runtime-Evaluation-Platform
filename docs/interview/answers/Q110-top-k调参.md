# Q110: hybrid_search 的 top_k 如何选？召回率和精度的 trade-off 如何调？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q110 |
| 分类 | RAG 与检索质量 |
| 难度 | ★ |

## 问题

hybrid_search 的 top_k 如何选？召回率和精度的 trade-off 如何调？

## 参考答案

Q110 与 top_k 相关。limit*2 召回再 RRF 截断 limit Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- top_k：limit*2 召回再 RRF 截断 limit
- 代码入口：app/wiki_agent/agent/tools/search_tools.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「top_k」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 top_k？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q109](../answers/Q109-path去重.md)
- [Q111](../answers/Q111-record-retrieval.md)
