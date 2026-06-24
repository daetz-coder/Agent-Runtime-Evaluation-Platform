# Q168: 前端 Dashboard 图表为空，可能有哪些原因（数据、API、前端渲染）？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q168 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★ |

## 问题

前端 Dashboard 图表为空，可能有哪些原因（数据、API、前端渲染）？

## 参考答案

问题「前端 Dashboard 图表为空，可能有哪些原因（数据、API、前端渲染）？」考察 Dashboard 空。无数据/API 失败/渲染错误 排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。 首要读 frontend/src/views/Dashboard.vue，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `frontend/src/views/Dashboard.vue`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Dashboard 空：无数据/API 失败/渲染错误
- 代码入口：frontend/src/views/Dashboard.vue
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Dashboard 空」最先看哪段代码？**

A: 打开 frontend/src/views/Dashboard.vue，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Dashboard 空？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q167](../answers/Q167-Milvus不可用.md)
- [Q169](../answers/Q169-SSE断开恢复.md)
