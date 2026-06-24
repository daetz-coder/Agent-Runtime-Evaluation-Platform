# Q163: 评估 overall 80 分但用户认为 Agent 表现很差——如何解释和处理？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q163 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★ |

## 问题

评估 overall 80 分但用户认为 Agent 表现很差——如何解释和处理？

## 参考答案

围绕 overall 高分争议：展示六维雷达；业务 KPI 对齐 面试回答应先说业务场景，再落到 app/graphs/evaluation_graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- overall 高分争议：展示六维雷达
- 代码入口：app/graphs/evaluation_graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「overall 高分争议」最先看哪段代码？**

A: 打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 overall 高分争议？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q162](../answers/Q162-Planning低分排查.md)
- [Q164](../answers/Q164-Retrieval零分.md)
