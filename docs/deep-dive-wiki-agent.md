# Wiki Agent — 技术深度剖析

> 面试用技术文档，聚焦业务场景、遇到的问题、解决方案和实现细节。

---

## 一、业务场景：为什么要做 Wiki Agent

### 1.1 背景

Wiki Agent 是一个 **RAG 知识库问答系统**，但它的定位不只是"问答"。它同时是评估平台的**真实 Agent 用例**——评估平台的 6 维评估体系就是在 Wiki Agent 的轨迹数据上验证的。

所以 Wiki Agent 有两个身份：
1. **独立产品**：团队知识库管理 + 智能问答
2. **评估平台的试验田**：提供真实的 Agent 轨迹数据，验证评估体系的有效性

### 1.2 核心业务场景

| 场景 | 用户操作 | Agent 行为 |
|------|----------|------------|
| 知识问答 | "项目的认证机制是怎么实现的？" | 检索知识库 → 生成回答 → 自动提取新知识 |
| 知识创建 | "帮我记录一下今天的会议决定" | LLM 生成内容 → HITL 确认 → 写入知识库 → 同步索引 |
| 知识更新 | "更新 OAuth 文档，加上 PKCE 支持" | 检索现有文档 → LLM 修改 → HITL 确认 → 更新 + 重新索引 |
| 知识图谱 | 浏览知识关联 | 构建 wikilink 有向图 → 前端可视化 |

---

## 二、核心技术难点与解决方案

### 2.1 难点一：四级混合检索的精度问题

**问题描述**：纯向量搜索对中文短查询效果差（语义鸿沟），纯关键词搜索无法处理同义词和语义扩展。

**解决方案：四级混合检索管线**（`search_tools.py`）

```
用户查询
    ↓ Query Rewriter（LLM 改写）
    生成 2-3 个语义等价的搜索 query
    ↓ 并行执行
    ┌─────────────────┐    ┌─────────────────┐
    │  语义搜索        │    │  BM25 关键词搜索  │
    │  (Milvus 向量库) │    │  (jieba 分词)     │
    │  BGE-small-zh   │    │  Okapi BM25      │
    └────────┬────────┘    └────────┬────────┘
             │                      │
             └──────┬───────────────┘
                    ↓
            RRF 融合（Reciprocal Rank Fusion）
            score(d) = Σ 1/(k + rank_i(d) + 1), k=60
                    ↓
            Cross-Encoder 重排序（可选）
            bge-reranker-base (~1GB)
                    ↓
            路径去重（同一文档的多个 chunk 只保留最高分）
                    ↓
            Top-K 结果
```

**关键技术决策**：

1. **RRF 而非加权融合**：RRF 只看排名不看原始分数，完美解决了 cosine similarity（0-1）和 BM25 TF-IDF 分数（无界）的量纲不一致问题。

2. **ThreadPoolExecutor 并行搜索**：语义搜索和 BM25 搜索在线程池中并行执行，然后 RRF 融合，最后可选 rerank。

3. **候选集过采样**：`recall_limit = max(limit * RERANK_CANDIDATE_MULTIPLIER, limit * 2)`，给 reranker 更多候选材料。

4. **优雅降级**：语义搜索失败 → 降级到关键词搜索；reranker 模型不可用 → 跳过 rerank 返回 RRF 顺序；embedding 模型加载失败 → 返回零向量，语义搜索返回空但 BM25 仍然可用。

**分块策略**（`chunker.py`）：
- 500 字符 chunk，50 字符 overlap
- 中文感知的分隔符优先级：`\n\n` → `\n` → `。` → `！` → `？` → `；` → `，`
- `keep_separator=True` 确保在中文句子边界断开，而不是在句子中间
- Embedding 时 title + chunk 拼接，确保向量同时捕获主题和内容

---

### 2.2 难点二：四路存储一致性问题

**问题描述**：Wiki Agent 的每次写操作需要同步到 4 个存储系统：Markdown 文件、Milvus 向量库、BM25 索引、Git 历史。没有分布式事务支持。

**解决方案：最终一致性 + 顺序写入**（`sync_manager.py`）

