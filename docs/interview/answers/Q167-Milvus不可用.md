# Q167: Milvus `available: false`，系统状态页显示什么？如何恢复？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q167 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★ |

## 问题

Milvus `available: false`，系统状态页显示什么？如何恢复？

## 参考答案

Q167 与 Milvus unavailable 相关。状态页 BM25-only；恢复 Milvus Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Milvus unavailable：状态页 BM25-only
- 代码入口：app/wiki_agent/agent/tools/search_tools.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Milvus unavailable」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Milvus unavailable？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q166](../answers/Q166-Wiki不引用知识库.md)
- [Q168](../answers/Q168-Dashboard为空.md)
