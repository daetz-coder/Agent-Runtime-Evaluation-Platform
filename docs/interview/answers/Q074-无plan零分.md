# Q74: 没有 `plan` 或 `plan_update` 动作时，Planning 得 0 分——这个规则是否过于严格？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q074 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

没有 `plan` 或 `plan_update` 动作时，Planning 得 0 分——这个规则是否过于严格？

## 参考答案

Q74 与 无 plan 零分 相关。无 plan/plan_update 返回 0；严格但可改 N/A Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 无 plan 零分：无 plan/plan_update 返回 0
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「无 plan 零分」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 无 plan 零分？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q073](../answers/Q073-Planning权重.md)
- [Q075](../answers/Q075-granularity定义.md)
