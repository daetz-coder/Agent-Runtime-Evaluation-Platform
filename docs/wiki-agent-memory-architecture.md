# Wiki Agent 记忆体系架构

> 四路记忆系统 + 六层压缩策略 + 四端一致性保障。

---

## 一、整体架构图

```
用户发送消息
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  chat.py — 入口层                                                               │
│                                                                                 │
│  ① get_recent_messages(session_id, limit=20)   ← SQL LIMIT，只取最近 10 轮     │
│  ② _build_history(messages, max_turns=10)      ← 滑动窗口截断                  │
│  ③ add_message(session_id, "user", message)    ← 写入 SQLite                   │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  context_retriever.py — retrieve_context()                                      │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ ① Query 改写 Pipeline（query_rewriter.py）                                │  │
│  │    Contextualizer → QueryClassifier → QueryRewriter → SimilarityValidator │  │
│  │    原始 query → 改写 queries (1~5 个)                                      │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                          │                                                      │
│           ┌──────────────┼──────────────┬──────────────────┐                    │
│           ▼              ▼              ▼                  ▼                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐              │
│  │ ② External  │ │ ③ User      │ │ ④ Session   │ │ ⑤ Working    │              │
│  │    KB (RAG) │ │   Memory    │ │   Memory    │ │   Memory     │              │
│  │             │ │             │ │             │ │              │              │
│  │ hybrid_search│ │ user_memory │ │ sessions.   │ │ chat_history │              │
│  │ (Milvus+BM25│ │ .facts      │ │ key_facts   │ │ (最近10条)   │              │
│  │ +Reranker)  │ │             │ │             │ │ 200字/条     │              │
│  │             │ │ 跨session   │ │ 当前session │ │              │              │
│  │ top 5 结果  │ │ 上限30条    │ │ 上限20条    │ │ 截断2000字   │              │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬───────┘              │
│         │               │               │               │                      │
│         └───────────────┼───────────────┼───────────────┘                      │
│                         ▼                                                      │
│              RetrievedContext                                                   │
│              {wiki_results, user_facts, session_facts, history_summary}         │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  build_context_block() — 预算裁剪组装（总预算 ~3000 字符）                        │
│                                                                                 │
│  优先级 1: [用户记忆]  user_facts     (600 字符)  ← 最重要，跨 session 持久生效    │
│  优先级 2: [会话记忆]  session_facts  (400 字符)  ← 当前 session 生效             │
│  优先级 3: [知识库]    wiki_results   (1200 字符) ← RAG 检索结果                  │
│  优先级 4: [对话历史]  history        (800 字符)  ← 最近对话                      │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  graph.py — _build_llm_messages() 二次截断保护                                  │
│                                                                                 │
│  ① SystemMessage(SYSTEM_PROMPT)                                                 │
│  ② [截断提示] 如果 history 被截断 → SystemMessage 提示 LLM                      │
│  ③ SystemMessage(context_block) ← 四层上下文预算裁剪结果                         │
│  ④ prior[-(HISTORY_MAX_TURNS*2):] ← 最近 N 轮对话（二次截断保护）               │
│  ⑤ HumanMessage(当前问题)                                                       │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                                  ▼
                          chat_llm.astream()
                          流式生成 AI 回复
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  graph.py — search 节点：事实提取                                                │
│                                                                                 │
│  _extract_key_facts() → LLM 结构化提取                                           │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ Pydantic 模型约束                                                          │  │
│  │                                                                           │  │
│  │  ExtractedFact {                                                          │  │
│  │    content: str        ← 事实内容                                          │  │
│  │    type: str           ← user_preference / user_habit / project_context    │  │
│  │                           tech_constraint / task_goal                      │  │
│  │    scope: str          ← user (跨session) / session (当前session)          │  │
│  │    confidence: float   ← 0.0 ~ 1.0                                        │  │
│  │  }                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                          │                                                      │
│              ┌───────────┴───────────┐                                          │
│              ▼                       ▼                                          │
│     scope == "session"        scope == "user"                                   │
│              │                       │                                          │
│              ▼                       ▼                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐                              │
│  │ Session Memory      │  │ User Memory         │                              │
│  │ store.merge_session │  │ store.merge_user    │                              │
│  │ _key_facts()        │  │ _memory()           │                              │
│  │ 去重+置信度淘汰(20) │  │ 去重+置信度淘汰(30) │                              │
│  └─────────────────────┘  └─────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、六层压缩策略

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            压缩层次                                         │
├───────────────┬───────────────────────┬─────────────────────────────────────┤
│  层级          │  机制                  │  位置                               │
├───────────────┼───────────────────────┼─────────────────────────────────────┤
│  ① SQL 截断   │  get_recent_messages   │  store.py                           │
│               │  ORDER BY id DESC      │  只查最近 20 条                     │
│               │  LIMIT ?               │  不全量加载                         │
├───────────────┼───────────────────────┼─────────────────────────────────────┤
│  ② 滑动窗口   │  _build_history        │  chat.py                            │
│               │  messages[-(N*2):]     │  只取最近 10 轮                     │
│               │  max_turns 可配置      │  转为 LangChain messages            │
├───────────────┼───────────────────────┼─────────────────────────────────────┤
│  ③ 二次保护   │  _build_llm_messages   │  graph.py                           │
│               │  prior[-(N*2):]        │  截断 + SystemMessage 提示 LLM      │
│               │  + 截断提示            │  "更早的上下文已在摘要中呈现"       │
├───────────────┼───────────────────────┼─────────────────────────────────────┤
│  ④ 字符预算   │  build_context_block   │  context_retriever.py               │
│               │  按优先级裁剪          │  用户记忆: 600字                    │
│               │  总预算 ~3000 字符     │  会话记忆: 400字                    │
│               │                        │  KB结果: 1200字                     │
│               │                        │  对话历史: 800字                    │
├───────────────┼───────────────────────┼─────────────────────────────────────┤
│  ⑤ LLM 提炼  │  _extract_key_facts    │  graph.py                           │
│               │  从对话中提取事实      │  session: 上限 20 条                │
│               │  → session_facts       │  user: 上限 30 条                   │
│               │  → user_facts          │  低置信度被挤出                     │
│               │  去重+置信度排序       │  替代 ConversationSummaryMemory     │
├───────────────┼───────────────────────┼─────────────────────────────────────┤
│  ⑥ 分块截断   │  chunk_markdown        │  chunker.py                         │
│               │  500字/块              │  知识条目写入时                     │
│               │  50字重叠              │  Milvus 存分块而非全文              │
└───────────────┴───────────────────────┴─────────────────────────────────────┘
```