```python
async def sync_all(entry, content, category, tags):
    # 1. 写 Markdown（如果失败，后续全部跳过）
    await write_markdown_file(entry, content)

    # 2. 同步向量库（失败不回滚 Markdown）
    try:
        await sync_to_vector_store(entry, content)
    except Exception:
        logger.error("Vector sync failed, Markdown is still updated")

    # 3. 同步 BM25 索引（失败不回滚前两步）
    try:
        await sync_to_bm25(entry, content)
    except Exception:
        logger.error("BM25 sync failed")

    # 4. Git commit（失败不回滚前三步）
    try:
        await git_commit(entry)
    except Exception:
        logger.error("Git commit failed")
```

**关键设计决策**：

1. **明确选择最终一致性**：不追求强一致性，因为四个存储系统的事务语义不同，强行统一会增加大量复杂度。

2. **Delete-then-insert 策略**：更新时先删除旧 chunk，再插入新 chunk。这处理了 chunk 数量变化的情况（如文档变短了）。

3. **BM25 惰性重建**（`bm25_index.py`）：`_dirty` 标记控制是否需要重建索引，避免每次搜索都重新计算。BM25 索引通过 pickle 持久化到磁盘，冷启动时直接加载。

4. **全量重建能力**：`reindex_all()` 遍历所有 `.md` 文件，从头重建 Milvus 和 BM25。用于 bootstrap 和故障恢复。

5. **回滚机制**：`rollback()` 用 Git 恢复文件到指定 commit，然后重新索引该页面。

---

### 2.3 难点三：Human-in-the-Loop 的暂停/恢复

**问题描述**：Agent 生成了知识内容后，需要用户确认才能写入知识库。但 LangGraph 的执行是异步的，如何在 HTTP 请求-响应周期中实现"暂停等待用户确认"？

**解决方案：LangGraph interrupt + SQLite checkpoint**（`graph.py`）

```
用户发起聊天 → SSE 流式响应
    ↓
Agent 执行到 execute 节点
    ↓
graph.interrupt("请确认是否保存")  ← 暂停，状态序列化到 SQLite
    ↓
前端显示确认对话框
    ↓
用户点击确认 → POST /confirm {thread_id, confirm: true}
    ↓
graph.ainvoke(Command(resume=confirm), config)  ← 从 checkpoint 恢复
    ↓
执行 CRUD 操作 → 返回结果
```

**关键技术细节**：

1. **SQLite checkpointing**：`AsyncSqliteSaver` 在每个节点执行后持久化整个 `WikiState`，包括对话历史、检索结果、待确认内容。`interrupt()` 调用时状态被序列化到 `checkpoints.db`。

2. **SSE 流式解耦**：LangGraph 在后台 task 中执行，通过 `asyncio.Queue` 向 HTTP 响应流推送 token。这解耦了 Graph 执行（可能暂停）和 HTTP 响应（需要持续流式输出）。

3. **CRUD 失败自动重规划**：
   - create 失败（"已存在"）→ 自动重试为 update
   - update 失败（"不存在"）→ 自动重试为 create
   - 这是一个简单但有效的错误恢复策略

4. **单例 Graph + 懒初始化**：Graph 和 checkpointer 创建一次，跨请求复用。

---

### 2.4 难点四：预算感知的上下文组装

**问题描述**：Agent 有 4 个记忆来源（用户记忆、会话记忆、外部知识库、工作记忆），每个都有不同的优先级和大小。Token 预算有限，如何确保高优先级的记忆不被截断？

**解决方案：优先级预算裁剪**（`context_retriever.py`）

```
总预算 = 3000 字符
    ↓
┌─────────────────────────────────────────────────┐
│ 优先级 1: 用户记忆（跨会话持久事实）     600 字符 │  ← 永不截断
│ 优先级 2: 会话记忆（当前会话事实）       400 字符 │  ← 永不截断
│ 优先级 3: 外部知识库（RAG 检索结果）    1200 字符 │  ← 可能被截断
│ 优先级 4: 工作记忆（最近 10 条对话）     800 字符 │  ← 最先被截断
└─────────────────────────────────────────────────┘
```

**实现逻辑**：

