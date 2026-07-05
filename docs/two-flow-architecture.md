# Wiki Agent + 评估平台 双流架构

> 从 Wiki Agent 生成数据到评估平台消费数据的完整流程。

---

## 一、双流全景图

```
═══════════════════════════════════════════════════════════════════════
  Wiki Agent 流（数据生产）            评估平台流（数据消费）
═══════════════════════════════════════════════════════════════════════

  用户发消息 "介绍一下 JWT 认证"
       │
       ▼
  ┌─────────────────────────┐
  │  run_chat_stream()      │
  │  emit_session_start()   │───────────→ 创建评估任务 (task_id)
  └────────┬────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  search 节点             │
  │                         │
  │  ① retrieve_context()   │
  │     ├─ hybrid_search()  │──→ RETRIEVAL ──→ 记录检索查询+结果
  │     ├─ get_user_memory()│──→ MEMORY_READ ──→ 记忆读取
  │     └─ get_session_facts│──→ MEMORY_READ ──→ 记忆读取
  │                         │
  │  ② _extract_key_facts() │──→ MEMORY_WRITE ──→ 记忆写入
  │                         │
  │  ③ build_context_block()│──→ EVIDENCE ──→ 证据池构建
  │                         │
  │  ④ NODE_EXECUTE         │──→ 节点执行记录
  │  ⑤ STATE_CHANGE         │──→ 状态变化记录
  └────────┬────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  respond 节点            │
  │                         │
  │  ① LLM 流式生成回复     │──→ THINK ──→ 思考记录
  │  ② NODE_EXECUTE         │──→ 节点执行记录
  │  ③ STATE_CHANGE         │──→ 状态变化记录
  │  ④ emit_response()      │──→ EVIDENCE ──→ 最终回复记录
  └────────┬────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  decide 节点             │
  │                         │
  │  ① decide_action()      │
  │     └─ with_structured  │
  │        _output()        │
  │     └─ KnowledgeDecision│
  │        {action, title,  │
  │         content, ...}   │
  │                         │
  │  ② TOOL_DECISION        │──→ 工具选择决策
  │  ③ PLAN_UPDATE          │──→ 计划更新
  │  ④ NODE_EXECUTE         │──→ 节点执行记录
  │  ⑤ STATE_CHANGE         │──→ 状态变化记录
  └────────┬────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  execute 节点 (HITL)    │
  │                         │
  │  interrupt({}) ← 暂停   │──→ _flush() 保存已有步骤
  │                         │
  │  ── 用户确认 ──         │
  │                         │
  │  ① crud_tools.create()  │──→ TOOL_CALL + TOOL_RESULT
  │  ② 失败？               │
  │     └─ REPLAN           │──→ 重规划（尝试替代方案）
  │     └─ 重试 CRUD        │──→ TOOL_CALL + TOOL_RESULT
  │  ③ NODE_EXECUTE         │──→ 节点执行记录
  └────────┬────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  emit_session_end()     │
  │  collector.finish()     │───────────→ flush 所有步骤到 DB
  └─────────────────────────┘             触发评估

═══════════════════════════════════════════════════════════════════════
                               │
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                    评估平台（数据消费）                           │
  │                                                                 │
  │  ① agent_trajectories 表                                        │
  │     存储所有步骤（step_number, action_type, action_detail, ...） │
  │                                                                 │
  │  ② TrajectoryCompressor（4 阶段压缩）                           │
  │     ├─ 重要性过滤（按 action_type 权重）                         │
  │     ├─ THINK 摘要截断（200 字）                                  │
  │     ├─ 滑动窗口（最近 30 步 + 锚点步）                           │
  │     └─ 格式化为 LLM 可读文本                                     │
  │                                                                 │
  │  ③ 6 个评估器并行执行                                            │
  │     ├─ PlanningEvaluator  ← PLAN, PLAN_UPDATE                   │
  │     ├─ TacticalEvaluator  ← 所有非 PLAN 步骤                    │
  │     ├─ ToolUseEvaluator   ← TOOL_CALL, TOOL_RESULT             │
  │     ├─ MemoryEvaluator    ← MEMORY_WRITE, MEMORY_READ          │
  │     ├─ ReplanEvaluator    ← REPLAN, FAILURE                    │
  │     └─ RetrievalEvaluator ← RETRIEVAL, EVIDENCE                │
  │                                                                 │
  │  ④ with_structured_output + 重试                                │
  │     └─ Pydantic Schema 约束 LLM 输出格式                        │
  │     └─ 失败时反馈错误 → 重试 → 回退到手动解析                    │
  │                                                                 │
  │  ⑤ evaluations 表                                               │
  │     存储 6 维评分 + 反馈 + Judge 原始数据                        │
  └─────────────────────────────────────────────────────────────────┘
```

