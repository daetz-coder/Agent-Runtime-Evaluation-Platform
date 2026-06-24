# Q143: 为什么轨迹推送时任务保持 PENDING，评估开始才 RUNNING？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q143 |
| 分类 | 后端工程与 API 设计 |
| 难度 | ★ |

## 问题

为什么轨迹推送时任务保持 PENDING，评估开始才 RUNNING？

## 参考答案

Q143 与 PENDING vs RUNNING 相关。推轨迹仍 PENDING；评估开始 RUNNING Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/services/evaluation_service.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- PENDING vs RUNNING：推轨迹仍 PENDING
- 代码入口：app/services/evaluation_service.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「PENDING vs RUNNING」最先看哪段代码？**

A: 打开 app/services/evaluation_service.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 PENDING vs RUNNING？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q142](../answers/Q142-任务状态机.md)
- [Q144](../answers/Q144-async-session.md)
