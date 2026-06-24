# Q170: JSON.parse 错误（如系统设置页 `/health` 返回 HTML）——根因和修复思路？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q170 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★ |

## 问题

JSON.parse 错误（如系统设置页 `/health` 返回 HTML）——根因和修复思路？

## 参考答案

Q170 与 JSON parse HTML 相关。proxy 错配返回 HTML；fix vite proxy Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `frontend/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- JSON parse HTML：proxy 错配返回 HTML
- 代码入口：frontend/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「JSON parse HTML」最先看哪段代码？**

A: 打开 frontend/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 JSON parse HTML？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q169](../answers/Q169-SSE断开恢复.md)
- [Q171](../answers/Q171-extract-tool-calls.md)
