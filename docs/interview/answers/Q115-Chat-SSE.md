# Q115: Chat 接口是 SSE 流式还是一次性返回？流式事件类型有哪些？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q115 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★ |

## 问题

Chat 接口是 SSE 流式还是一次性返回？流式事件类型有哪些？

## 参考答案

围绕 Chat SSE：SSE 流式 token；事件 type 含 message/done/error 面试回答应先说业务场景，再落到 app/wiki_agent/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/wiki_agent/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Chat SSE：SSE 流式 token
- 代码入口：app/wiki_agent/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Chat SSE」最先看哪段代码？**

A: 打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Chat SSE？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q114](../answers/Q114-Wiki完整链路.md)
- [Q116](../answers/Q116-SYSTEM-PROMPT.md)