### 为什么不用 LangChain 的 ConversationSummaryMemory？

| 对比 | LangChain Memory | 本项目方案 |
|------|-----------------|-----------|
| 作用域 | Chain 级别，绑定单条链 | 多节点共享（search/respond/decide） |
| 持久化 | 内存或 Redis | SQLite 自建 session store |
| 压缩方式 | 每轮 LLM 调用压缩 | key_facts + user_memory（已等效） |
| 额外开销 | 每轮多一次 LLM 调用 | 复用 search 节点的提取，零额外调用 |

本项目的 `key_facts`（session scope）+ `user_memory`（user scope）本质上就是 `ConversationSummaryMemory` 的手动实现——LLM 从对话中提炼结构化事实，跨轮次持久化。

---

## 三、四路记忆对比

| 维度 | User Memory | Session Memory | External KB | Working Memory |
|------|------------|----------------|-------------|----------------|
| **存储位置** | `user_memory` 表 | `sessions.key_facts` | Milvus + BM25 + Markdown | 内存（不持久化） |
| **生命周期** | 永久 | 当前 session | 永久 | 当前对话轮次 |
| **跨 session** | ✅ | ❌ | ✅ | ❌ |
| **数据格式** | `list[dict]` 结构化 JSON | `list[dict]` 结构化 JSON | `list[dict]` 搜索结果 | `list[Message]` LangChain |
| **内容示例** | 用户偏好、用户习惯 | 项目技术栈、技术约束、任务目标 | 知识库文档摘要片段 | 最近 10 轮对话消息 |
| **来源** | LLM 判断 `scope=user` | LLM 判断 `scope=session` | `hybrid_search` | 原始消息 |
| **上限** | 30 条 | 20 条 | top 5 | 10 轮（20 条） |
| **淘汰策略** | 按置信度，保留最高 | 按置信度，保留最高 | 按相关度 RRF + Rerank | 滑动窗口 |
| **上下文预算** | 600 字符（优先级 1） | 400 字符（优先级 2） | 1200 字符（优先级 3） | 800 字符（优先级 4） |

