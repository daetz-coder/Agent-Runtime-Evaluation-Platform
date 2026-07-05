# Wiki Agent 技术难点深度解析

> 本文档剖析 Wiki Agent 项目中的 10 个核心技术难点，每个难点包含：问题本质、为什么难、现有解法、关键代码、以及学习建议。

---

## 目录

- [难点 1：四端数据一致性（SyncManager）](#难点-1四端数据一致性syncmanager)
- [难点 2：混合检索的 RRF 融合与重排](#难点-2混合检索的-rrf-融合与重排)
- [难点 3：LangGraph Human-in-the-Loop 中断恢复](#难点-3langgraph-human-in-the-loop-中断恢复)
- [难点 4：三路上下文的预算裁剪](#难点-4三路上下文的预算裁剪)
- [难点 5：Query 改写的多策略路由与相似度校验](#难点-5query-改写的多策略路由与相似度校验)
- [难点 6：LLM 输出的鲁棒 JSON 解析](#难点-6llm-输出的鲁棒-json-解析)
- [难点 7：SSE 流式输出与异步队列的协调](#难点-7sse-流式输出与异步队列的协调)
- [难点 8：优雅降级——每一条路径都可能失败](#难点-8优雅降级每一条路径都可能失败)
- [难点 9：评估中间件的解耦设计](#难点-9评估中间件的解耦设计)
- [难点 10：环境监控的增量索引同步](#难点-10环境监控的增量索引同步)
- [总结：难点之间的依赖关系](#总结难点之间的依赖关系)

---

## 难点 1：四端数据一致性（SyncManager）

### 问题本质

Wiki 的每一条知识同时存在于 **4 个存储系统** 中：

```
Markdown 文件  ←→  Milvus 向量库  ←→  BM25 倒排索引  ←→  Git 版本库
  (人类可读)       (语义检索)        (关键词检索)        (变更历史)
```

任何一个写操作（create/update/delete）都必须保证这四端一致。

### 为什么难

1. **没有分布式事务**：四个系统各自独立，无法用一个事务保证原子性
2. **失败不可预测**：Milvus 可能连接超时，Git 可能冲突，任何一步失败都需要处理
3. **外部修改**：用户可能直接用编辑器修改 Markdown 文件，系统需要感知变化
4. **性能与一致性的权衡**：同步更新四端会增加延迟，但异步又可能导致短暂不一致

### 现有解法

```python
# sync_manager.py — WikiSyncManager.create()

def create(self, path, title, content, tags, source, git_message):
    # ① 写 Markdown 文件（先写磁盘，失败则不继续）
    page = service.create_page(path, WikiPageCreate(...))

    # ② 同步到 Milvus + BM25（try-catch 隔离，失败不回滚 Markdown）
    self._sync_to_vector_store(path, title, content, tags)

    # ③ Git 提交（失败不回滚前两步）
    git_service.commit_changes(git_message, files=[path])
```

**关键设计**：
- **顺序执行**：Markdown → Milvus+BM25 → Git，每步独立 try-catch
- **优雅降级**：Milvus 不可用时跳过向量同步，BM25 不可用时跳过关键词索引
- **不回滚**：任何一步失败不影响已完成的步骤（最终一致性，非强一致性）
- **env_monitor 补偿**：外部文件变化通过轮询检测，自动触发索引同步

### 难在哪里

这个设计的难点不在于代码本身，而在于**一致性模型的选择**：

| 方案 | 优点 | 缺点 | 本项目选择 |
|------|------|------|-----------|
| 强一致性（分布式事务） | 数据永远一致 | 复杂、性能差、需要 2PC | ❌ |
| 最终一致性 + 补偿 | 简单、性能好 | 短暂不一致窗口 | ✅ |
| 写前日志（WAL） | 可恢复 | 实现复杂 | ❌ |

项目选择了**最终一致性**：允许短暂不一致，通过 env_monitor 轮询补偿。这是工程上的务实选择。

### 学习建议

> 先读 `crud_tools.py`（理解调用方），再读 `sync_manager.py`（理解实现），最后读 `env_monitor.py`（理解补偿机制）。

---

## 难点 2：混合检索的 RRF 融合与重排

### 问题本质

单一检索方式都有缺陷：

| 方式 | 优点 | 缺点 |
|------|------|------|
| 语义搜索（Milvus） | 理解同义词、语义相似 | 对精确关键词不敏感 |
| 关键词搜索（BM25） | 精确匹配、速度快 | 不理解同义词 |
| Cross-Encoder 重排 | 精度最高 | 速度最慢，不能直接检索 |

需要将三种方式组合，取长补短。

### 为什么难

1. **RRF 融合公式**：`score(d) = Σ 1/(k + rank_i(d) + 1)`，需要理解倒数秩融合的数学原理
2. **候选数量的平衡**：召回太少会漏掉好结果，召回太多会增加重排开销
3. **重排模型的加载**：BGE-reranker-base 模型约 1GB，首次加载慢，需要预热
4. **去重逻辑**：语义搜索和 BM25 可能返回同一文档的不同 chunk，需要按 path 去重

### 现有解法

```python
# search_tools.py — hybrid_search()

def hybrid_search(query, limit=5):
    # 候选数 = 最终数 × 3（给重排留足够候选）
    recall_limit = max(limit * settings.RERANK_CANDIDATE_MULTIPLIER, limit * 2)

    # ① 两路召回
    semantic_results = semantic_search(query, recall_limit)
    keyword_results = keyword_search(query, recall_limit)

    # ② RRF 融合
    merged = _rrf_merge(semantic_results, keyword_results)

    # ③ Cross-Encoder 重排
    return rerank_results(query, merged, top_k=limit)


def _rrf_merge(semantic_results, keyword_results, rrf_k=60):
    # 按 path 去重，保留最高分
    best_result = {}
    for result in semantic_results:
        if result["path"] not in best_result:
            best_result[result["path"]] = result
    for result in keyword_results:
        if result["path"] not in best_result:
            best_result[result["path"]] = result

    # 计算 RRF 分数
    rrf_scores = {}
    for rank, result in enumerate(semantic_results):
        rrf_scores.setdefault(result["path"], 0.0)
        rrf_scores[result["path"]] += 1.0 / (rrf_k + rank + 1)
    for rank, result in enumerate(keyword_results):
        rrf_scores.setdefault(result["path"], 0.0)
        rrf_scores[result["path"]] += 1.0 / (rrf_k + rank + 1)

    # 按 RRF 分数排序
    merged = [{**best_result[path], "score": score} for path, score in rrf_scores.items()]
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged
```

### RRF 融合的数学原理

```
假设有两个排序列表：

语义搜索排序：[A, B, C, D]     （rank 0, 1, 2, 3）
BM25 排序：   [B, D, A, E]     （rank 0, 1, 2, 3）

RRF 分数计算（k=60）：
  A: 1/(60+0+1) + 1/(60+2+1) = 0.0164 + 0.0159 = 0.0323
  B: 1/(60+1+1) + 1/(60+0+1) = 0.0161 + 0.0164 = 0.0325  ← 最高
  C: 1/(60+2+1)               = 0.0159
  D: 1/(60+3+1) + 1/(60+1+1) = 0.0156 + 0.0161 = 0.0317
  E:               1/(60+3+1) = 0.0156

最终排序：[B, A, D, C, E]
```

**关键洞察**：RRF 不需要归一化分数，只需要排名。这使得不同检索方式的分数可以直接融合，无需关心分数尺度差异。

### 学习建议

> 先理解 BM25 的 TF-IDF 原理（`bm25_index.py`），再理解向量相似度（`vector_store.py`），最后看 RRF 融合（`search_tools.py`）。重排部分可以先跳过，理解了前两步再看。

---

## 难点 3：LangGraph Human-in-the-Loop 中断恢复

### 问题本质

Agent 在 `decide` 节点决定要对知识库执行操作（create/update/delete）时，不能直接执行——需要用户确认。这意味着：

1. Agent 执行到一半需要**暂停**
2. 将决策结果返回给前端
3. 用户确认后，从**暂停点恢复**执行
4. 恢复时需要还原完整的执行状态

### 为什么难

1. **状态序列化**：暂停时需要将整个 `WikiState` 序列化到 SQLite checkpoint
2. **异步恢复**：恢复时需要从 checkpoint 反序列化状态，从暂停点继续
3. **并发安全**：同一个 thread_id 可能被多次 resume，需要防止重复执行
4. **前端协调**：前端需要保存 thread_id，确认时传回后端

### 现有解法

```python
# graph.py — execute 节点

async def execute(state: WikiState, config: RunnableConfig) -> WikiState:
    # interrupt() 会暂停执行，将当前状态保存到 checkpoint
    user_confirmed = interrupt({})

    # 当 resume_and_execute() 调用 graph.ainvoke(Command(resume=True)) 时
    # LangGraph 从 checkpoint 恢复状态，interrupt() 返回 True
    if not user_confirmed:
        return {**state, "action_result": {"status": "cancelled"}}

    # 执行 CRUD 操作
    decision = state.get("decision")
    result = crud_tools.create_knowledge(...)
    return {**state, "action_result": result}


# graph.py — resume_and_execute()

async def resume_and_execute(thread_id, confirm, session_id=None):
    graph = await get_wiki_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # Command(resume=confirm) 恢复 checkpoint，interrupt() 返回 confirm 的值
    result = await graph.ainvoke(Command(resume=confirm), config)
    return {"status": "ok", "result": result.get("action_result")}
```

### 执行流程图

```
第一次调用 (run_chat_stream):
  search → respond → decide → execute
                              │
                              ▼
                         interrupt({})  ← 暂停，状态保存到 checkpoint
                              │
                              ▼
                         返回 decision 给前端

第二次调用 (resume_and_execute):
  从 checkpoint 恢复 → execute 继续
                              │
                              ▼
                         interrupt() 返回 True/False
                              │
                              ▼
                         执行/取消 CRUD → END
```

### 难在哪里

1. **checkpoint 存储**：LangGraph 的 `AsyncSqliteSaver` 需要将完整的 state（包括消息列表、检索结果等）序列化为 JSON 存入 SQLite
2. **thread_id 管理**：前端需要保存 thread_id，后端需要根据 thread_id 找到对应的 checkpoint
3. **评估任务关联**：resume 时需要复用当前会话的评估 task_id，避免创建重复评估任务

### 学习建议

> 先理解 LangGraph 的 StateGraph 基础概念，再看 `interrupt()` 和 `Command(resume=...)` 的用法，最后看 `resume_and_execute()` 的完整流程。

---

## 难点 4：三路上下文的预算裁剪

### 问题本质

LLM 的上下文窗口是有限的。系统需要将三路记忆（RAG 检索结果、长期记忆 key_facts、对话历史）组装成一个上下文块，但不能超过预算。

### 为什么难

1. **优先级冲突**：三路记忆哪个更重要？如何分配预算？
2. **动态裁剪**：某路记忆可能很长，需要动态调整其他路的预算
3. **信息密度**：裁剪时不能丢失关键信息，但又必须控制长度
4. **key_facts 累积**：key_facts 会随对话不断增加，需要去重和淘汰

### 现有解法

```python
# context_retriever.py — build_context_block()

MAX_HISTORY_CHARS = 1000   # 对话历史预算
MAX_WIKI_CHARS = 1500      # RAG 检索结果预算
MAX_FACTS_CHARS = 500      # 长期记忆预算
# 总预算 ≈ 3000 字符

def build_context_block(ctx):
    blocks = []
    budget = MAX_HISTORY_CHARS + MAX_WIKI_CHARS + MAX_FACTS_CHARS  # ~3000

    # 优先级 1: key_facts（固定保留，最重要）
    if ctx.key_facts:
        facts_text = "\n".join(f"{i}. {f}" for i, f in enumerate(ctx.key_facts, 1))
        if len(facts_text) > MAX_FACTS_CHARS:
            facts_text = facts_text[:MAX_FACTS_CHARS] + "..."
        blocks.append(f"[长期记忆]\n{facts_text}")
        budget -= len(facts_text)  # 扣除已用预算

    # 优先级 2: wiki_results（RAG 检索结果）
    if ctx.wiki_results:
        wiki_lines = []
        used = 0
        for r in ctx.wiki_results:
            line = f"- {r['title']} ({r['path']}): {r['snippet']}"
            if used + len(line) > min(MAX_WIKI_CHARS, budget - 200):  # 动态预算
                break
            wiki_lines.append(line)
            used += len(line)
        blocks.append("[知识库搜索结果]\n" + "\n".join(wiki_lines))
        budget -= used

    # 优先级 3: history_summary（对话历史，优先级最低）
    if ctx.history_summary:
        remaining = min(MAX_HISTORY_CHARS, budget - 100)  # 动态预算
        if remaining > 50:
            hist = ctx.history_summary[:remaining] + "..."
            blocks.append(f"[对话历史]\n{hist}")

    return "\n\n".join(blocks)
```

### 预算分配策略

```
总预算: 3000 字符

┌─────────────────────────────────────────────┐
│ 优先级 1: key_facts（500 字符，固定保留）     │  ← 最重要，不参与动态分配
├─────────────────────────────────────────────┤
│ 优先级 2: wiki_results（1500 字符）          │  ← 动态：实际用多少扣多少
├─────────────────────────────────────────────┤
│ 优先级 3: history_summary（1000 字符）       │  ← 动态：用剩余预算
└─────────────────────────────────────────────┘

如果 key_facts 用了 300 字符 → wiki_results 最多用 1500，history 最多用 1000
如果 key_facts 用了 500 字符 → wiki_results 最多用 1500，history 最多用 1000
如果 wiki_results 用了 1200 字符 → history 最多用 1000
```

### key_facts 的累积与淘汰

```python
# store.py — merge_session_key_facts()

async def merge_session_key_facts(session_id, new_facts):
    existing = await get_session_key_facts(session_id)

    # 去重（忽略大小写）
    seen = {f.strip().lower() for f in existing}
    merged = list(existing)
    for fact in new_facts:
        normalized = fact.strip().lower()
        if normalized and normalized not in seen:
            merged.append(fact.strip())
            seen.add(normalized)

    # 淘汰：最多保留 20 条（保留最新的）
    if len(merged) > 20:
        merged = merged[-20:]

    # 持久化到 SQLite
    await db.execute("UPDATE sessions SET key_facts = ? WHERE id = ?",
                     (json.dumps(merged), session_id))
    return merged
```

### 学习建议

> 先理解三路记忆分别是什么（`context_retriever.py` 顶部注释），再看 `build_context_block()` 的预算分配逻辑，最后看 `merge_session_key_facts()` 的累积淘汰机制。

---

## 难点 5：Query 改写的多策略路由与相似度校验

### 问题本质

用户的原始查询往往不适合直接检索：

| 原始查询 | 问题 | 改写策略 |
|---------|------|---------|
| "它怎么优化？" | 含代词，不知道"它"是什么 | 指代消解 |
| "介绍一下向量数据库" | 太笼统 | Multi-Query（多角度改写） |
| "比较 Milvus 和 Pinecone 的差异" | 复杂问题 | Decompose（拆分子问题） |
| "那个能存向量的东西叫啥" | 模糊、口语化 | HyDE（假设性文档） |

### 为什么难

1. **分类准确性**：LLM 分类器可能分错类，导致使用错误的改写策略
2. **改写质量**：改写后的 query 可能偏离原始语义
3. **相似度校验**：需要判断改写是否保留了原始语义
4. **多查询合并**：改写后产生多个 query，每个都要检索，结果需要合并去重

### 现有解法

```python
# query_rewriter.py — rewrite_query()

async def rewrite_query(query, chat_history):
    # Step 1: 上下文补齐（检测到代词才触发）
    working_query = query
    if chat_history and Contextualizer.needs_contextualize(query):
        working_query = await Contextualizer.contextualize(query, chat_history)

    # Step 2: 路由分类
    query_type = await QueryClassifier.classify(working_query)
    # → direct / simple / complex / ambiguous

    # Step 3: 按分类执行改写策略
    if query_type == QueryType.DIRECT:
        rewritten = await QueryRewriter.direct(working_query)        # [q]
    elif query_type == QueryType.SIMPLE_FACTUAL:
        rewritten = await QueryRewriter.multi_query(working_query)   # [q, q', q'', q''']
    elif query_type == QueryType.COMPLEX:
        rewritten = await QueryRewriter.decompose(working_query)     # [q, q1, q2]
    elif query_type == QueryType.AMBIGUOUS:
        rewritten = await QueryRewriter.hyde(working_query)          # [q, hypothetical_doc]

    # Step 4: 相似度校验（过滤掉偏离原始语义的改写）
    validated = SimilarityValidator.validate(working_query, rewritten, threshold=0.7)

    return validated
```

### 相似度校验的原理

```python
# SimilarityValidator.validate()

def validate(original, rewritten_list, threshold=0.7):
    original_vec = generate_embedding(original)  # 原始 query 的向量

    validated = []
    for q in rewritten_list:
        if q == original:
            validated.append(q)
            continue
        q_vec = generate_embedding(q)
        sim = cosine_similarity(original_vec, q_vec)  # 余弦相似度
        if sim >= threshold:  # ≥ 0.7 才保留
            validated.append(q)
        else:
            print(f"过滤低相似度改写 (sim={sim:.3f}): {q}")

    return validated if validated else [original]  # 全部被过滤则返回原始
```

**关键洞察**：相似度校验是一道安全网——即使 LLM 改写得不好，也能通过向量相似度过滤掉偏离语义的改写。

### 学习建议

> 先理解四种改写策略的适用场景，再看 `QueryClassifier` 的分类逻辑，最后看 `SimilarityValidator` 的校验机制。这是整个检索系统中最"智能"的部分。

---

## 难点 6：LLM 输出的鲁棒 JSON 解析

### 问题本质

LLM 的输出是自由文本，不是结构化 JSON。即使 Prompt 要求返回 JSON，LLM 也可能：
- 在 JSON 前后加上解释文字
- 用 markdown code fence 包裹
- 返回格式错误的 JSON
- 返回空内容

### 为什么难

1. **不可预测**：每次调用 LLM 的输出格式可能不同
2. **容错要求高**：解析失败会导致整个评估流程中断
3. **多种格式**：需要支持裸 JSON、fenced JSON、嵌套 JSON 等

### 现有解法

```python
# knowledge_agent.py — decide_action()

# 路径 1（推荐）：with_structured_output
structured_llm = llm.with_structured_output(KnowledgeDecision)
chain = prompt | structured_llm
result = await chain.ainvoke(inputs)
# → KnowledgeDecision(action="create", title="JWT", content="...")

# 路径 2（降级）：PydanticOutputParser（LLM 不支持 function calling 时）
response = await llm.ainvoke([HumanMessage(content=prompt)])
raw_text = (response.content or "").strip()
decision = parser.parse(raw_text)  # PydanticOutputParser
```

```python
# base.py (evaluators) — _parse_json_from_llm()

@staticmethod
def _parse_json_from_llm(content: str) -> Optional[Dict[str, Any]]:
    # 策略 1: fenced code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略 2: 平衡大括号（从第一个 { 开始，找配对的 }）
    start = content.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(content[start:i+1])
                    except json.JSONDecodeError:
                        break

    # 策略 3: Greedy fallback（第一个 { 到最后一个 }）
    start = content.find("{")
    end = content.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

    return None
```

### 三种策略的对比

| 策略 | 适用场景 | 风险 |
|------|---------|------|
| Fenced code block | LLM 用 markdown 包裹 JSON | 可能匹配到错误的 fence |
| Balanced braces | JSON 前后有文字 | 正确性最高，但实现复杂 |
| Greedy fallback | 兜底方案 | 可能匹配到错误的 `{...}` |

### 学习建议

> 这个难点不在于算法复杂度，而在于**对 LLM 输出的容错思维**。建议收集真实 LLM 输出样本，测试三种策略的覆盖率。

---

## 难点 7：SSE 流式输出与异步队列的协调

### 问题本质

用户发消息后，需要实时看到 AI 的回复（逐 token 显示）。这需要：

1. LangGraph 异步执行
2. 通过 SSE（Server-Sent Events）推送给前端
3. 执行过程中产生多种事件（content、wiki_results、extraction、status）

### 为什么难

1. **生产者-消费者协调**：LangGraph 是生产者，SSE 是消费者，需要 asyncio.Queue 协调
2. **生命周期管理**：Graph 执行完成前，SSE 连接需要保持
3. **异常传播**：Graph 内部异常需要通过 Queue 传递给 SSE 消费者
4. **取消机制**：用户关闭页面时，需要取消正在执行的 Graph

### 现有解法

```python
# graph.py — run_chat_stream()

async def run_chat_stream(user_message, chat_history, session_id=None):
    graph = await get_wiki_graph()
    queue = asyncio.Queue()  # 事件队列

    config = {
        "configurable": {
            "thread_id": thread_id,
            "event_queue": queue,  # 注入到 Graph 状态中
            "chat_history": chat_history,
            "session_id": session_id,
        }
    }

    # 后台任务：执行 Graph，将事件推入 Queue
    async def _run_graph():
        try:
            await queue.put({"type": "evaluation_task", "task_id": eval_task_id})
            result = await graph.ainvoke(initial_state, config)
            await queue.put({"type": "_done", "result": result})
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)  # 哨兵值，表示结束

    task = asyncio.create_task(_run_graph())

    # 主协程：从 Queue 读取事件，yield 给 SSE
    try:
        while True:
            event = await queue.get()
            if event is None or event.get("type") == "_done":
                break
            yield event  # → SSE data: {...}
    finally:
        if not task.done():
            task.cancel()
```

### 事件流图

```
Graph 执行                    asyncio.Queue                  SSE 输出
──────────                    ─────────────                  ────────
search 节点                   ──→ {type: "status"}           ──→ data: {"type":"status"}
  ├─ retrieve_context()
  └─ record_retrieval()

respond 节点                  ──→ {type: "content", text}    ──→ data: {"type":"content"}
  └─ astream() 逐 token       ──→ {type: "content", text}    ──→ data: {"type":"content"}
                              ──→ {type: "content", text}    ──→ data: {"type":"content"}
                              ...

decide 节点                   ──→ {type: "extraction"}       ──→ data: {"type":"extraction"}

完成                          ──→ {type: "_done"}            ──→ data: {"type":"done"}
                              ──→ None (哨兵)                ──→ 连接关闭
```

### 学习建议

> 先理解 asyncio.Queue 的生产者-消费者模型，再看 `run_chat_stream()` 的 `asyncio.create_task()` + `yield` 模式。这是 Python 异步编程的经典模式。

---

## 难点 8：优雅降级——每一条路径都可能失败

### 问题本质

系统依赖多个外部组件（Milvus、Redis、Git、LLM API），任何一个都可能不可用。系统需要在部分组件不可用时仍能正常工作。

### 为什么难

1. **失败路径多**：每个组件可能在任何时候失败
2. **降级策略不同**：不同组件的降级方式不同
3. **不能静默吞异常**：需要记录日志，但不能中断主流程
4. **用户体验**：降级后功能受限，但核心功能不受影响

### 现有解法

| 组件 | 不可用时的行为 | 降级策略 |
|------|--------------|---------|
| Milvus | 语义搜索降级为 BM25 | `search_tools.py: semantic_search()` 失败时 fallback 到 `keyword_search()` |
| BM25 | 关键词搜索不可用 | `search_tools.py: keyword_search()` 返回空列表 |
| Redis | 无缓存直接读写数据库 | `cache.py: cache_get()` 返回 None，`cache_set()` 返回 False |
| Git | 跳过版本提交 | `git_service.py: commit_changes()` 返回 None |
| Reranker | 使用 RRF 排序结果 | `reranker.py: rerank_results()` 返回原始候选 |
| Query Rewrite | 直接使用原始 query | `query_rewriter.py: rewrite_query()` 返回 [query] |
| LLM API | 返回空结果或默认值 | `knowledge_agent.py` 返回 action="none" |
| Embedding 模型 | 返回零向量 | `embeddings.py` 返回 [0.0] * 512 |

### 关键代码示例

```python
# search_tools.py — semantic_search()

def semantic_search(query, limit=5):
    try:
        store = get_vector_store()
        if not store.available:
            return keyword_search(query, limit)  # 降级到 BM25

        embedding = generate_embedding(query)
        results = store.search(embedding, limit=limit * 3)
        # ... 处理结果
        return formatted[:limit]
    except Exception as e:
        print(f"[搜索] 语义搜索失败: {e}")
        return keyword_search(query, limit)  # 异常时降级到 BM25
```

```python
# embeddings.py — generate_embedding()

def generate_embedding(text):
    model = get_embedding_model()
    if model is None:
        return [0.0] * settings.EMBEDDING_DIM  # 模型不可用时返回零向量
    try:
        return model.encode(text).tolist()
    except Exception:
        return [0.0] * settings.EMBEDDING_DIM  # 异常时返回零向量
```

### 学习建议

> 这个难点是**工程思维**的体现。建议关注每个 `try-except` 块的处理方式：是记录日志、返回默认值、还是降级到备选方案。

---

## 难点 9：评估中间件的解耦设计

### 问题本质

Wiki Agent 需要将每一步执行轨迹提交给评估引擎，但业务代码（`graph.py`）不应该直接依赖 SDK。需要一个中间层来解耦。

### 为什么难

1. **关注点分离**：业务逻辑和评估逻辑应该独立演化
2. **自动采集 vs 手动记录**：SDK 可以自动采集 LLM 调用和节点执行，但检索细节需要手动记录
3. **生命周期管理**：评估会话的 start/record/finish 需要在正确的时间点调用
4. **透明性**：业务代码不应该感知评估的存在

### 现有解法

通过 SDK TrajectoryCollector 的生命周期钩子实现解耦：

```
graph.py (业务代码)          hooks.py (钩子层)              SDK TrajectoryCollector
─────────────────          ───────────────────           ───────────────────────
emit_session_start() ────→ collector.start_async() ────→ 创建评估任务
emit_retrieval()     ────→ collector.record_retrieval() → 记录检索
emit_key_facts()     ────→ collector.record_memory_write() → 记录事实
emit_response()      ────→ collector.record(EVIDENCE)   → 记录回复
emit_session_end()   ────→ collector.finish_async()     → flush + 触发评估
```

```python
# hooks.py — 委托给 SDK TrajectoryCollector

try:
    from sdk.collector import ActionType, get_collector
except ImportError:
    get_collector = None  # SDK 不可用时降级

async def emit_retrieval(query, results, duration_ms):
    collector = get_collector()
    if collector and collector.enabled:
        collector.record_retrieval(query, results, duration_ms=duration_ms)
```

### 解耦效果

```python
# graph.py — 业务代码不直接依赖 SDK，只调用 hooks

from app.wiki_agent.hooks import emit_retrieval, emit_response, emit_session_end

# 在关键节点调用 emit
await emit_retrieval(query, results, duration_ms)
await emit_response(session_id, response)
await emit_session_end(session_id)
```

### 学习建议

> 理解 SDK TrajectoryCollector 的 record/start/finish 生命周期，再看 hooks.py 如何委托，最后看 graph.py 如何在关键节点调用。

---

## 难点 10：环境监控的增量索引同步

### 问题本质

用户可能直接用编辑器（如 VS Code）修改 knowledge/ 目录下的 Markdown 文件，绕过了系统的 API。系统需要感知这些外部变化，并自动同步索引。

### 为什么难

1. **变化检测**：需要高效检测哪些文件发生了变化
2. **增量同步**：不能每次都全量重建索引，需要只同步变化的文件
3. **删除检测**：文件被删除时，需要清理对应的向量和 BM25 索引
4. **性能**：轮询间隔太短浪费 CPU，太长则同步延迟高

### 现有解法

```python
# env_monitor.py — EnvironmentMonitor

class EnvironmentMonitor:
    def __init__(self, poll_interval=5.0):
        self._snapshots = {}  # path → FileSnapshot(path, hash, mtime, size)
        self._callbacks = []  # 变化回调列表

    async def _detect_changes(self):
        """检测文件变化"""
        current = self._scan_all()  # 扫描所有 .md 文件的 hash
        changes = []

        # 检测新增和修改
        for path, snapshot in current.items():
            if path not in self._snapshots:
                changes.append(FileChangeEvent(path, ChangeType.CREATED))
            elif snapshot.hash != self._snapshots[path].hash:
                changes.append(FileChangeEvent(path, ChangeType.MODIFIED))

        # 检测删除
        for path in self._snapshots:
            if path not in current:
                changes.append(FileChangeEvent(path, ChangeType.DELETED))

        self._snapshots = current  # 更新快照
        return changes
```

### 自动同步回调

```python
# env_monitor.py — auto_sync_callback()

async def auto_sync_callback(changes):
    """检测到变化时自动同步索引"""
    for change in changes:
        if change.change_type == ChangeType.DELETED:
            sync_manager._delete_from_vector_store(change.path)  # 清理索引
        else:
            sync_manager.reindex_page(change.path)  # 重建该页面的索引
```

### 性能优化

```python
# 使用 MD5 hash 而不是读取文件内容比较
def _scan_all(self):
    snapshots = {}
    for md_file in self._knowledge_dir.rglob("*.md"):
        stat = md_file.stat()
        content = md_file.read_bytes()
        file_hash = hashlib.md5(content).hexdigest()  # 快速 hash
        snapshots[rel_path] = FileSnapshot(path=rel_path, hash=file_hash, ...)
    return snapshots
```

### 学习建议

> 先理解 `FileSnapshot` 的 hash 比较机制，再看 `_detect_changes()` 的变化检测逻辑，最后看 `auto_sync_callback()` 如何调用 `sync_manager` 同步索引。

---

## 总结：难点之间的依赖关系

```
                    ┌─────────────────────────────────────┐
                    │  难点 8: 优雅降级                    │
                    │  （贯穿所有难点的工程思维）            │
                    └──────────────────┬──────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────┐            ┌─────────────────┐            ┌───────────────┐
│ 难点 2:       │            │ 难点 4:         │            │ 难点 1:       │
│ 混合检索      │            │ 上下文预算裁剪   │            │ 四端一致性    │
│ RRF + 重排    │            │                 │            │ SyncManager   │
└───────┬───────┘            └────────┬────────┘            └───────┬───────┘
        │                             │                             │
        │ 依赖                        │ 依赖                        │ 依赖
        ▼                             ▼                             ▼
┌───────────────┐            ┌─────────────────┐            ┌───────────────┐
│ 难点 5:       │            │ 难点 6:         │            │ 难点 10:      │
│ Query 改写    │            │ LLM JSON 解析   │            │ 环境监控      │
└───────┬───────┘            └────────┬────────┘            └───────┬───────┘
        │                             │                             │
        └──────────────────────────────┼──────────────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────┐
                    │  难点 3: LangGraph HITL 中断恢复     │
                    │  难点 7: SSE 流式输出                 │
                    │  难点 9: 评估中间件解耦               │
                    └─────────────────────────────────────┘
```

### 学习顺序建议

| 阶段 | 难点 | 前置知识 | 预计时间 |
|------|------|---------|---------|
| 1 | 难点 6: LLM JSON 解析 | Python JSON、正则表达式 | 30 min |
| 2 | 难点 1: 四端一致性 | 文件 I/O、Git 基础 | 45 min |
| 3 | 难点 10: 环境监控 | 文件系统、hash | 20 min |
| 4 | 难点 2: 混合检索 | 向量相似度、BM25 基础 | 60 min |
| 5 | 难点 5: Query 改写 | LLM 调用、Embedding | 45 min |
| 6 | 难点 4: 上下文裁剪 | Token 概念、优先级队列 | 30 min |
| 7 | 难点 8: 优雅降级 | 异常处理、try-catch | 30 min |
| 8 | 难点 7: SSE 流式输出 | asyncio、Queue、SSE | 45 min |
| 9 | 难点 3: HITL 中断恢复 | LangGraph checkpoint | 60 min |
| 10 | 难点 9: 评估中间件 | SDK 适配器、装饰器模式 | 30 min |
