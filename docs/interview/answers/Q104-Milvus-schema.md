# Q104: Milvus collection schema 如何设计？有哪些字段（path、chunk、title、embedding）？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q104 |
| 分类 | RAG 与检索质量 |
| 难度 | ★ |

## 问题

Milvus collection schema 如何设计？有哪些字段（path、chunk、title、embedding）？

## 参考答案

Q104 与 Milvus schema 相关。path/chunk/title/embedding 字段 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/wiki_agent/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Milvus schema：path/chunk/title/embedding 字段
- 代码入口：app/wiki_agent/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Milvus schema」最先看哪段代码？**

A: 打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Milvus schema？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q103](../answers/Q103-零向量降级.md)
- [Q105](../answers/Q105-Milvus降级BM25.md)
