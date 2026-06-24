# Q38: `observation` 字段非字符串时会 `json.dumps`，为什么？下游 Evaluator 如何消费？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q038 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★ |

## 问题

`observation` 字段非字符串时会 `json.dumps`，为什么？下游 Evaluator 如何消费？

## 参考答案

Q38 与 observation 序列化 相关。非字符串 json.dumps；Judge 读 observation 文本 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `sdk/collector.py`
- `app/evaluators/base.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- observation 序列化：非字符串 json.dumps
- 代码入口：sdk/collector.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「observation 序列化」最先看哪段代码？**

A: 打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 observation 序列化？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q037](../answers/Q037-伪造轨迹检测.md)
- [Q039](../answers/Q039-step-number语义.md)
