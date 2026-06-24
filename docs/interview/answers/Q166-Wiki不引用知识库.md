# Q166: Wiki Agent 回答不引用知识库内容，从检索到生成，逐步怎么 debug？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q166 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★ |

## 问题

Wiki Agent 回答不引用知识库内容，从检索到生成，逐步怎么 debug？

## 参考答案

围绕 Wiki 不引用 KB：查 hybrid 结果与 SYSTEM_PROMPT 面试回答应先说业务场景，再落到 app/wiki_agent/agent/graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Wiki 不引用 KB：查 hybrid 结果与 SYSTEM_PROMPT
- 代码入口：app/wiki_agent/agent/graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Wiki 不引用 KB」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Wiki 不引用 KB？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q165](../answers/Q165-benchmark失败定位.md)
- [Q167](../answers/Q167-Milvus不可用.md)