---

## 四、四端一致性保障（sync_manager）

```
                    用户操作 / Agent 决策
                           │
                           ▼
                 ┌───────────────────┐
                 │   sync_manager    │
                 │  四端同步管理器     │
                 └────────┬──────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │ ① Markdown  │ │ ② Milvus    │ │ ③ BM25      │
   │  文件系统    │ │  向量数据库  │ │  倒排索引    │
   │             │ │             │ │             │
   │ service.py  │ │ chunk_md()  │ │ jieba分词   │
   │ YAML        │ │ → embed()   │ │ → BM25Okapi │
   │ frontmatter │ │ → insert()  │ │ → pickle    │
   │ + 正文      │ │             │ │   持久化    │
   └──────┬──────┘ └─────────────┘ └─────────────┘
          │
          ▼
   ┌─────────────┐
   │ ④ Git       │
   │  版本控制    │
   │             │
   │ git add +   │
   │ git commit  │
   └─────────────┘

一致性策略（BASE）：
  · 顺序写入：Markdown → Milvus+BM25 → Git
  · 不用分布式事务，允许短暂不一致
  · Markdown 为 source of truth
  · reindex_page(path) — 单条补偿
  · reindex_all()      — 全量对账
  · Milvus 不可用时跳过向量同步（优雅降级）
```

---

## 五、事实提取流程

```
用户消息 + 对话历史 + 检索结果
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  _extract_key_facts()                                        │
│                                                              │
│  ① 构建 Prompt                                               │
│     · 用户消息                                               │
│     · 对话历史摘要（最近 6 条，200字/条）                     │
│     · 知识库检索结果（top 5）                                │
│     · 现有 User Memory（冲突检测）                           │
│     · 现有 Session Memory（冲突检测）                        │
│     · PydanticOutputParser 格式说明                          │
│                                                              │
│  ② 调用 LLM                                                  │
│     · 优先 with_structured_output（Function Calling）        │
│     · 降级 PydanticOutputParser（code fence 提取）           │
│                                                              │
│  ③ Pydantic 校验                                             │
│     · ExtractedFact 模型约束                                 │
│     · confidence 范围 0.0 ~ 1.0                              │
│     · type / scope 枚举校验                                  │
│                                                              │
│  ④ 按 scope 分流                                             │
│     · scope=session → merge_session_key_facts() → 去重+淘汰 │
│     · scope=user    → merge_user_memory()       → 去重+淘汰 │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、事实类型分类

| type | scope | 说明 | 示例 |
|------|-------|------|------|
| `user_preference` | user | 用户明确表达的个人偏好 | "我喜欢 Python" / "我偏好简洁的回答" |
| `user_habit` | user | 用户的行为习惯 | "我习惯先写测试" / "我喜欢详细解释" |
| `project_context` | session | 当前项目的上下文 | "这个项目使用 Java" / "我们用 MongoDB" |
| `tech_constraint` | session | 当前的技术约束 | "必须兼容 Python 3.9" / "不能用外部依赖" |
| `task_goal` | session | 当前任务目标 | "正在实现登录功能" / "需要优化查询性能" |

---

## 七、Human-in-the-Loop 流程

```
decide 节点输出 decision (action != "none")
        │
        ▼
execute 节点: interrupt({}) ──→ 图暂停，state 存入 SQLite checkpoint
        │
        ▼
