# Q184: 如何把本平台的评估能力封装成 MCP Server，供 Cursor / Claude Desktop 调用？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q184 |
| 分类 | 编码与现场设计题 |
| 难度 | ★ |

## 问题

如何把本平台的评估能力封装成 MCP Server，供 Cursor / Claude Desktop 调用？

## 参考答案

围绕 MCP Server：暴露 evaluate/tools MCP 面试回答应先说业务场景，再落到 app/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- MCP Server：暴露 evaluate/tools MCP
- 代码入口：app/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「MCP Server」最先看哪段代码？**

A: 打开 app/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 MCP Server？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q183](../answers/Q183-在线评估.md)
- [Q185](../answers/Q185-黄金数据集.md)