---

## 二、Wiki Agent 的规划与原始数据

### 2.1 规划来源

Wiki Agent 的"规划"不是显式的 PLAN 步骤，而是**隐式在 decide 节点中**：

```
用户: "介绍一下 JWT 认证"
       │
       ▼
  decide 节点
    └─ knowledge_agent.decide_action()
         └─ with_structured_output(KnowledgeDecision)
              └─ LLM 返回:
                 {
                     "action": "create",
                     "title": "JWT 认证介绍",
                     "category": "programming/auth",
                     "content": "# JWT 认证\n\nJSON Web Token...",
                     "reason": "对话中包含 JWT 知识，知识库无相关条目"
                 }
```

**这个 KnowledgeDecision 就是"规划"** — 决定做什么、怎么做。

### 2.2 原始数据是什么？

Wiki Agent 的原始数据 = **LangGraph 节点执行过程中的所有中间产物**：

| 原始数据 | 来源 | 格式 |
|---------|------|------|
| 用户消息 | `state["user_message"]` | str |
| 检索结果 | `hybrid_search()` 返回 | list[dict]（title, path, snippet, score） |
| 记忆数据 | `get_user_memory()` / `get_session_key_facts()` | list[dict]（content, type, confidence） |
| LLM 回复 | `chat_llm.astream()` 收集 | str（流式拼接） |
| 知识决策 | `decide_action()` 返回 | KnowledgeDecision Pydantic 对象 |
| CRUD 结果 | `crud_tools.create_knowledge()` 返回 | dict（status, path, message） |

---

## 三、数据如何进入 Wrapper（Collector）

### 3.1 Wrapper 是什么？

```
graph.py（业务代码）  →  hooks.py（Wrapper）  →  collector（SDK）
     │                      │                      │
     │  emit_retrieval()    │  record_retrieval()   │  构建 step dict
     │  emit_key_facts()    │  record_memory_write()│  Pydantic 校验
     │  emit_response()     │  record(EVIDENCE)     │  追加到缓冲区
     │                      │                      │
     └──────────────────────┴──────────────────────┘
```

### 3.2 每个节点产生的步骤

```
search 节点执行：
  │
  ├─ collector.record_node_execute("search", input={...})
  │    └─ step: {action_type: "node_execute", action_detail: {node_name, input}}
  │
  ├─ collector.record_retrieval(query, results, duration_ms)
  │    └─ step: {action_type: "retrieval", action_detail: {query, retrieved_docs, ...}}
  │
  ├─ collector.record_memory_read("user_memory", value=5, hit=True)
  │    └─ step: {action_type: "memory_read", action_detail: {key, value, hit}}
  │
  ├─ collector.record_memory_write("key_facts", facts, source="llm_extraction")
  │    └─ step: {action_type: "memory_write", action_detail: {key, value, source}}
  │
  ├─ collector.record_evidence("rag_context", sources={...})
  │    └─ step: {action_type: "evidence", action_detail: {evidence_type, sources}}
  │
  ├─ collector.record_node_execute("search_complete", output={...})
  │    └─ step: {action_type: "node_execute", action_detail: {node_name, output}}
  │
  └─ collector.record_state_change(before, after, trigger="search")
       └─ step: {action_type: "state_change", action_detail: {node_name, trigger, diff}}
```

