# Q159: `EVAL_WEBHOOK_URL` 通知机制的安全考虑？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q159 |
| 分类 | 系统设计与生产化 |
| 难度 | ★ |

## 问题

`EVAL_WEBHOOK_URL` 通知机制的安全考虑？

## 参考答案

问题「`EVAL_WEBHOOK_URL` 通知机制的安全考虑？」考察 WEBHOOK 安全。EVAL_WEBHOOK_URL HMAC 签名 当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。 首要读 app/core/config.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/core/config.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- WEBHOOK 安全：EVAL_WEBHOOK_URL HMAC 签名
- 代码入口：app/core/config.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「WEBHOOK 安全」最先看哪段代码？**

A: 打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 WEBHOOK 安全？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q158](../answers/Q158-Wiki-XSS.md)
- [Q160](../answers/Q160-平台观测.md)
