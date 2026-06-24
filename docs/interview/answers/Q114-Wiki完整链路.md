# Q114: Wiki Agent 的完整请求链路：用户提问 → 检索 → 生成 → 可选知识提取，请逐步说明。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q114 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★★ |

## 问题

Wiki Agent 的完整请求链路：用户提问 → 检索 → 生成 → 可选知识提取，请逐步说明。

## 参考答案

问题「Wiki Agent 的完整请求链路：用户提问 → 检索 → 生成 → 可选知识提取，请逐步说明。」考察 Wiki 链路。提问→hybrid_search→LLM respond→可选 extract Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。 首要读 app/wiki_agent/agent/graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Wiki 链路：提问→hybrid_search→LLM respond→可选 extract
- 代码入口：app/wiki_agent/agent/graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Wiki 链路」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Wiki 链路？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q113](../answers/Q113-RAG-ground-truth.md)
- [Q115](../answers/Q115-Chat-SSE.md)