---

## 四、评估平台获取了什么信息？

### 4.1 从 DB 读取的轨迹数据

```sql
SELECT * FROM agent_trajectories WHERE task_id = 'xxx' ORDER BY step_number;
```

| step_number | action_type | action_detail | observation | timestamp |
|---|---|---|---|---|
| 1 | plan | `{"goal": "介绍一下 JWT", "context": {...}}` | null | 2026-07-05T10:00:00Z |
| 2 | node_execute | `{"node_name": "search", "input": {...}}` | null | 2026-07-05T10:00:01Z |
| 3 | retrieval | `{"query": "JWT 认证", "retrieved_docs": [...], "duration_ms": 156}` | null | 2026-07-05T10:00:01.2Z |
| 4 | memory_read | `{"key": "user_memory", "value": 3, "hit": true}` | null | 2026-07-05T10:00:01.3Z |
| 5 | memory_write | `{"key": "key_facts", "value": ["JWT 是一种认证方式"]}` | null | 2026-07-05T10:00:02Z |
| 6 | evidence | `{"evidence_type": "rag_context", "sources": {...}}` | null | 2026-07-05T10:00:02.1Z |
| 7 | node_execute | `{"node_name": "search_complete", "output": {...}}` | null | 2026-07-05T10:00:02.2Z |
| 8 | state_change | `{"node_name": "search", "diff": {...}}` | null | 2026-07-05T10:00:02.3Z |
| 9 | node_execute | `{"node_name": "respond", "input": {...}}` | null | 2026-07-05T10:00:02.4Z |
| 10 | think | `{"thought": "LLM call to deepseek-chat"}` | null | 2026-07-05T10:00:03Z |
| 11 | evidence | `{"final_response": "JWT 是一种...", "session_id": "s1"}` | null | 2026-07-05T10:00:05Z |
| 12 | node_execute | `{"node_name": "decide", "input": {...}}` | null | 2026-07-05T10:00:05.1Z |
| 13 | tool_decision | `{"tool_name": "crud_create", "input": {...}}` | null | 2026-07-05T10:00:06Z |
| 14 | plan_update | `{"next_action": "execute create", "reason": "..."}` | null | 2026-07-05T10:00:06.1Z |
| 15 | node_execute | `{"node_name": "execute", "input": {...}}` | null | 2026-07-05T10:00:06.2Z |
| 16 | tool_call | `{"tool_name": "crud_create", "input": {...}}` | null | 2026-07-05T10:00:07Z |
| 17 | tool_result | `{"tool_name": "crud_create", "success": true}` | `{"status": "ok", "path": "..."}` | 2026-07-05T10:00:07.5Z |

### 4.2 评估器提取的数据

```python
# PlanningEvaluator
_extract_plans(trajectory)      → [step 1 的 action_detail]
_extract_plan_updates(trajectory) → [step 14 的 action_detail]

# ToolUseEvaluator
_extract_tool_calls(trajectory)  → [step 16 的 action_detail]
_extract_tool_results(trajectory) → [step 17 的 action_detail]

# MemoryEvaluator
_extract_memory_events(trajectory) → [step 4, 5 的 action_detail]

# RetrievalEvaluator
_extract_retrievals(trajectory)  → [step 3 的 action_detail]
_extract_evidence(trajectory)   → [step 6, 11 的 action_detail]

# ReplanEvaluator
# 扫描 failure + replan 步骤
```

---

## 五、格式保证机制

### 5.1 三层保证

