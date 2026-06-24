# Q147: `/health` 和 `/api/v1/system/health` 为什么有两个？前端开发环境 proxy 如何配置？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q147 |
| 分类 | 后端工程与 API 设计 |
| 难度 | ★ |

## 问题

`/health` 和 `/api/v1/system/health` 为什么有两个？前端开发环境 proxy 如何配置？

## 参考答案

问题「`/health` 和 `/api/v1/system/health` 为什么有两个？前端开发环境 proxy 如何配置？」考察 双 health。/health 与 /api/v1/system/health；proxy FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。 首要读 app/main.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/main.py`
- `frontend/vite.config.ts`
- `app/graphs/evaluation_graph.py`

## 回答要点

- 双 health：/health 与 /api/v1/system/health
- 代码入口：app/main.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「双 health」最先看哪段代码？**

A: 打开 app/main.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 双 health？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q146](../answers/Q146-AUTH_ENABLED.md)
- [Q148](../answers/Q148-10万次日评估.md)
