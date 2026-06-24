# Q21: Agent 的 `context`（如 `key_facts`）在评估中起什么作用？Memory Evaluator 如何利用它？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q021 |
| 分类 | Agent 架构与设计理念 |
| 难度 | ★ |

## 问题

Agent 的 `context`（如 `key_facts`）在评估中起什么作用？Memory Evaluator 如何利用它？

## 参考答案

context 随 task 存储（如 key_facts 列表），MemoryEvaluator prompt 注入 context 与 trajectory 中 memory_read/write。retention 评是否记住早期事实；consistency 评是否自相矛盾。无显式 memory 动作时 Judge 从 trajectory 启发式推断。Wiki Agent 可在 context 传 session metadata。

## 代码依据

- `app/evaluators/memory_evaluator.py`
- `app/models/schemas.py`
- `app/db/models.py`

## 回答要点

- key_facts 是 ground hint
- memory_read/write 显式更佳
- 无动作时靠 LLM 推断，噪声更大
- context 在 evaluate API 传入

## 常见追问

**Q: key_facts 谁维护？**

A: Agent 或 adapter 在 start/update 时写入。

**Q: 和 vector memory 关系？**

A: key_facts 是评估锚点，非替代向量库。

## 相关题目

- [Q020](../answers/Q020-第三方框架适配.md)
- [Q022](../answers/Q022-轨迹token超限.md)
