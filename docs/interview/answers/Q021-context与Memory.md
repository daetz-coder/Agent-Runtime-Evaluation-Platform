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

可以合并成 **4 类**，更适合工程实现：

```text
1. Working Memory + Short-term Memory
   → Session State Memory

2. Long-term Memory
   → User Profile Memory

3. Episodic Memory + Procedural Memory
   → Experience / Policy Memory

4. Semantic Memory
   → Knowledge Memory
```

## 推荐存储方式

| Memory 类型       | 存什么                                   | 存哪里                           | 是否进 Chroma |
| ----------------- | ---------------------------------------- | -------------------------------- | ------------- |
| Working Memory    | 本轮临时变量、工具中间结果、当前步骤状态 | LangGraph `state`                | 否            |
| Short-term Memory | 当前会话历史、最近消息、session facts    | LangGraph `state` + checkpointer | 通常否        |
| Long-term Memory  | 用户偏好、长期目标、稳定事实             | SQL/KV + 可选 Chroma             | 可选          |
| Episodic Memory   | 历史任务摘要、失败经验、成功路径         | SQL + Chroma                     | 是            |
| Semantic Memory   | 文档知识、领域知识、实体事实             | Chroma / 向量库 / KG             | 是            |
| Procedural Memory | 固定流程、工具使用策略、规则模板         | 代码 / YAML / SQL                | 一般否        |

## 1. Working Memory：存入 state

这是当前 step 的临时变量，不应该进长期库。

```python
state = {
    "messages": [],
    "current_question": user_input,
    "tool_results": {},
    "scratchpad": {},
    "current_step": "retrieval"
}
```

特点：

```text
生命周期：本轮任务
存储位置：LangGraph state
是否持久化：可通过 checkpointer 暂存
是否进 Chroma：不进
```

## 2. Short-term Memory：state + checkpointer

例如当前会话中的事实：

```python
state = {
    "messages": messages,
    "session_facts": {
        "current_topic": "Agent Memory",
        "preferred_answer_style": "答辩风格",
        "last_question": "RAG和Memory关系"
    }
}
```

特点：

```text
生命周期：当前 session/thread
存储位置：LangGraph state
持久化：checkpointer
是否进 Chroma：一般不进
```

短期记忆主要靠：

```text
thread_id + checkpointer
```

恢复。

## 3. Long-term Memory：SQL/KV + 可选 Chroma

长期记忆是稳定用户事实，比如：

```json
{
  "user_id": "u001",
  "memory_type": "profile",
  "key": "preferred_language",
  "value": "Chinese",
  "confidence": 0.95,
  "source": "user_explicit",
  "updated_at": "2026-06-25"
}
```

推荐：

```text
结构化事实 → SQL / KV
语义检索内容 → Chroma
```

例如：

```text
preferred_language = Chinese
```

这种结构化偏好，存 SQL/KV 更好。

而：

```text
用户长期研究 Agent Evaluation、Memory Evaluator、Trajectory Compression 等方向。
```

这种语义描述，可以存 Chroma。

## 4. Episodic Memory：任务经验，建议合并到 Experience Memory

你问“Episodic Memory 可以合并成什么”，我建议合并到：

```text
Experience Memory
```

它保存的是“过去某次任务发生了什么”。

例如：

```json
{
  "memory_type": "episode",
  "task_id": "task_023",
  "summary": "用户讨论了 Agent Memory 架构，重点关注 key_facts、RAG 和 Chroma 存储。",
  "outcome": "形成了 Memory 分层方案",
  "mistakes": ["一开始没有区分 key_facts 和 long-term memory"],
  "useful_patterns": ["用 Resolver 处理短期与长期记忆冲突"],
  "created_at": "2026-06-25"
}
```

存储：

```text
元数据 → SQL
summary embedding → Chroma
```

因为以后用户说：

```text
继续上次那个 Memory 架构
```

就可以通过 Chroma 召回这个 episode。

## 5. Semantic Memory：知识事实，存 Chroma / KG

Semantic Memory 是知识，不是用户画像。

例如：

```text
RAG 属于检索机制，不是 Memory 本身。
LangGraph 的 short-term memory 主要通过 state + checkpointer 实现。
Memory Resolver 用于解决短期和长期记忆冲突。
```

存储：

```text
文档型知识 → Chroma
结构化实体关系 → Knowledge Graph / SQL
```

例如 Chroma 文档：

```python
doc = {
    "content": "RAG is a retrieval mechanism used to retrieve relevant memory or external documents.",
    "metadata": {
        "memory_type": "semantic",
        "source": "project_notes",
        "topic": "agent_memory"
    }
}
```

## 6. Procedural Memory：流程策略，建议不要和普通记忆混存

Procedural Memory 是“怎么做事”。

例如：

```yaml
tool_use_policy:
  - if question requires latest information, use web_search
  - if question asks about uploaded files, use file_search
  - if final answer uses retrieval, cite sources
```

存储位置：

```text
稳定策略 → 代码 / YAML / Prompt template
可更新策略 → SQL
不建议默认存 Chroma
```

为什么？

因为 procedural memory 更像规则，不是普通语义片段。如果放进 Chroma，可能召回不稳定，导致策略执行不可靠。

## 最推荐的工程架构

```text
User Input
   ↓
LangGraph State
   ├── Working Memory
   └── Short-term Memory
          ↓
Memory Write Detector
          ↓
Fact / Episode / Knowledge Extractor
          ↓
Memory Classifier
          ├── User Profile Memory → SQL/KV
          ├── Experience Memory → SQL + Chroma
          ├── Knowledge Memory → Chroma / KG
          └── Policy Memory → YAML / SQL
          ↓
Memory Retriever
          ├── SQL/KV exact lookup
          ├── Chroma semantic search
          └── KG query
          ↓
Memory Resolver
          ↓
Context Builder
          ↓
LLM
```

## 最终建议

你的项目可以这样落地：

```text
state 存：
- messages
- current_task
- current_tool_result
- session_facts
- scratchpad

SQL/KV 存：
- user_profile
- key_facts
- memory metadata
- confidence
- timestamp
- source

Chroma 存：
- episodic summaries
- semantic knowledge chunks
- long textual user/project memories

YAML/代码 存：
- procedural policy
- tool selection rules
- evaluator prompts
```

一句话：

> `state` 只存当前会话和当前任务；`Chroma` 存需要语义召回的长期文本；`SQL/KV` 存结构化、需要精确更新的用户事实；`Procedural Memory` 尽量放代码、YAML 或 Prompt 模板中，不建议完全依赖向量召回。



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