```python
async def retrieve_context(query, session_id):
    budget = 600 + 400 + 1200 + 800  # 总预算 3000

    # 优先级 1: 用户记忆（永不截断）
    user_memory = await load_user_memory(session_id)
    budget -= len(user_memory)

    # 优先级 2: 会话记忆（永不截断）
    session_memory = await load_session_memory(session_id)
    budget -= len(session_memory)

    # 优先级 3: 知识库（预算不足时截断）
    wiki_results = await search_knowledge(query)
    if len(wiki_results) > budget:
        wiki_results = wiki_results[:budget]  # 截断
    budget -= len(wiki_results)

    # 优先级 4: 工作记忆（预算不足时截断）
    history = await load_recent_history(session_id)
    if len(history) > budget:
        history = history[:budget]  # 截断
```

**查询复杂度自适应**：

```python
complexity = classify_complexity(query)
if complexity == "TRIVIAL":
    # "你好"、"谢谢" → 跳过 RAG，只加载记忆
    pass
elif complexity == "SIMPLE":
    # "什么是 OAuth" → 语义搜索，跳过 rerank
    results = await semantic_search(query)
elif complexity == "COMPLEX":
    # "项目的认证机制有哪些安全考虑" → 完整四级管线
    results = await hybrid_search(query, with_rerank=True)
```

---

### 2.5 难点五：记忆系统的分层管理

**问题描述**：Agent 需要记住用户的偏好（跨会话）、当前对话的上下文（会话内）、以及从对话中提取的事实。如何分层管理这些记忆？

**解决方案：三层记忆架构**

```
┌─────────────────────────────────────────────────┐
│ 用户记忆（User Memory）                         │
│ - 存储：SQLite user_memory.facts                │
│ - 生命周期：永久                                 │
│ - 内容：用户偏好、技术栈、常用配置               │
│ - 示例："用户偏好 Python"、"项目用 PostgreSQL"    │
├─────────────────────────────────────────────────┤
│ 会话记忆（Session Memory）                      │
│ - 存储：SQLite session.key_facts                │
│ - 生命周期：单次会话                             │
│ - 内容：当前任务上下文、临时发现                 │
│ - 示例："这个 bug 的根因是类型转换错误"          │
├─────────────────────────────────────────────────┤
│ 工作记忆（Working Memory）                      │
│ - 存储：内存（最近 10 条消息）                   │
│ - 生命周期：当前对话                             │
│ - 内容：最近的对话历史                           │
└─────────────────────────────────────────────────┘
```

**事实提取流程**（`graph.py`）：

```python
# 1. 正则预过滤：简单消息跳过 LLM 调用
if is_simple_query(message):  # "你好"、"谢谢"、"什么是 X"
    return  # 不提取事实

# 2. LLM 提取事实 + 判定范围
facts = await llm.extract_facts(
    message=message,
    existing_user_memory=user_memory,
    existing_session_memory=session_memory,
)
# 每个 fact 有 scope 字段：user（跨会话）或 session（当前会话）

# 3. 异步写入（不阻塞主响应流）
asyncio.create_task(_store_memories(facts))
```

**关键设计决策**：

- **冲突感知提取**：prompt 中包含现有记忆，让 LLM 处理矛盾（偏好变化 vs 不同上下文）
- **异步 fire-and-forget**：`_store_memories()` 作为 `asyncio.create_task` 启动，不 await，记忆写入不阻塞主响应
- **双重 fallback 解析**：先用 `with_structured_output`（API 级 Schema 强制），失败后降级到 PydanticOutputParser（文本解析 + 重试）

---

### 2.6 难点六：Milvus Lite 的 gRPC 稳定性

**问题描述**：Milvus Lite（嵌入式模式）的 gRPC 默认 keepalive 设置过于激进，导致频繁 GOAWAY 错误。

**解决方案：环境变量调优 + 重试机制**（`vector_store.py`）

```python
# 在任何 gRPC import 之前设置环境变量
os.environ["GRPC_KEEPALIVE_TIME_MS"] = "120000"      # 默认 10s → 120s
os.environ["GRPC_KEEPALIVE_TIMEOUT_MS"] = "20000"     # 默认 20s → 20s
os.environ["GRPC_HTTP2_MIN_TIME_BETWEEN_PINGS_MS"] = "120000"
os.environ["GRPC_HTTP2_MAX_PINGS_WITHOUT_DATA"] = "0"
```

