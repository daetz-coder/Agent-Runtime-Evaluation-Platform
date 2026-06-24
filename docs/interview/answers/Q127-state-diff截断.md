# Q127: 状态 diff 截断策略是什么？大 state 会不会导致轨迹爆炸？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q127 |
| 分类 | SDK 与零侵入接入 |
| 难度 | ★ |

## 问题

状态 diff 截断策略是什么？大 state 会不会导致轨迹爆炸？

## 参考答案

围绕 state diff 截断：_short 限制 state 快照大小 面试回答应先说业务场景，再落到 sdk/adapters/langgraph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `sdk/adapters/langgraph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- state diff 截断：_short 限制 state 快照大小
- 代码入口：sdk/adapters/langgraph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「state diff 截断」最先看哪段代码？**

A: 打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 state diff 截断？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q126](../answers/Q126-同步异步节点.md)
- [Q128](../answers/Q128-SDK独立安装.md)
