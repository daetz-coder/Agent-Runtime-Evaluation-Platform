# Q24: Human-in-the-loop 场景下，轨迹里应该记录什么？Wiki Agent 的 interrupt 机制如何体现？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q024 |
| 分类 | Agent 架构与设计理念 |
| 难度 | ★ |

## 问题

Human-in-the-loop 场景下，轨迹里应该记录什么？Wiki Agent 的 interrupt 机制如何体现？

## 参考答案

Human-in-the-loop：轨迹应记录 interrupt、用户输入、decide 节点分支。Wiki Agent graph decide 节点判断是否需要人工确认（如知识提取）；LangGraph interrupt 暂停后恢复，checkpoint AsyncSqliteSaver 存状态。EvaluationTrace 可 record_state_change 记录 HITL 前后 diff。评估时 Tactical 可看是否因 HITL 改变路径。

>Human-in-the-loop 的轨迹应完整记录 **interrupt、human_input、state_change、replan** 等关键事件。Wiki Agent 通过 `decide` 节点作为 HITL 网关，在需要人工确认时调用 LangGraph 的 `interrupt()` 暂停执行，并利用持久化 checkpoint 保存 Graph State。用户反馈后恢复执行，Trajectory 继续记录后续动作，从而保证 Agent 的执行路径既可恢复，又可评估。Tactical Evaluator 可以利用这些轨迹分析 Human Feedback 是否改善了规划、工具选择和最终回答质量。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/models/action_types.py`
- `app/wiki_agent/evaluation.py`

## 回答要点

- 记录 interrupt 与用户决策
- decide 节点 HITL 网关
- state_change 记录前后状态
- checkpoint 支持会话恢复

## 常见追问

**Q: interrupt 和 failure？**

A: interrupt 是预期暂停，failure 是异常。

**Q: 评 HITL 质量？**

A: 可看 replan/tactical 是否因反馈改进。

## 相关题目

- [Q023](../answers/Q023-多轮与子任务.md)
- [Q025](../answers/Q025-两套collector对比.md)
