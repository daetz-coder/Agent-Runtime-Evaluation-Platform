# Q119: Wiki 页面的 CRUD 如何触发向量索引同步？删除页面后 Milvus 和 BM25 如何清理？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q119 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★ |

## 问题

Wiki 页面的 CRUD 如何触发向量索引同步？删除页面后 Milvus 和 BM25 如何清理？

## 参考答案

Q119 与 CRUD 索引 相关。删页清理 Milvus+BM25 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/wiki_agent/sync_manager.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- CRUD 索引：删页清理 Milvus+BM25
- 代码入口：app/wiki_agent/sync_manager.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「CRUD 索引」最先看哪段代码？**

A: 打开 app/wiki_agent/sync_manager.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 CRUD 索引？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q118](../answers/Q118-reject提取.md)
- [Q120](../answers/Q120-history-rollback.md)
