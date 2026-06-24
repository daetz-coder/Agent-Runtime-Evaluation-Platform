# Q83: `context.key_facts` 和从 trajectory 启发式推断的记忆，哪个更可靠？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q083 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

`context.key_facts` 和从 trajectory 启发式推断的记忆，哪个更可靠？

## 参考答案

Q83 与 key_facts 可靠性 相关。显式 key_facts 优于纯推断 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/evaluators/memory_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- key_facts 可靠性：显式 key_facts 优于纯推断
- 代码入口：app/evaluators/memory_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「key_facts 可靠性」最先看哪段代码？**

A: 打开 app/evaluators/memory_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 key_facts 可靠性？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q082](../answers/Q082-Memory三子维.md)
- [Q084](../answers/Q084-无memory动作.md)