```
第 1 层：Pydantic Schema（定义格式）
    sdk/schemas.py
    ├─ PlanDetail {goal, context?, steps?}
    ├─ RetrievalDetail {query, source?, retrieved_docs?}
    ├─ KnowledgeDecision {action, reason, title?, content?}
    └─ ...

第 2 层：record() 校验（写入时校验）
    sdk/collector.py → _validate_step()
    └─ schema_class.model_validate(action_detail)
    └─ 缺少必填字段 → 拒绝 + warning

第 3 层：with_structured_output（LLM 输出约束）
    ├─ Agent LLM：KnowledgeDecision schema → function calling
    └─ 评估器 LLM：ToolUseEvaluationResult schema → function calling
```

### 5.2 每个环节的格式保证

| 环节 | 数据 | 保证方式 | 保证者 |
|------|------|---------|--------|
| Wiki Agent 检索 | 检索结果 dict | search_tools 返回格式 | 代码硬编码 |
| Wiki Agent 记忆 | key_facts list | session_store 返回格式 | 代码硬编码 |
| Wiki Agent 决策 | KnowledgeDecision | **with_structured_output** | Pydantic Schema + API |
| Wiki Agent CRUD | crud_tools 返回 | sync_manager 返回格式 | 代码硬编码 |
| Collector 记录 | step dict | **Pydantic Schema 校验** | sdk/schemas.py |
| Collector 上传 | steps list | HTTP JSON 序列化 | json.dumps |
| 评估器输入 | 格式化文本 | _format_trajectory() | 代码硬编码 |
| 评估器输出 | 评分 dict | **with_structured_output** | Pydantic Schema + API |

### 5.3 关键代码链路

```python
# ① Wiki Agent 决策 — with_structured_output 保证
knowledge_agent.py:
    structured_llm = llm.with_structured_output(KnowledgeDecision)
    result = await chain.ainvoke(inputs)
    # → KnowledgeDecision(action="create", title="JWT", content="...")

# ② Collector 记录 — Pydantic Schema 校验保证
collector.py:
    error = self._validate_step(action_type, action_detail)
    # → ToolCallDetail.model_validate({"tool_name": "crud_create", ...})
    # → 通过 ✅ 或 拒绝 ❌

# ③ 评估器输出 — with_structured_output 保证
tool_use_evaluator.py:
    structured_llm = self.llm.with_structured_output(ToolUseEvaluationResult)
    result = await self._invoke_structured_llm(chain, inputs, ToolUseEvaluationResult)
    # → ToolUseEvaluationResult(selection_quality=85, feedback="...")
```

---

## 六、区别与联系

### 区别

| | Wiki Agent 流 | 评估平台流 |
|---|---|---|
| **角色** | 数据生产者 | 数据消费者 |
| **运行时机** | 用户发消息时 | 用户对话结束后 |
| **核心逻辑** | 检索 → 回复 → 决策 → 执行 | 读取轨迹 → 压缩 → LLM 评分 |
| **LLM 用途** | 生成回复 + 知识决策 | 评估打分 |
| **输出格式** | KnowledgeDecision（决策） | ToolUseEvaluationResult（评分） |
| **格式保证** | with_structured_output | with_structured_output |

### 联系

```
Wiki Agent 的输出 ──→ Collector record() ──→ DB ──→ 评估平台的输入

Wiki Agent 的 TOOL_CALL   → 评估平台的 ToolUseEvaluator 消费
Wiki Agent 的 RETRIEVAL   → 评估平台的 RetrievalEvaluator 消费
Wiki Agent 的 MEMORY_WRITE → 评估平台的 MemoryEvaluator 消费
Wiki Agent 的 PLAN_UPDATE → 评估平台的 PlanningEvaluator 消费
Wiki Agent 的 REPLAN      → 评估平台的 ReplanEvaluator 消费
```

**一条轨迹，两个流共享**：
- Wiki Agent **写入**轨迹（record_*）
- 评估平台**读取**轨迹（_extract_*）
- 两者通过 `action_type` 字段关联
