# Q25: 请对比 `app/collectors/trajectory.py` 和 `sdk/collector.py` 两套实现：为什么存在两份？如何保持同步？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q025 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★★ |

## 问题

请对比 `app/collectors/trajectory.py` 和 `sdk/collector.py` 两套实现：为什么存在两份？如何保持同步？

## 参考答案

围绕 两套 collector：服务端 collector 供平台内部；SDK 零依赖 httpx 供外部 Agent；逻辑应对齐 ActionType 与 batch flush 面试回答应先说业务场景，再落到 app/collectors/trajectory.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/collectors/trajectory.py`
- `sdk/collector.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- 两套 collector：服务端 collector 供平台内部
- 代码入口：app/collectors/trajectory.py
- app/collectors/trajectory.py 供平台内部
- sdk/collector.py 供外部零依赖
- 两者 ActionType 与 batch 语义应一致

## 常见追问

**Q: 「两套 collector」最先看哪段代码？**

A: 打开 app/collectors/trajectory.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 两套 collector？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q024](../answers/Q024-HITL轨迹记录.md)
- [Q026](../answers/Q026-finish与离线缓冲.md)
