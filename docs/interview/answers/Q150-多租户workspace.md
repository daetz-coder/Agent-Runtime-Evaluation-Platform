# Q150: 多租户（workspace）隔离如何实现？`workspace_endpoints.py` 的设计意图？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q150 |
| 分类 | 系统设计与生产化 |
| 难度 | ★ |

## 问题

多租户（workspace）隔离如何实现？`workspace_endpoints.py` 的设计意图？

## 参考答案

问题「多租户（workspace）隔离如何实现？`workspace_endpoints.py` 的设计意图？」考察 多租户 workspace。workspace 隔离 task/eval 当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。 首要读 app/api/v1/endpoints/workspace_endpoints.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/api/v1/endpoints/workspace_endpoints.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 多租户 workspace：workspace 隔离 task/eval
- 代码入口：app/api/v1/endpoints/workspace_endpoints.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「多租户 workspace」最先看哪段代码？**

A: 打开 app/api/v1/endpoints/workspace_endpoints.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 多租户 workspace？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q149](../answers/Q149-Celery队列.md)
- [Q151](../answers/Q151-评估版本化.md)
