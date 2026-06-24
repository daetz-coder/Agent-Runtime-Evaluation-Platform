# Q113: RAG 评估中，ground truth 从哪里来？本项目有没有标注数据集？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q113 |
| 分类 | RAG 与检索质量 |
| 难度 | ★ |

## 问题

RAG 评估中，ground truth 从哪里来？本项目有没有标注数据集？

## 参考答案

Q113 与 RAG ground truth 相关。合成轨迹+人工 spot；无大规模标注集 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/benchmarks/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- RAG ground truth：合成轨迹+人工 spot
- 代码入口：app/benchmarks/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「RAG ground truth」最先看哪段代码？**

A: 打开 app/benchmarks/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 RAG ground truth？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q112](../answers/Q112-检索好生成差.md)
- [Q114](../answers/Q114-Wiki完整链路.md)
