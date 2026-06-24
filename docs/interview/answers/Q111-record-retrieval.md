# Q111: Wiki Agent search 节点如何 `record_retrieval`？数据如何流到 RetrievalEvaluator？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q111 |
| 分类 | RAG 与检索质量 |
| 难度 | ★ |

## 问题

Wiki Agent search 节点如何 `record_retrieval`？数据如何流到 RetrievalEvaluator？

## 参考答案

问题「Wiki Agent search 节点如何 `record_retrieval`？数据如何流到 RetrievalEvaluator？」考察 record_retrieval。search 后写入 retrieval 步骤 Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。 首要读 app/wiki_agent/evaluation.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/wiki_agent/evaluation.py`
- `app/wiki_agent/agent/graph.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- record_retrieval：search 后写入 retrieval 步骤
- 代码入口：app/wiki_agent/evaluation.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「record_retrieval」最先看哪段代码？**

A: 打开 app/wiki_agent/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 record_retrieval？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q110](../answers/Q110-top-k调参.md)
- [Q112](../answers/Q112-检索好生成差.md)
