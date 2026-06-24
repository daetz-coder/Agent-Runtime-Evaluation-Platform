# Q31: LangGraph adapter 如何「透明包装」节点函数？包装后性能开销如何估算？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q031 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★ |

## 问题

LangGraph adapter 如何「透明包装」节点函数？包装后性能开销如何估算？

## 参考答案

围绕 LangGraph 包装：instrument_langgraph 装饰节点记录 NODE_EXECUTE；开销约一次 dict 序列化 面试回答应先说业务场景，再落到 sdk/adapters/langgraph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `sdk/adapters/langgraph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- LangGraph 包装：instrument_langgraph 装饰节点记录 NODE_EXECUTE
- 代码入口：sdk/adapters/langgraph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「LangGraph 包装」最先看哪段代码？**

A: 打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 LangGraph 包装？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q030](../answers/Q030-低侵入埋点.md)
- [Q032](../answers/Q032-Callback映射.md)
