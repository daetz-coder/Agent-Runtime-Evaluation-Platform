# Q141: 已完成评估的 SSE replay 为什么不重跑 LLM？如何实现？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q141 |
| 分类 | 后端工程与 API 设计 |
| 难度 | ★ |

## 问题

已完成评估的 SSE replay 为什么不重跑 LLM？如何实现？

## 参考答案

问题「已完成评估的 SSE replay 为什么不重跑 LLM？如何实现？」考察 SSE replay。已完成评估重放缓存结果不重跑 LLM FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。 首要读 app/api/v1/endpoints/evaluation.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/api/v1/endpoints/evaluation.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- SSE replay：已完成评估重放缓存结果不重跑 LLM
- 代码入口：app/api/v1/endpoints/evaluation.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「SSE replay」最先看哪段代码？**

A: 打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 SSE replay？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q140](../answers/Q140-SSE事件格式.md)
- [Q142](../answers/Q142-任务状态机.md)
