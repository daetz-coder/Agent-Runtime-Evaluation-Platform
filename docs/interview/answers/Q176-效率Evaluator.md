# Q176: 实现一个 Evaluator：检测 Agent 是否在 10 步内完成任务（效率指标），如何设计？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q176 |
| 分类 | 编码与现场设计题 |
| 难度 | ★ |

## 问题

实现一个 Evaluator：检测 Agent 是否在 10 步内完成任务（效率指标），如何设计？

## 参考答案

Q176 与 效率 Evaluator 相关。统计 step 数与 goal 达成 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/evaluators/base.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 效率 Evaluator：统计 step 数与 goal 达成
- 代码入口：app/evaluators/base.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「效率 Evaluator」最先看哪段代码？**

A: 打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 效率 Evaluator？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q175](../answers/Q175-新增Safety维.md)
- [Q177](../answers/Q177-采样率上报.md)