**重试机制**：

```python
async def _with_retry(operation, *args, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return await operation(*args)
        except Exception as e:
            if "GOAWAY" in str(e) or "ENHANCE_YOUR_CALM" in str(e):
                _client = None  # 强制重连
                continue
            raise
```

---

### 2.7 难点七：Reranker 模型的下载可靠性

**问题描述**：ModelScope 下载 bge-reranker-base（~1GB）时，有时会把权重文件留在临时目录（`._____temp`），导致模型加载失败。

**解决方案：临时文件提升**（`reranker.py`）

```python
def promote_temp_weights(model_dir):
    """检测 ModelScope 下载的临时文件，将有效的权重文件提升到模型根目录。"""
    for item in os.listdir(model_dir):
        if item.endswith("._____temp"):
            temp_path = os.path.join(model_dir, item)
            # 检查临时目录中的文件大小（≥900MB 才认为是有效的权重文件）
            for f in os.listdir(temp_path):
                fpath = os.path.join(temp_path, f)
                if os.path.getsize(fpath) > 900 * 1024 * 1024:
                    shutil.move(fpath, os.path.join(model_dir, f))
```

**优雅降级**：reranker 加载失败时，`rerank_results` 静默返回 RRF 顺序，不抛异常。系统继续工作，只是精度略低。

---

## 三、LangGraph 图结构

```
┌──────────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐
│  search  │────▶│ respond  │────▶│  decide   │────▶│ execute  │
│ (检索)   │     │ (生成)   │     │ (HITL决策)│     │ (CRUD)   │
└──────────┘     └──────────┘     └───────────┘     └──────────┘
                    │                  │                    │
                    │ (简单查询)       │ (无需操作)         │
                    ▼                  ▼                    ▼
                   END               END                  END
```

**search 节点**：
- 查询复杂度分类 → TRIVIAL 跳过 RAG
- 并行加载用户记忆 + 会话记忆
- 完整四级检索管线（对 COMPLEX 查询）
- Query Rewriter 改写查询

**respond 节点**：
- 组装上下文（预算感知裁剪）
- SSE 流式生成回答
- LLM 提取事实（异步 fire-and-forget）

**decide 节点**：
- LLM 判断是否需要 CRUD 操作
- 无需操作 → END
- 需要操作 → execute

**execute 节点**：
- `graph.interrupt()` 暂停等待用户确认
- 用户确认后执行 CRUD
- 失败时自动重规划（create↔update 互转）

---

## 四、与评估平台的集成

Wiki Agent 的每一步都通过 `TrajectoryCollector` 记录轨迹：

```python
# search 节点
collector.record("retrieval", query=query, result_count=len(results), retrieved_docs=results)
collector.record("evidence", evidence_type="rag", sources={...})

# respond 节点
collector.record("think", thought=llm_response)
collector.record("memory_write", key="user_preference", value="Python", memory_type="user")

# decide 节点
collector.record("tool_decision", decision="create", reason="新知识")

# execute 节点
collector.record("tool_call", tool_name="create_knowledge", input={...})
collector.record("tool_result", success=True, duration_ms=120)
```

这些轨迹数据被评估平台的 6 个评估器分析，形成质量分数。这就是"评估平台的试验田"的含义——Wiki Agent 产生的真实轨迹数据驱动了评估体系的验证和迭代。

---

## 五、性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 检索 Top-1 准确率 | 75% | BGE-small-zh + RRF 混合检索 |
| MRR（Mean Reciprocal Rank） | 0.825 | 检索质量指标 |
| 首 token 延迟 | <500ms | SSE 流式输出 |
| 单次检索耗时 | ~200ms | 语义搜索 + BM25 并行 |
| Rerank 额外开销 | ~300ms | bge-reranker-base 推理 |
| 知识库索引大小 | ~1000 篇文档 | Milvus Lite + BM25 pickle |
| 记忆提取开销 | ~1s | LLM 调用，异步不阻塞响应 |
