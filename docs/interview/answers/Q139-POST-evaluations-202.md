# Q139: 评估 API `POST /evaluations` 返回 202 异步，客户端如何获取结果？轮询还是 SSE？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q139 |
| 分类 | 后端工程与 API 设计 |
| 难度 | ★★ |

## 问题

评估 API `POST /evaluations` 返回 202 异步，客户端如何获取结果？轮询还是 SSE？

## 参考答案

围绕 POST evaluations 202：异步；客户端轮询或 SSE 面试回答应先说业务场景，再落到 app/api/v1/endpoints/evaluation.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/api/v1/endpoints/evaluation.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- POST evaluations 202：异步
- 代码入口：app/api/v1/endpoints/evaluation.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「POST evaluations 202」最先看哪段代码？**

A: 打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 POST evaluations 202？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q138](../answers/Q138-多模型benchmark.md)
- [Q140](../answers/Q140-SSE事件格式.md)
