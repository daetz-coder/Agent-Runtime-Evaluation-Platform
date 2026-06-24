# Q118: 用户 reject 提取结果后，状态如何更新？会不会重复提示？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q118 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★ |

## 问题

用户 reject 提取结果后，状态如何更新？会不会重复提示？

## 参考答案

围绕 reject 提取：状态标记 rejected 防重复 prompt 面试回答应先说业务场景，再落到 app/wiki_agent/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/wiki_agent/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- reject 提取：状态标记 rejected 防重复 prompt
- 代码入口：app/wiki_agent/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「reject 提取」最先看哪段代码？**

A: 打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 reject 提取？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q117](../answers/Q117-自动提取.md)
- [Q119](../answers/Q119-CRUD索引同步.md)
