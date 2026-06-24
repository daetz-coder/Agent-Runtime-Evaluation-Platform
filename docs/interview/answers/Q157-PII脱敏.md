# Q157: trajectory 里可能包含用户 PII 或 API Key，平台如何脱敏？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q157 |
| 分类 | 系统设计与生产化 |
| 难度 | ★ |

## 问题

trajectory 里可能包含用户 PII 或 API Key，平台如何脱敏？

## 参考答案

围绕 PII 脱敏：_short+regex Redact；存储加密 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `sdk/collector.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- PII 脱敏：_short+regex Redact
- 代码入口：sdk/collector.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「PII 脱敏」最先看哪段代码？**

A: 打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 PII 脱敏？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q156](../answers/Q156-评估幂等.md)
- [Q158](../answers/Q158-Wiki-XSS.md)