前端收到 decision (SSE)
        │
        ├─ 用户确认 → POST /confirm {thread_id, confirm: true}
        │       │
        │       ▼
        │   resume_and_execute()
        │   graph.ainvoke(Command(resume=True))
        │       │
        │       ▼
        │   interrupt() 返回 True
        │   → sync_manager 执行 CRUD
        │   → Markdown → Milvus+BM25 → Git
        │
        └─ 用户取消 → POST /confirm {thread_id, confirm: false}
                │
                ▼
            interrupt() 返回 False → 返回 cancelled
```

---

## 八、存储结构

### Session Memory（sessions 表）

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '新对话',
    key_facts TEXT DEFAULT '[]',          -- JSON: list[dict]
    active_eval_task_id TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### User Memory（user_memory 表）

```sql
CREATE TABLE user_memory (
    id TEXT PRIMARY KEY DEFAULT 'default',
    facts TEXT DEFAULT '[]',              -- JSON: list[dict]
    updated_at TIMESTAMP
);
```

### Messages（messages 表）

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,                   -- 'user' / 'assistant'
    content TEXT NOT NULL,
    wiki_results TEXT,                    -- JSON
    extraction TEXT,                      -- JSON
    created_at TIMESTAMP
);
```

---

## 九、关键设计决策

### 1. 为什么 Session Memory 和 User Memory 分开？

```
Session A: "我使用 Java"    → Session Memory A: project_context
Session B: "我喜欢 Python"  → User Memory: user_preference

分开存储：
· Session A 的 Java 不会污染 Session B
· Session B 的 Python 偏好跨 session 持久生效
· LLM 判断 scope，而非规则匹配
```

### 2. 为什么用置信度淘汰而非 FIFO？

```
FIFO 问题：
  第 1 条: "用户偏好 Python" (confidence=0.9)  ← 最早，可能被淘汰
  第 20 条: "用户说了你好" (confidence=0.3)     ← 最新，保留

置信度淘汰：
  按 confidence 排序，保留最高的 20/30 条
  "用户偏好 Python" 永远不会被淘汰
```

### 3. 为什么用六层压缩而非单一方案？

```
单层截断（如只用滑动窗口）：
  → 丢失旧对话中的重要上下文

单层 LLM 压缩（如 ConversationSummaryMemory）：
  → 每轮多一次 LLM 调用，延迟和成本翻倍

六层组合：
  ①②③ 滑动窗口 — 零成本，保证最近对话完整
  ④ 字符预算   — 零成本，控制 context 长度
  ⑤ LLM 提炼   — 复用 search 节点，零额外调用
  ⑥ 分块截断   — 写入时一次性处理
```

### 4. 为什么不用 LangChain Memory 类？

| 原因 | 说明 |
|------|------|
| 作用域不匹配 | Memory 绑定 Chain，但本项目多节点共享 history |
| 持久化不兼容 | LangChain 用内存/Redis，本项目用 SQLite |
| 已有替代 | key_facts + user_memory = 手动实现的 SummaryMemory |
| 避免额外调用 | 不需要每轮多一次 LLM 压缩调用 |

---

## 十、核心文件索引

| 文件 | 职责 |
|------|------|
| `agent/context_retriever.py` | 四路记忆检索 + 预算裁剪组装 |
| `agent/graph.py` | 事实提取 + LLM 消息构建 + 二次截断 |
| `agent/knowledge_agent.py` | 知识库 CRUD 决策（四层上下文检索） |
| `session/store.py` | Session/User Memory CRUD + get_recent_messages |
| `routers/chat.py` | 入口层：滑动窗口截断 + history 构建 |
| `agent/tools/query_rewriter.py` | Query 改写 Pipeline（检索优化） |
| `agent/tools/search_tools.py` | 混合检索（Milvus + BM25 + Reranker） |
| `agent/tools/sync_manager.py` | 四端同步管理器（Markdown + Milvus + BM25 + Git） |
| `config.py` | HISTORY_MAX_TURNS 等全局配置 |
