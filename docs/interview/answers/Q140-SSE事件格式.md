# Q140: `POST /evaluations/stream` SSE 事件格式是什么？progress / result / done 各携带什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q140 |
| 分类 | 后端工程与 API 设计 |
| 难度 | ★ |

## 问题

`POST /evaluations/stream` SSE 事件格式是什么？progress / result / done 各携带什么？

## 参考答案

Q140 与 SSE 格式 相关。progress/result/done 事件 JSON Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/api/v1/endpoints/evaluation.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- SSE 格式：progress/result/done 事件 JSON
- 代码入口：app/api/v1/endpoints/evaluation.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「SSE 格式」最先看哪段代码？**

A: 打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 SSE 格式？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q139](../answers/Q139-POST-evaluations-202.md)
- [Q141](../answers/Q141-SSE-replay.md)
