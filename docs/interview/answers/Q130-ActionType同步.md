# Q130: SDK 的 `ActionType` 和平台 `app/models/action_types.py` 如何保持一致？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q130 |
| 分类 | SDK 与零侵入接入 |
| 难度 | ★ |

## 问题

SDK 的 `ActionType` 和平台 `app/models/action_types.py` 如何保持一致？

## 参考答案

围绕 ActionType 同步：两处常量需 CI diff 检查 面试回答应先说业务场景，再落到 app/models/action_types.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/models/action_types.py`
- `sdk/collector.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- ActionType 同步：两处常量需 CI diff 检查
- 代码入口：app/models/action_types.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「ActionType 同步」最先看哪段代码？**

A: 打开 app/models/action_types.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 ActionType 同步？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q129](../answers/Q129-非LangChain接入.md)
- [Q131](../answers/Q131-单调性基准.md)
