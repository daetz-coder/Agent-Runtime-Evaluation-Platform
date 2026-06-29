# Q25: 请说明 `sdk/collector.py` 与 `app/collectors/inprocess_transport.py` 的关系：为什么 Wiki 内嵌时需要 in-process transport？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q025 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★★ |

## 问题

请说明 `sdk/collector.py` 与 `app/collectors/inprocess_transport.py` 的关系：为什么 Wiki 内嵌时需要 in-process transport？

## 参考答案

围绕 Collector 架构：sdk/collector.py 为唯一实现；Wiki 内嵌时用 app/collectors/inprocess_transport.py 直写 DB 避免 HTTP 自锁 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `sdk/collector.py`
- `app/collectors/inprocess_transport.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- Collector 单一实现：sdk/collector.py
- 代码入口：sdk/collector.py
- Wiki 内嵌用 inprocess_transport 绕过 HTTP
- 外部 Agent 用 HTTP 上报 trajectory
- ActionType 与 batch 语义一致

## 常见追问

**Q: 「Collector 架构」最先看哪段代码？**

A: 打开 sdk/collector.py；Wiki 内嵌路径看 app/collectors/inprocess_transport.py。

**Q: Demo 里如何验证 Collector？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q024](../answers/Q024-HITL轨迹记录.md)
- [Q026](../answers/Q026-finish与离线缓冲.md)
