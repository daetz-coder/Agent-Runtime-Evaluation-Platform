# Wiki Agent 学习指南

> 从零开始学习 Wiki Agent 项目的完整路径：先看什么、再看什么、每个文件的重点是什么、有哪些技术难点。

---

## 目录

- [项目一句话概括](#项目一句话概括)
- [学习路线总览](#学习路线总览)
- [第一阶段：全局认知（15 分钟）](#第一阶段全局认知15-分钟)
- [第二阶段：数据存储层（20 分钟）](#第二阶段数据存储层20-分钟)
- [第三阶段：检索系统（30 分钟）](#第三阶段检索系统30-分钟)
- [第四阶段：Query 改写（15 分钟）](#第四阶段query-改写15-分钟)
- [第五阶段：Agent 编排（30 分钟）](#第五阶段agent-编排30-分钟)
- [第六阶段：数据同步（15 分钟）](#第六阶段数据同步15-分钟)
- [第七阶段：API 与前端（20 分钟）](#第七阶段api-与前端20-分钟)
- [第八阶段：评估集成（10 分钟）](#第八阶段评估集成10-分钟)
- [技术难点索引](#技术难点索引)
- [核心文件速查表](#核心文件速查表)

---

## 项目一句话概括

Wiki Agent 是一个 **基于 RAG 的个人知识库问答系统**：用户用自然语言提问，系统从知识库中检索相关文档，结合对话历史和长期记忆，由 LLM 生成回答，并在对话过程中自动识别有价值的知识写入知识库。

---

## 学习路线总览

```
第一阶段: config.py → bootstrap.py → schemas.py
           全局认知：系统由什么组成，启动时做了什么

第二阶段: service.py → database.py → store.py
           数据存储：Markdown 文件怎么存，会话怎么管理

第三阶段: embeddings.py → chunker.py → vector_store.py
           → bm25_index.py → reranker.py → search_tools.py
           检索系统：从 query 到搜索结果的完整链路

第四阶段: query_rewriter.py
           Query 改写：如何优化用户的搜索查询

第五阶段: context_retriever.py → knowledge_agent.py → graph.py
           Agent 编排：系统如何"思考"和"决策"

第六阶段: sync_manager.py → crud_tools.py → env_monitor.py
           数据同步：写操作如何保证四端一致

第七阶段: chat.py → wiki.py → git_service.py
           API 与前端：用户如何与系统交互

第八阶段: hooks.py + SDK TrajectoryCollector
           评估集成：通过生命周期钩子接入评估平台
```

---

## 第一阶段：全局认知（15 分钟）

> **目标**：知道系统由哪些组件组成，启动时做了什么，核心数据模型是什么。

### 1.1 `app/wiki_agent/config.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | 所有可配置参数，了解系统有哪些组件 |
| 重点 | LLM 配置（DeepSeek/ZhipuAI）、Milvus 路径、Embedding 模型、Rerank 开关、Query Rewrite 开关 |
| 关键认知 | 系统由 LLM + Milvus + BM25 + Git + SQLite 组成，每个都可以独立开关 |

**读完你应该知道**：
- 系统用 DeepSeek 或 ZhipuAI 作为 LLM
- 知识库以 Markdown 文件存储在 `data/wiki_agent/knowledge/`
- 向量数据库用 Milvus Lite（本地文件，无需独立服务）
- Embedding 模型是 BGE-small-zh-v1.5（512 维）

### 1.2 `app/wiki_agent/bootstrap.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | 启动流程，理解各组件的初始化顺序 |
| 重点 | `startup()` 函数的 6 个步骤 |
| 关键认知 | 启动时会自动创建目录、复制种子数据、初始化数据库、同步索引、预加载模型、启动监控 |

**读完你应该知道**：
```
startup() 的 6 个步骤：
1. ensure_directories()      → 创建运行时目录
2. seed_knowledge_if_empty()  → 知识库为空时复制示例文件
3. init_db()                  → 初始化 SQLite 表
4. sync_indexes_if_needed()   → 首次启动同步 Milvus + BM25
5. preload_reranker_if_enabled() → 预加载重排模型
6. start_env_monitor()        → 启动文件变化监控
```

### 1.3 `app/wiki_agent/wiki/schemas.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | 所有 Pydantic 数据模型，理解系统的核心概念 |
| 重点 | `WikiPage`（知识条目）、`WikiNode`（目录树）、`WikiGraph`（知识图谱）、`WikiDiff`（版本 diff） |
| 关键认知 | 这些模型是整个系统的"语言"，所有 API 和服务都围绕它们展开 |

**读完你应该知道**：
- 一个知识条目有 path、title、content、summary、category、tags、links、source
- 目录树是递归的 `WikiNode`（is_dir + children）
- 知识图谱由 `GraphNode`（节点）和 `GraphLink`（边）组成

---

## 第二阶段：数据存储层（20 分钟）

> **目标**：理解数据是怎么存的——知识条目以 Markdown 文件存储，会话以 SQLite 存储。

### 2.1 `app/wiki_agent/wiki/service.py` ⭐

| 关注点 | 说明 |
|--------|------|
| 读什么 | Markdown 文件的 CRUD、frontmatter 解析、搜索、WikiLinks |
| 重点 | `_parse_frontmatter()`（YAML 元数据解析）、`get_tree()`（递归目录树）、`search_pages()`（全文搜索）、`extract_wikilinks()`（`[[链接]]` 解析） |
| 关键认知 | 知识条目就是 Markdown 文件，元数据存在文件头部的 YAML frontmatter 中 |

**读完你应该知道**：
```markdown
---
title: 条目标题
tags: [标签1, 标签2]
category: 技术/编程语言
links: [关联条目路径]
---
正文内容...
```

- `get_tree()` 递归扫描目录，构建树形结构
- `search_pages()` 基于关键词匹配 + 权重评分（标题 3 分 > 文件名 2 分 > 正文 1 分）
- `[[向量索引]]` 这种语法会被解析为知识库内部链接

### 2.2 `app/wiki_agent/database.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | SQLite 表结构 |
| 重点 | `sessions` 表（id, name, key_facts, active_eval_task_id）和 `messages` 表（role, content, wiki_results, extraction） |
| 关键认知 | 会话和消息用 SQLite 存储，key_facts 是会话级的长期记忆 |

### 2.3 `app/wiki_agent/session/store.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | 会话管理、key_facts 累积、Redis 缓存策略 |
| 重点 | `merge_session_key_facts()`（去重 + 淘汰，最多 20 条）、`get_session()`（带 Redis 缓存） |
| 关键认知 | key_facts 是 LLM 从对话中提取的关键事实，累积后作为长期记忆注入上下文 |

**读完你应该知道**：
- 每轮对话后，LLM 会提取 0~5 条 key_facts
- key_facts 去重后累积，超过 20 条时淘汰最早的
- Redis 缓存会话数据，写操作后自动失效

---

## 第三阶段：检索系统（30 分钟）

> **目标**：理解从用户 query 到最终搜索结果的完整链路。这是 RAG 的核心。

### 3.1 `app/wiki_agent/agent/tools/embeddings.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | Embedding 模型加载和向量生成 |
| 重点 | `get_embedding_model()`（单例加载）、`generate_embedding()`（文本 → 512 维向量） |
| 关键认知 | Embedding 是将文本转换为数字向量的过程，语义相似的文本向量距离近 |

**读完你应该知道**：
- 模型是 BAAI/bge-small-zh-v1.5，输出 512 维向量
- 单例模式，全局缓存模型实例
- 失败时返回零向量（512 个 0.0），不中断流程

### 3.2 `app/wiki_agent/agent/tools/chunker.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | 文档分块策略 |
| 重点 | `chunk_markdown()`（LangChain RecursiveCharacterTextSplitter）、分层分隔符 |
| 关键认知 | 长文档需要切分成小块才能向量化，分块质量直接影响检索效果 |

**读完你应该知道**：
- 默认 `chunk_size=500`，`chunk_overlap=50`
- 分隔符优先级：`\n\n` → `\n` → `。` → `！` → `？` → `；` → `，` → 空格
- overlap 保证块之间有上下文重叠，避免信息在边界处丢失

### 3.3 `app/wiki_agent/agent/tools/vector_store.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | Milvus 向量存储的增删改查 |
| 重点 | `insert_chunks()`（批量插入）、`delete_by_path()`（按页面删除）、`search()`（向量相似度搜索） |
| 关键认知 | 每个知识条目被分成多个 chunk，每个 chunk 有一个 512 维向量 |

**读完你应该知道**：
- Collection Schema：chunk_id, vector, path, title, document, tags, chunk_index, total_chunks
- 搜索时返回 `1.0 - distance` 作为相似度分数（COSINE 距离）
- 同一页面的多个 chunk 按 path 去重，保留最高分

### 3.4 `app/wiki_agent/agent/tools/bm25_index.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | BM25 倒排索引的实现 |
| 重点 | `_tokenize()`（jieba 分词 + 停用词过滤）、`search()`（BM25 评分 + 按 path 去重）、`save()`/`load()`（pickle 持久化） |
| 关键认知 | BM25 是基于词频的精确匹配算法，与语义搜索互补 |

**读完你应该知道**：
- 用 jieba 做中文分词，过滤 78 个停用词和单字 token
- BM25Okapi 是 rank_bm25 库的实现
- 索引用 pickle 持久化到磁盘，首次访问时从 knowledge/ 目录全量重建

### 3.5 `app/wiki_agent/agent/tools/reranker.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | Cross-Encoder 重排器 |
| 重点 | `rerank_results()`（对 RRF 候选重新排序）、`resolve_rerank_model_id()`（本地模型路径解析） |
| 关键认知 | 重排是第二遍精排，比向量搜索更准但更慢，所以只对候选集重排 |

**读完你应该知道**：
- 模型是 BAAI/bge-reranker-base，基于 Cross-Encoder 架构
- 输入是 (query, document) 对，输出是相关性分数
- 失败时降级为 RRF 排序结果（优雅降级）

### 3.6 `app/wiki_agent/agent/tools/search_tools.py` ⭐⭐

| 关注点 | 说明 |
|--------|------|
| 读什么 | **混合搜索入口**，完整 Pipeline |
| 重点 | `hybrid_search()`（三阶段 Pipeline）、`_rrf_merge()`（RRF 融合公式）、`semantic_search()`（Milvus 搜索 + BM25 降级） |
| 关键认知 | 这是检索系统的核心——语义搜索 + BM25 → RRF 融合 → Cross-Encoder 重排 |

**读完你应该知道**：

```
hybrid_search(query, limit=5) 的完整流程：

1. 召回（候选数 = limit × 3）
   ├─ semantic_search(query) → Milvus 向量搜索
   └─ keyword_search(query) → BM25 关键词搜索

2. RRF 融合
   score(d) = Σ 1/(k + rank_i(d) + 1)  其中 k=60
   → 按 path 去重，保留最高分

3. Cross-Encoder 重排
   → 对 (query, document) 对打分
   → 返回 top_k 个结果
```

**技术难点**：
- RRF 融合不需要归一化分数，只需要排名——这使得不同检索方式的分数可以直接融合
- 候选数 = limit × RERANK_CANDIDATE_MULTIPLIER（默认 3），给重排留足够候选
- 语义搜索失败时自动降级到 BM25

---

## 第四阶段：Query 改写（15 分钟）

> **目标**：理解如何优化用户的搜索查询，提升检索召回率。

### 4.1 `app/wiki_agent/agent/tools/query_rewriter.py` ⭐

| 关注点 | 说明 |
|--------|------|
| 读什么 | 4 阶段 Query 改写 Pipeline |
| 重点 | `rewrite_query()`（主入口）、`Contextualizer`（指代消解）、`QueryClassifier`（4 分类路由）、`QueryRewriter`（4 种改写策略）、`SimilarityValidator`（相似度校验） |
| 关键认知 | 原始 query 往往不适合直接检索，需要改写优化 |

**读完你应该知道**：

```
rewrite_query(query, chat_history) 的 4 个阶段：

1. Contextualizer — 指代消解
   检测代词（它/这个/那个...）→ LLM 改写为自包含问题
   "它怎么优化？" → "Milvus 向量数据库怎么优化？"

2. QueryClassifier — 4 分类路由
   direct  → 简单明确，不改写
   simple  → 简单，Multi-Query 改写
   complex → 复杂，Decompose 拆分
   ambiguous → 模糊，HyDE 假设性文档

3. QueryRewriter — 按分类执行改写策略
   direct:    [q]
   simple:    [q, q', q'', q''']  （同义词 + 具体 + 抽象）
   complex:   [q, q1, q2]          （拆分为子问题）
   ambiguous: [q, hypothetical_doc] （生成假设性文档）

4. SimilarityValidator — 相似度校验
   对每个改写 query 计算与原始 query 的余弦相似度
   相似度 < 0.7 → 丢弃
```

**技术难点**：
- 分类器可能分错类 → 相似度校验是安全网
- 改写可能偏离原始语义 → 向量相似度过滤
- 全部被过滤时兜底返回原始 query

---

## 第五阶段：Agent 编排（30 分钟）

> **目标**：理解系统如何"思考"——用户消息进来后，系统如何检索、回复、决策、执行。

### 5.1 `app/wiki_agent/agent/context_retriever.py` ⭐

| 关注点 | 说明 |
|--------|------|
| 读什么 | 三路记忆的合并逻辑和预算裁剪 |
| 重点 | `retrieve_context()`（三路检索入口）、`build_context_block()`（预算裁剪组装） |
| 关键认知 | LLM 的上下文由三部分组成：RAG 检索结果 + 长期记忆 + 对话历史 |

**读完你应该知道**：

```
retrieve_context(query, chat_history, session_id) 的流程：

1. Query 改写 → rewrite_query()
2. 对每个改写 query 执行 hybrid_search() → 合并去重 → top 5
3. 获取 session key_facts（长期记忆）
4. 获取最近 10 条对话历史（短期记忆）
5. 返回 RetrievedContext

build_context_block(ctx) 的预算裁剪：

总预算 ~3000 字符
├─ 优先级 1: key_facts（500 字符，固定保留）
├─ 优先级 2: wiki_results（1500 字符，动态分配）
└─ 优先级 3: history_summary（1000 字符，用剩余预算）
```

**技术难点**：
- 预算是动态的——某路记忆用得少，其他路可以用更多
- key_facts 优先级最高——它是 LLM 自己提取的关键事实，最可靠
- 兜底：改写查询全部无结果时，用原始 query 再搜一次

### 5.2 `app/wiki_agent/agent/knowledge_agent.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | 知识库维护决策器 |
| 重点 | `decide_action()`（LLM 决策入口）、`KnowledgeDecision`（决策模型）、`DECIDE_PROMPT`（决策 Prompt） |
| 关键认知 | 对话结束后，LLM 会分析是否需要对知识库执行操作 |

**读完你应该知道**：
- 决策类型：create / update / delete / none
- 决策前会先 `hybrid_search()` 查找相关现有知识
- 用 with_structured_output 生成结构化决策（降级 PydanticOutputParser）
- Wiki 链接规则：content 中引用其他条目时用 `[[页面名称]]` 语法

### 5.3 `app/wiki_agent/agent/graph.py` ⭐⭐⭐

| 关注点 | 说明 |
|--------|------|
| 读什么 | **核心编排文件**，LangGraph 四节点工作流 |
| 重点 | `WikiState`（状态定义）、`search()`/`respond()`/`decide()`/`execute()`（四个节点）、`create_wiki_graph()`（图构建）、`run_chat_stream()`（SSE 流式入口）、`resume_and_execute()`（HITL 恢复） |
| 关键认知 | 整个对话流程由 LangGraph 编排：search → respond → decide → execute |

**读完你应该知道**：

```
LangGraph 工作流：

START → search → respond → (len > 50 ?) → decide → (action != none ?) → execute → END
                              ↓ no                ↓ no
                             END                 END

search 节点:
  ① retrieve_context() — 三路记忆检索
  ② record_retrieval() — 记录检索事件
  ③ _extract_key_facts() — LLM 提取 key_facts
  ④ merge_session_key_facts() — 累积到 session

respond 节点:
  ① _build_llm_messages() — 组装消息列表
  ② chat_llm.astream() — 流式生成回复
  ③ 逐 token 通过 queue 推送 SSE 事件

decide 节点:
  ① knowledge_agent.decide_action() — LLM 决策

execute 节点:
  ① interrupt({}) — 暂停，等待用户确认
  ② 用户确认后 → crud_tools 执行 CRUD
```

**技术难点**：
- **HITL 中断恢复**：`interrupt({})` 暂停 → checkpoint 保存 → `Command(resume=...)` 恢复
- **SSE 流式输出**：`asyncio.Queue` 协调 Graph 生产者和 SSE 消费者
- **key_facts 累积**：每轮对话提取新 facts，去重后累积到 session

---

## 第六阶段：数据同步（15 分钟）

> **目标**：理解写操作如何保证四端（Markdown + Milvus + BM25 + Git）一致。

### 6.1 `app/wiki_agent/agent/tools/sync_manager.py` ⭐⭐

| 关注点 | 说明 |
|--------|------|
| 读什么 | **四端同步管理器** |
| 重点 | `create()`/`update()`/`delete()`（CRUD 流程）、`_sync_to_vector_store()`（Milvus+BM25 同步）、`reindex_all()`（全量重建）、`rollback()`（Git 回滚 + 索引同步） |
| 关键认知 | 所有写操作必须经过此管理器，不允许绕过 |

**读完你应该知道**：

```
create() 的流程：
1. service.create_page()     → 写 Markdown 文件
2. _sync_to_vector_store()   → 分块 → 生成 embedding → 写 Milvus → 更新 BM25
3. git_service.commit_changes() → Git 提交

每步独立 try-catch：
- Markdown 写入失败 → 不继续
- Milvus 同步失败 → 跳过（降级），不影响 Markdown 和 Git
- Git 提交失败 → 跳过，不影响 Markdown 和 Milvus
```

**技术难点**：
- **最终一致性**：没有分布式事务，允许短暂不一致
- **优雅降级**：Milvus 不可用时跳过向量同步
- **env_monitor 补偿**：外部文件变化通过轮询检测，自动触发索引同步

### 6.2 `app/wiki_agent/agent/tools/crud_tools.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | Agent 的 CRUD 工具 |
| 重点 | `create_knowledge()`（路径生成 + 去重检查）、`update_knowledge()`、`delete_knowledge()` |
| 关键认知 | 这是 Agent 调用 sync_manager 的入口，路径自动生成（category/safe-title.md） |

### 6.3 `app/wiki_agent/agent/tools/env_monitor.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | 文件变化监控和自动索引同步 |
| 重点 | `EnvironmentMonitor`（轮询检测）、`_detect_changes()`（MD5 hash 比较）、`auto_sync_callback()`（变化回调） |
| 关键认知 | 用户直接编辑 Markdown 文件时，系统会自动感知并同步索引 |

**读完你应该知道**：
- 每 5 秒扫描 knowledge/ 目录下所有 .md 文件的 MD5 hash
- 检测到变化后调用 `sync_manager.reindex_page()` 重建索引
- 检测到删除后调用 `sync_manager._delete_from_vector_store()` 清理索引

---

## 第七阶段：API 与前端（20 分钟）

> **目标**：理解用户如何与系统交互。

### 7.1 `app/wiki_agent/routers/chat.py` ⭐

| 关注点 | 说明 |
|--------|------|
| 读什么 | 对话 API |
| 重点 | `chat_stream()`（SSE 流式对话）、`confirm_knowledge()`（HITL 确认）、`stream_response()`（SSE 事件生成） |
| 关键认知 | 前端通过 SSE 实时接收 AI 回复和知识提取结果 |

**读完你应该知道**：
- `POST /api/chat/stream` — SSE 流式对话，返回 `text/event-stream`
- `POST /api/chat/confirm` — HITL 确认/取消，调用 `resume_and_execute()`
- SSE 事件类型：content / wiki_results / extraction / status / error / done

### 7.2 `app/wiki_agent/routers/wiki.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | Wiki REST API |
| 重点 | CRUD 端点（经 sync_manager）、搜索、标签、知识图谱、导出、版本管理 |
| 关键认知 | 所有写操作都经过 sync_manager，确保四端一致 |

### 7.3 `app/wiki_agent/wiki/git_service.py`

| 关注点 | 说明 |
|--------|------|
| 读什么 | Git 版本管理 |
| 重点 | `commit_changes()`（提交）、`get_history()`（历史）、`get_structured_diff()`（结构化 diff）、`rollback()`（回滚） |
| 关键认知 | 每次写操作都会 Git 提交，支持查看历史和回滚 |

---

## 第八阶段：评估集成（10 分钟）

> **目标**：理解 Wiki Agent 如何接入评估平台，自动采集执行轨迹。

### 8.1 `app/wiki_agent/hooks.py` + SDK TrajectoryCollector ⭐

| 关注点 | 说明 |
|--------|------|
| 读什么 | 生命周期钩子——通过 SDK TrajectoryCollector 接入评估平台 |
| 重点 | `emit_session_start()`、`emit_retrieval()`、`emit_response()`、`emit_session_end()` |
| 关键认知 | 业务代码通过 emit 函数触发事件，SDK 不可用时自动降级为空操作 |

**读完你应该知道**：
- `collector.record_retrieval(query, results, ms)` → 记录检索事件
- `collector.record(EVIDENCE, {...})` → 记录回复
- `collector.start_async()` → 创建评估任务
- `collector.finish_async(auto_run=True)` → flush 轨迹，触发评估
- SDK 内置离线模式：平台不可达时本地缓冲，不阻塞 Agent

---

## 技术难点索引

详细解析见 [wiki-agent-difficult-points.md](wiki-agent-difficult-points.md)。

| # | 难点 | 核心挑战 | 对应文件 |
|---|------|---------|---------|
| 1 | 四端数据一致性 | Markdown + Milvus + BM25 + Git 无法用分布式事务 | `sync_manager.py` |
| 2 | 混合检索 RRF 融合 | 语义搜索 + BM25 的分数尺度不同 | `search_tools.py` |
| 3 | HITL 中断恢复 | interrupt() 暂停 → checkpoint → Command(resume=...) 恢复 | `graph.py` |
| 4 | 三路上下文预算裁剪 | 3000 字符预算内按优先级分配 | `context_retriever.py` |
| 5 | Query 改写多策略路由 | 指代消解 → 分类 → 4 种策略 → 相似度校验 | `query_rewriter.py` |
| 6 | LLM JSON 鲁棒解析 | 3 种策略：fenced → balanced braces → greedy | `knowledge_agent.py` |
| 7 | SSE 流式 + 异步队列 | asyncio.Queue 协调生产者和消费者 | `graph.py` |
| 8 | 优雅降级 | 每个组件都可能失败，需要独立降级策略 | 贯穿所有文件 |
| 9 | 生命周期钩子解耦 | 通过 SDK TrajectoryCollector 接入评估，hooks.py 解耦 | `hooks.py` |
| 10 | 环境监控增量同步 | MD5 hash 检测变化，自动重建索引 | `env_monitor.py` |

**建议学习顺序**：6 → 1 → 10 → 2 → 5 → 4 → 8 → 7 → 3 → 9

---

## 核心文件速查表

| 文件 | 行数 | 核心职责 | 复杂度 |
|------|------|---------|--------|
| `config.py` | ~60 | 全局配置 | ⭐ |
| `bootstrap.py` | ~175 | 启动引导 | ⭐ |
| `database.py` | ~65 | SQLite 表结构 | ⭐ |
| `schemas.py` | ~170 | Pydantic 数据模型 | ⭐ |
| `service.py` | ~580 | 知识条目 CRUD + 搜索 + 图谱 | ⭐⭐ |
| `git_service.py` | ~215 | Git 版本管理 | ⭐⭐ |
| `store.py` | ~345 | 会话存储 + key_facts | ⭐⭐ |
| `embeddings.py` | ~40 | Embedding 模型 | ⭐ |
| `chunker.py` | ~85 | 文档分块 | ⭐ |
| `vector_store.py` | ~350 | Milvus 向量存储 | ⭐⭐ |
| `bm25_index.py` | ~285 | BM25 倒排索引 | ⭐⭐ |
| `reranker.py` | ~158 | Cross-Encoder 重排 | ⭐⭐ |
| `search_tools.py` | ~132 | **混合搜索入口** | ⭐⭐⭐ |
| `query_rewriter.py` | ~360 | **Query 改写 Pipeline** | ⭐⭐⭐ |
| `context_retriever.py` | ~152 | **三路记忆合并** | ⭐⭐⭐ |
| `knowledge_agent.py` | ~117 | 知识库维护决策 | ⭐⭐ |
| `graph.py` | ~620 | **LangGraph 核心编排** | ⭐⭐⭐⭐ |
| `sync_manager.py` | ~346 | **四端同步管理器** | ⭐⭐⭐ |
| `crud_tools.py` | ~175 | Agent CRUD 工具 | ⭐⭐ |
| `env_monitor.py` | ~215 | 文件变化监控 | ⭐⭐ |
| `hooks.py` | ~95 | **生命周期钩子** | ⭐⭐ |
| `llm_factory.py` | ~45 | 统一 LLM 工厂 | ⭐ |
| `chat.py` | ~240 | 对话 API | ⭐⭐ |
| `wiki.py` | ~330 | Wiki REST API | ⭐⭐ |
| `debug.py` | ~365 | 调试 API | ⭐⭐ |
| `vector_admin.py` | ~70 | 向量管理 API | ⭐ |
| `vector_schemas.py` | ~55 | 向量管理模型 | ⭐ |

**必读 3 遍的文件**：
1. `graph.py` — 整个系统的编排核心
2. `search_tools.py` — RAG 检索的核心
3. `sync_manager.py` — 数据一致性的核心
