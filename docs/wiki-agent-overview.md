# Wiki Agent 项目全面解析

> 基于 RAG（检索增强生成）的个人知识库问答系统，集成于 Agent Runtime Evaluation Platform。

---

## 目录

- [一、项目概述](#一项目概述)
- [二、技术栈](#二技术栈)
- [三、目录结构与文件功能](#三目录结构与文件功能)
  - [3.1 核心配置层](#31-核心配置层)
  - [3.2 Agent 智能体层](#32-agent-智能体层)
  - [3.3 工具层（tools）](#33-工具层tools)
  - [3.4 Wiki 知识管理层](#34-wiki-知识管理层)
  - [3.5 会话管理层](#35-会话管理层)
  - [3.6 API 路由层](#36-api-路由层)
  - [3.7 前端层](#37-前端层)
  - [3.8 示例与模型资源](#38-示例与模型资源)
- [四、架构设计](#四架构设计)
  - [4.1 整体架构图](#41-整体架构图)
  - [4.2 LangGraph 对话流程图](#42-langgraph-对话流程图)
  - [4.3 混合检索 Pipeline](#43-混合检索-pipeline)
  - [4.4 三端同步机制](#44-三端同步机制)
  - [4.5 三路记忆体系](#45-三路记忆体系)
  - [4.6 Query 改写 Pipeline](#46-query-改写-pipeline)
- [五、数据流](#五数据流)
  - [5.1 用户对话数据流](#51-用户对话数据流)
  - [5.2 知识库 CRUD 数据流](#52-知识库-crud-数据流)
  - [5.3 评估数据流](#53-评估数据流)
- [六、API 接口一览](#六api-接口一览)
- [七、关键设计决策](#七关键设计决策)

---

## 一、项目概述

Wiki Agent 是一个**基于 RAG 的个人知识库问答系统**，作为 Agent Runtime Evaluation Platform 的三大核心子系统之一。它的定位是：

```
Agent Runtime（运行 Agent） → 评估引擎（评估质量） → Wiki Agent（知识沉淀）
```

**核心能力**：
1. **知识库管理**：以 Markdown 文件为存储单元，支持 CRUD、分类、标签、版本管理（Git）、知识图谱
2. **智能问答**：通过 LangGraph 编排 Agent 工作流，结合向量检索 + BM25 关键词检索 + Cross-Encoder 重排的三阶段混合检索
3. **自动知识沉淀**：在对话过程中自动识别有价值的知识，经 Human-in-the-Loop 确认后写入知识库
4. **运行时评估**：通过 SDK 自动采集 Agent 的每一步执行轨迹，提交给评估引擎进行多维度质量评分

---

## 二、技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| Agent 编排 | LangGraph + LangChain | ReAct 循环、对话状态管理、Human-in-the-Loop |
| 向量检索 | Milvus Lite | 语义相似度搜索（512 维 BGE 向量） |
| 关键词检索 | rank_bm25 + jieba | BM25 倒排索引、中文分词 |
| 重排模型 | BAAI/bge-reranker-base | Cross-Encoder 精排 |
| Embedding | BAAI/bge-small-zh-v1.5 | 中文文本向量化（512 维） |
| LLM | DeepSeek / ZhipuAI GLM | 对话生成、决策推理、标签生成、Query 改写 |
| 数据库 | SQLite (aiosqlite) | 会话存储、消息持久化 |
| 版本管理 | GitPython | 知识库 Git 版本控制 |
| 后端框架 | FastAPI | REST API + SSE 流式输出 |
| 前端 | Vue 3 + TypeScript | 知识库浏览、对话交互、知识图谱可视化 |

---

## 三、目录结构与文件功能

```
app/wiki_agent/
├── __init__.py                    # 包初始化（空）
├── config.py                      # 全局配置（路径、模型、参数）
├── bootstrap.py                   # 启动引导（目录创建、种子数据、索引同步）
├── database.py                    # SQLite 数据库初始化（会话表、消息表）
│
├── agent/                         # Agent 智能体层
│   ├── __init__.py
│   ├── graph.py                   # ★ LangGraph 主编排（search → respond → decide → execute）
│   ├── knowledge_agent.py         # 知识库维护决策器（create/update/delete/none）
│   ├── context_retriever.py       # 统一上下文检索（合并三路记忆）
│   ├── auto_tagger.py             # LLM 自动标签生成
│   ├── eval_middleware.py         # 评估中间件（SDK 桥接层）
│   └── tools/                     # Agent 工具集
│       ├── __init__.py
│       ├── search_tools.py        # 混合搜索入口（语义 + BM25 + RRF + 重排）
│       ├── vector_store.py        # Milvus 向量存储（增删改查）
│       ├── bm25_index.py          # BM25 倒排索引（jieba 分词）
│       ├── chunker.py             # 文档分块器（Markdown/PDF/Word/TXT）
│       ├── embeddings.py          # Embedding 模型加载与向量生成
│       ├── reranker.py            # Cross-Encoder 重排器
│       ├── query_rewriter.py      # Query 改写 Pipeline（上下文补齐 + 分类 + 多策略改写 + 校验）
│       ├── crud_tools.py          # 知识条目 CRUD 工具
│       ├── sync_manager.py        # ★ 四端同步管理器（Markdown + Milvus + BM25 + Git）
│       └── env_monitor.py         # 环境监控器（文件变化自动同步索引）
│
├── wiki/                          # Wiki 知识管理层
│   ├── __init__.py
│   ├── service.py                 # 知识条目 CRUD 服务（文件读写、搜索、图谱、分类）
│   ├── git_service.py             # Git 版本管理（提交、历史、diff、回滚）
│   ├── schemas.py                 # Pydantic 数据模型（WikiPage、WikiNode、WikiGraph 等）
│   └── vector_schemas.py          # 向量管理 API 的数据模型
│
├── session/                       # 会话管理层
│   ├── __init__.py
│   └── store.py                   # 会话存储服务（SQLite + Redis 缓存）
│
├── routers/                       # API 路由层
│   ├── __init__.py
│   ├── chat.py                    # 对话 API（流式/非流式、HITL 确认、会话管理）
│   ├── wiki.py                    # Wiki API（CRUD、搜索、标签、图谱、导出、版本管理）
│   ├── debug.py                   # 调试 API（内部状态可视化）
│   └── vector_admin.py            # 向量管理 API + Web UI
│
├── seed/                          # 种子知识库内容
│   └── knowledge/                 # 首次启动时的示例 Markdown 文件
│
└── static/                        # 静态资源
    └── vector_admin.html          # 向量管理 Web UI
```

### 3.1 核心配置层

#### `config.py` — 全局配置

**功能**：使用 `pydantic_settings` 管理所有可配置参数，支持 `.env` 文件覆盖。

**关键配置项**：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥 |
| `ZHIPUAI_API_KEY` | — | 智谱 GLM API 密钥（可选，优先使用） |
| `KNOWLEDGE_DIR` | `data/wiki_agent/knowledge` | 知识库 Markdown 文件存储目录 |
| `MILVUS_URI` | `data/wiki_agent/milvus.db` | Milvus 向量数据库路径 |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | Embedding 模型 |
| `EMBEDDING_DIM` | 512 | 向量维度 |
| `RERANK_ENABLED` | `true` | 是否启用 Cross-Encoder 重排 |
| `QUERY_REWRITE_ENABLED` | `true` | 是否启用 Query 改写 |
| `GIT_ENABLED` | `true` | 是否启用 Git 版本管理 |
| `EVAL_ENABLED` | `true` | 是否启用运行时评估 |

**设计要点**：
- 优先使用 ZhipuAI（如果配置了 API Key），否则回退到 DeepSeek
- 所有路径均为绝对路径，基于 `PROJECT_ROOT` 计算
- Milvus 使用 Lite 模式（本地文件），无需独立服务

#### `bootstrap.py` — 启动引导

**功能**：平台启动时初始化 Wiki Agent 的所有资源。

**启动流程**：
1. `ensure_directories()` — 创建运行时目录（knowledge/、milvus.db/、chat.db/）
2. `seed_knowledge_if_empty()` — 如果知识库为空，复制种子 Markdown 文件
3. `init_db()` — 初始化 SQLite 数据库表
4. `sync_indexes_if_needed()` — 首次启动时同步 Milvus + BM25 索引
5. `preload_reranker_if_enabled()` — 预加载 Cross-Encoder 重排模型
6. `start_env_monitor()` — 启动环境监控器（5 秒轮询检测文件变化）

#### `database.py` — 数据库初始化

**功能**：管理 SQLite 数据库的表结构和连接。

**表结构**：
- `sessions` — 会话表（id, name, key_facts, active_eval_task_id, timestamps）
- `messages` — 消息表（id, session_id, role, content, wiki_results, extraction, timestamp）

---

### 3.2 Agent 智能体层

#### `agent/graph.py` — ★ LangGraph 主编排

**功能**：Wiki Agent 的核心编排文件，定义了完整的对话工作流。

**状态定义 (`WikiState`)**：
```python
class WikiState(TypedDict):
    user_message: str          # 用户消息
    wiki_results: list[dict]   # 知识库检索结果
    wiki_text: str | None      # 检索结果文本（向后兼容）
    ai_response: str           # AI 回复
    decision: dict | None      # 知识库操作决策
    action_result: dict | None # 操作执行结果
    stage: str                 # 当前阶段
    retrieved_context: dict | None  # 统一检索上下文
```

**四个节点**：

| 节点 | 职责 |
|------|------|
| `search` | 统一检索三路记忆（KB + key_facts + history），提取 key_facts |
| `respond` | 基于上下文流式生成 AI 回复（通过 SSE 逐 token 推送） |
| `decide` | 分析对话内容，决定是否需要对知识库执行 CRUD 操作 |
| `execute` | Human-in-the-Loop：等待用户确认后执行知识库操作 |

**条件路由**：
- `respond` → `should_decide` → 如果回复长度 > 50 字 → `decide`，否则 → `END`
- `decide` → `should_execute` → 如果决策不是 `none` → `execute`，否则 → `END`

**两个运行入口**：
- `run_chat_stream()` — SSE 流式对话（通过 asyncio.Queue 推送事件）
- `run_chat_invoke()` — 非流式对话（同步等待结果）
- `resume_and_execute()` — 从 checkpoint 恢复，执行 HITL 确认

#### `agent/knowledge_agent.py` — 知识库维护决策器

**功能**：用 LLM 分析对话内容，决定是否需要对知识库执行操作。

**决策类型**：
- `create` — 对话中有新的长期价值知识 → 创建条目
- `update` — 对话对现有知识进行了补充或修正 → 更新条目
- `delete` — 用户明确要求删除 → 删除条目
- `none` — 普通问答、闲聊 → 不操作

**工作流程**：
1. 调用 `search_tools.hybrid_search()` 查找相关现有知识
2. 读取相关条目的正文内容（前 500 字预览）
3. 构建 Prompt（用户消息 + AI 回复 + 现有知识 + 格式指令）
4. 用 LLM 生成结构化 `KnowledgeDecision`（通过 PydanticOutputParser）

#### `agent/context_retriever.py` — 统一上下文检索

**功能**：合并三路记忆源，为 LLM 提供完整的上下文。

**三路记忆**：

| 记忆类型 | 来源 | 说明 |
|----------|------|------|
| External KB (RAG) | `hybrid_search()` | 知识库混合检索结果 |
| Long-term Memory | `session.key_facts` | 会话累积的关键事实 |
| Short-term Memory | `chat_history` | 最近 10 条对话消息 |

**预算管理**：总预算约 3000 字符，按优先级分配：
1. key_facts（500 字符，固定保留）
2. wiki_results（1500 字符）
3. history_summary（1000 字符）

#### `agent/auto_tagger.py` — 自动标签生成

**功能**：用 LLM 为知识条目自动生成 3-5 个标签。

**特性**：
- 优先复用已有标签
- 标签 2-5 个中文字或英文字
- 输出 JSON 格式

#### `agent/eval_middleware.py` — 评估中间件

**功能**：Wiki Agent 与评估 SDK 的唯一桥接层。业务代码不直接 import SDK。

**核心职责**：
- `instrument_graph()` — 用 SDK 包裹 LangGraph，自动采集节点执行/状态变化
- `wrap_llm()` — 用 SDK 包裹 LLM，自动采集 LLM 调用
- `start_session()` — 启动评估会话，创建 task，生成结构化计划
- `finish_session()` — 结束评估会话，flush 轨迹
- `record_retrieval()` — 记录检索事件（SDK 无法自动采集）
- `record_key_facts()` — 记录 key_facts 为 memory_write 事件

---

### 3.3 工具层（tools）

#### `tools/search_tools.py` — 混合搜索入口

**功能**：提供语义搜索、BM25 搜索、RRF 混合搜索的统一入口。

**三种搜索模式**：

| 模式 | 函数 | 说明 |
|------|------|------|
| 语义搜索 | `semantic_search()` | Milvus 向量相似度搜索 |
| 关键词搜索 | `keyword_search()` | BM25 倒排索引搜索 |
| 混合搜索 | `hybrid_search()` | RRF 融合 + Cross-Encoder 重排 |

**`hybrid_search()` Pipeline**：
1. `semantic_search()` — 召回 `limit * RERANK_CANDIDATE_MULTIPLIER` 个候选
2. `keyword_search()` — 召回同样数量的候选
3. `_rrf_merge()` — RRF（Reciprocal Rank Fusion）倒数秩融合
4. `rerank_results()` — Cross-Encoder 精排，返回 top-K

#### `tools/vector_store.py` — Milvus 向量存储

**功能**：封装 Milvus Lite 的所有操作。

**核心类 `MilvusVectorStore`**：
- `insert_chunks()` — 批量插入文档块（含向量、路径、标题、内容、标签）
- `delete_by_path()` — 按页面路径删除所有块
- `search()` — 向量相似度搜索
- `list_paths()` — 列出所有已索引的页面路径
- `list_chunks()` — 分页查询块（支持路径/关键词过滤）
- `delete_all()` — 清空集合
- `get_stats()` — 获取统计信息

**Collection Schema**：
```
id: STRING (chunk_id, 如 "path/to/page.md#chunk0")
vector: FLOAT_VECTOR (512 维)
path: STRING (页面路径)
title: STRING
document: STRING (块内容)
tags: STRING (逗号分隔)
chunk_index: INT
total_chunks: INT
updated_at: STRING
```

#### `tools/bm25_index.py` — BM25 倒排索引

**功能**：基于 jieba 分词 + rank_bm25 的中文关键词检索。

**核心类 `BM25Index`**：
- `add_document()` — 添加文档的所有块到索引
- `remove_document()` — 按路径移除文档
- `search()` — BM25 搜索（按 path 去重，保留最高分块）
- `save()` / `load()` — 持久化/加载索引（pickle）
- `build_from_knowledge_dir()` — 从 knowledge/ 目录全量重建

**分词策略**：
- 使用 jieba 中文分词
- 过滤停用词（78 个常见中文停用词）
- 过滤单字 token

#### `tools/chunker.py` — 文档分块器

**功能**：将文档拆分为适合向量化的文本块。

**支持格式**：Markdown、PDF（pypdf）、Word（python-docx）、TXT

**分块策略**：
- 使用 LangChain `RecursiveCharacterTextSplitter`
- 分层分隔符：`\n\n` → `\n` → `。` → `！` → `？` → `；` → `，` → `. ` → `! ` → `? ` → `; ` → `, ` → ` ` → ``
- 默认 `chunk_size=500`，`chunk_overlap=50`
- 兜底方案：简单按字符数切分

#### `tools/embeddings.py` — Embedding 模型

**功能**：加载和使用 BGE-small-zh-v1.5 模型生成文本向量。

**特性**：
- 单例模式（全局缓存模型实例）
- 优先使用本地模型路径，不存在则从 HuggingFace 下载
- 失败时返回零向量（512 维）

#### `tools/reranker.py` — Cross-Encoder 重排器

**功能**：使用 BGE-reranker-base 对 RRF 融合后的候选进行精排。

**特性**：
- 单例模式，启动时预加载
- 支持本地模型路径 + ModelScope 临时权重文件自动提升
- 失败时降级为 RRF 排序结果
- 可通过 `RERANK_ENABLED=false` 关闭

#### `tools/query_rewriter.py` — Query 改写 Pipeline

**功能**：前置的查询优化 Pipeline，提升检索召回率。

**四阶段 Pipeline**：

| 阶段 | 组件 | 说明 |
|------|------|------|
| 1 | `Contextualizer` | 多轮对话指代消解（检测代词 → LLM 改写为自包含问题） |
| 2 | `QueryClassifier` | LLM 4 分类路由（direct / simple / complex / ambiguous） |
| 3 | `QueryRewriter` | 按分类执行改写策略 |
| 4 | `SimilarityValidator` | 余弦相似度过滤（阈值 0.7） |

**四种改写策略**：

| 分类 | 策略 | 说明 |
|------|------|------|
| `direct` | 直传 | 不改写，直接使用原始 query |
| `simple` | Multi-Query | 同义词替换 + 具体描述 + 抽象概括（3 个改写） |
| `complex` | Decompose | 拆解为 2-3 个独立子问题 |
| `ambiguous` | HyDE | 生成假设性文档作为检索 query |

#### `tools/crud_tools.py` — 知识条目 CRUD 工具

**功能**：Agent 的知识库操作工具，所有操作通过 `sync_manager` 执行。

**函数**：
- `read_knowledge(path)` — 读取条目
- `create_knowledge(title, content, category, tags)` — 创建条目
- `update_knowledge(path, title, content, tags)` — 更新条目
- `delete_knowledge(path)` — 删除条目
- `list_knowledge(category)` — 列出条目
- `get_knowledge_tree()` — 获取目录树

#### `tools/sync_manager.py` — ★ 四端同步管理器

**功能**：确保 Markdown 文件、Milvus 向量、BM25 索引、Git 版本四端一致。

**核心类 `WikiSyncManager`**：

| 操作 | 流程 |
|------|------|
| `create()` | 写 Markdown → 生成 embedding → 写 Milvus → 更新 BM25 → Git 提交 |
| `update()` | 更新 Markdown → 更新 Milvus → 更新 BM25 → Git 提交 |
| `delete()` | 删除 Markdown → 删除 Milvus 向量 → 删除 BM25 → Git 提交 |
| `reindex_all()` | 遍历所有 Markdown → 全量重建 Milvus + BM25 |
| `reindex_page()` | 单页面重建索引（用于 Git 回滚后同步） |
| `rollback()` | Git 回滚文件 → 重建索引 |
| `import_markdown()` | 导入 Markdown（创建或覆盖） |

**设计要点**：
- 所有写操作必须经过此管理器，不允许绕过
- Milvus 不可用时自动跳过向量同步（优雅降级）
- BM25 索引每次修改后立即持久化

#### `tools/env_monitor.py` — 环境监控器

**功能**：监控 knowledge/ 目录的文件变化，自动触发索引同步。

**工作模式**：
- **轮询模式**（默认）：每 5 秒扫描所有 .md 文件的 MD5 hash
- 检测到变化后调用 `sync_manager.reindex_page()` 或 `_delete_from_vector_store()`

**检测的变化类型**：
- `CREATED` — 新增文件
- `MODIFIED` — 文件内容变化（hash 不同）
- `DELETED` — 文件被删除

---

### 3.4 Wiki 知识管理层

#### `wiki/service.py` — 知识条目 CRUD 服务

**功能**：基于文件系统的知识条目管理，使用 YAML frontmatter 存储元数据。

**Markdown 文件格式**：
```markdown
---
title: 条目标题
summary: 一句话摘要
category: 分类路径
tags:
- 标签1
- 标签2
links:
- 关联条目路径
source: manual
created: 2024-01-01T00:00:00
updated: 2024-01-01T00:00:00
---

正文内容...
```

**核心功能**：

| 功能 | 函数 | 说明 |
|------|------|------|
| 目录树 | `get_tree()` | 递归构建目录树结构 |
| CRUD | `get_page()` / `create_page()` / `update_page()` / `delete_page()` | 文件读写 |
| 搜索 | `search_pages()` | 基于文件名 + 内容的全文搜索（关键词匹配 + 权重评分） |
| Wiki Links | `extract_wikilinks()` / `resolve_link()` | 解析 `[[...]]` 语法 |
| 反向链接 | `get_backlinks()` | 查找所有引用了指定页面的页面 |
| 标签 | `get_all_tags()` | 从 frontmatter 收集所有标签 |
| 知识图谱 | `get_link_graph()` | 构建节点 + 链接的图数据 |
| 分类 | `get_categories()` | 从 category 字段构建分类树 |
| 词条索引 | `get_entry_index()` | 按首字母（拼音）分组 |

#### `wiki/git_service.py` — Git 版本管理

**功能**：基于 GitPython 的知识库版本控制。

**核心功能**：
- `commit_changes()` — 提交变更（自动检测是否有变更）
- `get_history()` — 获取变更历史（支持按文件过滤）
- `get_diff()` — 获取两个版本之间的 diff
- `get_structured_diff()` — 获取结构化 diff（hunk + line 级别）
- `rollback()` — 回滚文件到指定版本

#### `wiki/schemas.py` — 数据模型

**功能**：定义所有 Pydantic 数据模型。

**主要模型**：

| 模型 | 说明 |
|------|------|
| `WikiNode` | 目录树节点（name, path, is_dir, children） |
| `WikiPage` | 知识条目（path, title, content, summary, category, tags, links, source, timestamps） |
| `WikiPageCreate` / `WikiPageUpdate` | 创建/更新请求 |
| `WikiCommit` | Git 提交记录（hash, message, date, files） |
| `WikiSearchResult` | 搜索结果（path, title, snippet, score） |
| `WikiBacklink` | 反向链接 |
| `WikiDiff` / `WikiDiffHunk` / `WikiDiffLine` | 结构化 diff |
| `GraphNode` / `GraphLink` / `WikiGraph` | 知识图谱 |
| `TagInfo` | 标签信息 |
| `CategoryInfo` | 分类信息（支持层级） |
| `EntryIndexItem` | 词条索引项 |

---

### 3.5 会话管理层

#### `session/store.py` — 会话存储服务

**功能**：管理对话会话和消息，支持 Redis 缓存。

**核心功能**：

| 函数 | 说明 |
|------|------|
| `create_session()` | 创建新会话 |
| `get_session()` | 获取会话及所有消息（带 Redis 缓存） |
| `list_sessions()` | 列出所有会话摘要 |
| `add_message()` | 添加消息（自动更新 session 的 updated_at） |
| `delete_session()` | 删除会话及所有消息 |
| `get_session_key_facts()` | 获取会话累积的关键事实 |
| `merge_session_key_facts()` | 合并新 key_facts（去重，最多 20 条） |
| `get_active_eval_task_id()` | 获取当前活跃的评估任务 ID |
| `set_active_eval_task_id()` | 设置活跃评估任务 ID |
| `update_extraction_status()` | 更新知识提取的确认状态 |

**缓存策略**：
- 会话详情：`wiki:session:{id}`，TTL 由 `CACHE_SESSION_TTL` 控制
- 会话列表：`wiki:sessions:list`，TTL 60 秒
- key_facts：`wiki:session:{id}:facts`，TTL 同会话
- 写操作后自动失效相关缓存

---

### 3.6 API 路由层

#### `routers/chat.py` — 对话 API

**前缀**：`/api/chat`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/stream` | POST | SSE 流式对话 |
| `/message` | POST | 非流式对话 |
| `/save-knowledge` | POST | 手动保存知识到知识库 |
| `/confirm` | POST | HITL 确认/取消知识库操作 |
| `/sessions` | POST | 创建会话 |
| `/sessions` | GET | 列出所有会话 |
| `/sessions/{id}` | GET | 获取会话详情 |
| `/sessions/{id}` | DELETE | 删除会话 |

**SSE 事件类型**：
- `content` — AI 回复的文本片段
- `wiki_results` — 知识库检索结果
- `extraction` — 知识提取结果
- `evaluation_task_id` — 评估任务 ID
- `status` — 状态提示
- `error` — 错误信息
- `done` — 对话结束

#### `routers/wiki.py` — Wiki API

**前缀**：`/api/wiki`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/tree` | GET | 获取目录树 |
| `/search` | GET | 搜索知识条目 |
| `/page/{path}` | GET | 读取条目 |
| `/page/{path}` | POST | 创建条目 |
| `/page/{path}` | PUT | 更新条目 |
| `/page/{path}` | DELETE | 删除条目 |
| `/page/{path}/history` | GET | 获取条目变更历史 |
| `/page/{path}/rollback` | POST | 回滚到指定版本 |
| `/page/{path}/diff` | GET | 获取版本 diff |
| `/page/{path}/backlinks` | GET | 获取反向链接 |
| `/import` | POST | 导入 Markdown |
| `/auto-tag` | POST | 自动生成标签 |
| `/export` | GET | 导出知识库为 ZIP |
| `/tags` | GET | 获取所有标签 |
| `/graph` | GET | 获取知识图谱 |
| `/categories` | GET | 获取分类树 |
| `/category/{cat}/entries` | GET | 获取分类下的词条 |
| `/index` | GET | 获取词条索引 |
| `/upload` | POST | 上传图片/文件 |
| `/assets/{filename}` | GET | 访问上传的文件 |

#### `routers/debug.py` — 调试 API

**前缀**：`/api/debug`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/overview` | GET | 各数据源汇总统计 |
| `/sessions` | GET | 所有 session 列表 |
| `/sessions/{id}` | GET | 单个 session 详情（含消息） |
| `/checkpoints` | GET | LangGraph checkpoint 线程列表 |
| `/checkpoints/{thread_id}` | GET | 单个 thread 的 checkpoint 时间线 |
| `/bm25` | GET | BM25 索引统计 |

#### `routers/vector_admin.py` — 向量管理

**前缀**：`/api/wiki`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/vector-stats` | GET | Milvus 统计信息 |
| `/vector-rebuild` | POST | 全量重建索引 |
| `/vector-paths` | GET | 已索引的页面路径 |
| `/vector-chunks` | GET | 分页查询块 |

**Web UI**：`/wiki-admin` — 向量管理可视化页面

---

### 3.7 前端层

#### `views/WikiAgent.vue` — 入口视图

**功能**：简单的包装组件，引入 `WikiAgentApp`。

#### `wiki/WikiAgentApp.vue` — 主应用组件

**功能**：Wiki Agent 的前端主界面，包含两种模式。

**两种模式**：

| 模式 | 说明 |
|------|------|
| 知识库（Wiki） | 左侧目录树 + 右侧内容区（页面浏览/编辑、搜索、变更流、知识图谱、词条索引） |
| 对话（Chat） | 左侧会话列表 + 右侧对话区（流式对话、知识提取确认） |

**子组件**：

| 组件 | 说明 |
|------|------|
| `Sidebar` | 左侧目录树导航 |
| `WikiPage` | 知识条目浏览/编辑（Markdown 渲染、面包屑、反向链接、关联条目） |
| `ChatView` | 对话界面（会话管理、消息列表、知识提取卡片、HITL 确认） |
| `HistoryPanel` | 全局变更流（Git 历史） |
| `LinkGraph` | 知识图谱可视化（ECharts） |
| `EntryIndex` | 按首字母分组的词条索引 |
| `ImportDialog` | Markdown 导入弹窗 |
| `CreateDialog` | 新建条目弹窗 |
| `TemplateDialog` | 条目模板选择弹窗 |

#### `wiki/components/ChatView.vue` — 对话组件

**功能**：完整的对话交互界面。

**核心特性**：
- 左侧会话列表（新建、切换、删除）
- 右侧消息区（用户消息、AI 回复、知识库检索结果、知识提取卡片）
- SSE 流式接收 AI 回复（逐 token 渲染）
- Markdown 渲染（使用 marked 库）
- 知识提取 HITL 确认（确认/拒绝 → 调用 `/api/chat/confirm`）
- 评估任务链接（跳转到评估详情页）

#### `wiki/components/WikiPage.vue` — 知识条目组件

**功能**：知识条目的浏览和编辑。

**核心特性**：
- 面包屑导航
- 页面元数据显示（分类、来源、更新时间、标签）
- Markdown 渲染 + `[[wikilink]]` 点击导航
- 反向链接面板
- 关联条目面板
- 分栏编辑器（标题、摘要、分类、标签、Markdown 正文、实时预览）

---

### 3.8 示例与模型资源

#### `example/wiki-agent/` — 示例运行数据

```
example/wiki-agent/
├── README.md                    # 示例说明
├── fix/                         # Bug 修复记录
├── knowledge/                   # 示例知识库内容（Git 仓库）
│   ├── welcome.md               # 欢迎页
│   ├── 知识汇总.md               # 知识汇总
│   ├── notes/                   # 笔记
│   ├── programming/             # 编程知识
│   ├── development/             # 开发工具
│   ├── software/                # 软件测试
│   └── system/                  # 系统介绍
├── milvus.db/                   # Milvus Lite 数据库文件
└── models/                      # 本地模型文件
    ├── bge-small-zh-v1.5/       # Embedding 模型
    └── bge-reranker-base/       # Reranker 模型
```

---

## 四、架构设计

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ WikiPage │  │ ChatView │  │ LinkGraph│  │ HistoryPanel     │ │
│  │ 浏览/编辑 │  │ 对话交互  │  │ 知识图谱  │  │ 版本历史         │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────────────┘ │
└───────┼──────────────┼──────────────┼──────────────┼─────────────┘
        │ REST         │ SSE          │ REST         │ REST
        ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Router Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │wiki.py   │  │chat.py   │  │debug.py  │  │vector_admin.py   │ │
│  │CRUD/搜索  │  │对话/HITL │  │内部状态   │  │向量管理           │ │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └──────────────────┘ │
└───────┼──────────────┼──────────────────────────────────────────┘
        │              │
        ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Service Layer 服务层                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              wiki/service.py                              │   │
│  │  知识条目 CRUD · 搜索 · WikiLinks · 图谱 · 分类 · 索引    │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              wiki/git_service.py                           │   │
│  │  Git 提交 · 历史 · diff · 回滚                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              session/store.py                              │   │
│  │  会话 CRUD · 消息管理 · key_facts · Redis 缓存             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Layer 智能体层                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              agent/graph.py (LangGraph)                   │   │
│  │  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐      │   │
│  │  │ search │──▶│respond │──▶│ decide │──▶│execute │      │   │
│  │  │三路检索 │   │流式回复 │   │知识决策 │   │HITL执行│      │   │
│  │  └────────┘   └────────┘   └────────┘   └────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  agent/context_retriever.py  —  统一上下文检索             │   │
│  │  agent/knowledge_agent.py    —  知识库维护决策             │   │
│  │  agent/auto_tagger.py        —  自动标签生成               │   │
│  │  agent/eval_middleware.py    —  评估中间件（SDK 桥接）      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Tool Layer 工具层                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐   │
│  │ search_tools   │  │ query_rewriter│  │ sync_manager      │   │
│  │ 混合搜索入口    │  │ Query改写Pipeline│ │ 四端同步管理器    │   │
│  └───────┬───────┘  └───────────────┘  └────────┬──────────┘   │
│          │                                        │              │
│  ┌───────┴───────────────────────────────┐  ┌────┴──────────┐   │
│  │         检索 Pipeline                  │  │  CRUD Pipeline │   │
│  │  ┌──────────┐  ┌──────┐  ┌─────────┐  │  │  ┌──────────┐ │   │
│  │  │ semantic  │  │ BM25 │  │ RRF融合  │  │  │  │Markdown  │ │   │
│  │  │ Milvus   │  │jieba │  │ 倒数秩   │  │  │  │文件读写   │ │   │
│  │  └──────────┘  └──────┘  └────┬────┘  │  │  └──────────┘ │   │
│  │                                │       │  │  ┌──────────┐ │   │
│  │                         ┌──────┴──────┐│  │  │ Milvus   │ │   │
│  │                         │  Reranker   ││  │  │ 向量同步  │ │   │
│  │                         │ CrossEncoder││  │  └──────────┘ │   │
│  │                         └─────────────┘│  │  ┌──────────┐ │   │
│  └────────────────────────────────────────┘  │  │ BM25同步  │ │   │
│                                              │  └──────────┘ │   │
│  ┌───────────────┐  ┌───────────────┐       │  ┌──────────┐ │   │
│  │ chunker       │  │ embeddings    │       │  │ Git提交   │ │   │
│  │ 文档分块       │  │ 向量生成      │       │  └──────────┘ │   │
│  └───────────────┘  └───────────────┘       └──────────────┘   │
│  ┌───────────────┐                                              │
│  │ env_monitor   │                                              │
│  │ 文件变化监控   │                                              │
│  └───────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Storage Layer 存储层                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Milvus   │  │ SQLite   │  │ 文件系统  │  │ Git          │   │
│  │ 向量数据库│  │ 会话/消息 │  │ Markdown │  │ 版本控制     │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
│  ┌──────────┐  ┌──────────┐                                    │
│  │ BM25     │  │ Redis    │                                    │
│  │ 倒排索引  │  │ 缓存(可选)│                                    │
│  └──────────┘  └──────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.2 LangGraph 对话流程图

```
用户发送消息
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  search 节点                                                 │
│  ① Query 改写 Pipeline                                       │
│     ├─ Contextualizer（代词消解）                              │
│     ├─ QueryClassifier（4 分类路由）                           │
│     ├─ QueryRewriter（Multi-Query / HyDE / Decompose）        │
│     └─ SimilarityValidator（余弦相似度过滤）                    │
│  ② 对每个改写 query 执行 hybrid_search                        │
│     ├─ semantic_search (Milvus)                               │
│     ├─ keyword_search (BM25)                                  │
│     ├─ RRF 融合                                               │
│     └─ Cross-Encoder 重排                                     │
│  ③ 获取 session key_facts（长期记忆）                          │
│  ④ 获取最近对话历史（短期记忆）                                 │
│  ⑤ LLM 提取新 key_facts 并合并到 session                      │
│  ⑥ 组装统一上下文块（带预算裁剪）                               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  respond 节点                                                │
│  ① 构建 LLM 消息列表                                          │
│     [SystemPrompt] + [ContextBlock] + [ChatHistory] + [User]  │
│  ② astream() 流式生成回复                                     │
│  ③ 逐 token 通过 SSE 推送给前端                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ should_decide │
                   │ len > 50 ?   │
                   └──────┬───────┘
                    yes   │   no
                 ┌────────┴────────┐
                 ▼                 ▼
┌────────────────────────────┐   END
│  decide 节点                │
│  ① hybrid_search 查找相关知识│
│  ② 读取相关条目正文预览      │
│  ③ LLM 决策：               │
│     create / update / delete │
│     / none                   │
└─────────────┬──────────────┘
              │
              ▼
       ┌──────────────┐
       │should_execute│
       │action != none│
       └──────┬───────┘
        yes   │   no
     ┌────────┴────────┐
     ▼                 ▼
┌────────────────────┐  END
│  execute 节点       │
│  interrupt({})      │  ← Human-in-the-Loop
│  等待用户确认/取消   │
│  执行 CRUD 操作     │
│  (经 sync_manager)  │
└────────────────────┘
     │
     ▼
    END
```

---

### 4.3 混合检索 Pipeline

```
用户 Query
     │
     ▼
┌─────────────────────────────────────┐
│  ① Query 改写（可选）                │
│  原始 query + 改写 queries (1~4个)   │
└─────────────────┬───────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌────────┐  ┌────────┐  ┌────────────┐
│Semantic │  │ BM25   │  │ 对每个query │
│Search   │  │Search  │  │ 分别执行    │
│(Milvus) │  │(jieba) │  │ 两种搜索    │
│         │  │        │  │            │
│512维向量 │  │TF-IDF  │  │            │
│余弦相似度│  │加权评分 │  │            │
└────┬────┘  └───┬────┘  └────────────┘
     │           │
     └─────┬─────┘
           ▼
┌─────────────────────────────────────┐
│  ② RRF 融合（Reciprocal Rank Fusion）│
│                                     │
│  score(d) = Σ 1/(k + rank_i(d) + 1) │
│                                     │
│  k = 60（平滑参数）                  │
│  语义搜索和 BM25 各贡献一份排名       │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  ③ Cross-Encoder 重排               │
│                                     │
│  BAAI/bge-reranker-base             │
│  输入: (query, document) 对          │
│  输出: 相关性分数                     │
│                                     │
│  候选数 = top_k × RERANK_CANDIDATE_  │
│          MULTIPLIER (默认 3)         │
│  返回 top_k 个结果                   │
└─────────────────┬───────────────────┘
                  │
                  ▼
           最终结果 (top_k)
```

---

### 4.4 四端同步机制

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
   │ service.py  │ │ chunk_markdown() │ jieba分词  │
   │ YAML        │ │ → generate_  │ │ → BM25Okapi│
   │ frontmatter │ │   embedding()│ │ → pickle   │
   │ + 正文      │ │ → insert_    │ │   持久化    │
   │             │ │   chunks()   │ │             │
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

一致性保证：
- 所有写操作必须经过 sync_manager
- 任何一端失败不影响其他端（try-catch 隔离）
- Milvus 不可用时跳过向量同步（优雅降级）
- BM25 每次修改后立即持久化
- env_monitor 自动检测外部文件变化并同步
```

---

### 4.5 三路记忆体系

```
┌─────────────────────────────────────────────────────────┐
│                   统一上下文检索                          │
│              context_retriever.py                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  External KB (RAG) — 外部知识库                  │    │
│  │                                                 │    │
│  │  hybrid_search(query) → top 5 results           │    │
│  │  每个结果: {path, title, snippet, score}         │    │
│  │                                                 │    │
│  │  预算: 1500 字符                                │    │
│  │  优先级: ★★★                                    │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Long-term Memory — 长期记忆                    │    │
│  │                                                 │    │
│  │  session.key_facts (SQLite + Redis)             │    │
│  │  每轮对话 LLM 自动提取关键事实                   │    │
│  │  去重合并，最多 20 条                            │    │
│  │                                                 │    │
│  │  预算: 500 字符                                 │    │
│  │  优先级: ★★★★（最高）                           │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Short-term Memory — 短期记忆                   │    │
│  │                                                 │    │
│  │  chat_history (最近 10 条消息)                   │    │
│  │  拼接为 "用户: ... / 助手: ..." 格式             │    │
│  │                                                 │    │
│  │  预算: 1000 字符                                │    │
│  │  优先级: ★★                                     │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  总预算: ~3000 字符                                      │
│  组装顺序: key_facts → wiki_results → history            │
└─────────────────────────────────────────────────────────┘
```

---

### 4.6 Query 改写 Pipeline

```
用户原始 Query
     │
     ▼
┌─────────────────────────────────────┐
│  ① Contextualizer 上下文补齐         │
│                                     │
│  规则检测: query 含代词?              │
│  (它/这个/那个/这些/上述/前者...)      │
│                                     │
│  是 → LLM 指代消解                   │
│       "它怎么优化" →                  │
│       "Milvus 向量数据库怎么优化"     │
│  否 → 直传                           │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  ② QueryClassifier 路由分类          │
│                                     │
│  LLM 4 分类:                         │
│  ┌──────────┬─────────────────────┐ │
│  │ direct   │ 简单明确，不改写     │ │
│  │ simple   │ 简单，轻微改写       │ │
│  │ complex  │ 复杂，需分解         │ │
│  │ ambiguous│ 模糊，需 HyDE       │ │
│  └──────────┴─────────────────────┘ │
└─────────────────┬───────────────────┘
                  │
         ┌────────┼────────┬──────────┐
         ▼        ▼        ▼          ▼
┌──────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│  direct  │ │ simple  │ │ complex │ │ambiguous│
│  直传    │ │Multi-   │ │Decompose│ │  HyDE   │
│          │ │Query    │ │         │ │         │
│ [q]      │ │[q,q',   │ │[q,q1,  │ │[q,hypo] │
│          │ │ q'',    │ │ q2]    │ │         │
│          │ │ q''']   │ │        │ │假设性文档│
└────┬─────┘ └────┬────┘ └───┬────┘ └────┬────┘
     │            │          │           │
     └────────────┴──────────┴───────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  ③ SimilarityValidator 相似度校验    │
│                                     │
│  对每个改写 query:                    │
│  1. 生成 embedding                   │
│  2. 计算与原始 query 的余弦相似度     │
│  3. 相似度 < 0.7 → 丢弃              │
│                                     │
│  兜底: 全部被过滤则返回 [original]    │
└─────────────────┬───────────────────┘
                  │
                  ▼
           最终 queries (1~5 个)
           传入 context_retriever
```

---

## 五、数据流

### 5.1 用户对话数据流

```
用户输入消息
     │
     ▼
Frontend (ChatView.vue)
  POST /api/chat/stream
     │
     ▼
chat.py router
  ├─ ensure_session() → 创建/获取 session
  ├─ get_session() → 获取历史消息
  ├─ add_message("user", ...) → 持久化用户消息
  └─ run_chat_stream() → 调用 graph.py
         │
         ▼
    LangGraph 执行
      ├─ search → retrieve_context() + hybrid_search()
      ├─ respond → astream() → SSE 逐 token 推送
      ├─ decide → knowledge_agent.decide_action()
      └─ execute → interrupt() → 等待 HITL
         │
         ▼
    SSE 事件流
      ├─ data: {"type": "content", "text": "..."}
      ├─ data: {"type": "wiki_results", "results": "..."}
      ├─ data: {"type": "extraction", "data": {...}}
      └─ data: {"type": "done"}
         │
         ▼
    chat.py
      add_message("assistant", collected, wiki_results, extraction)
         │
         ▼
    Frontend 渲染
      ├─ 逐 token 显示 AI 回复
      ├─ 显示知识库检索结果（可折叠）
      └─ 显示知识提取卡片（HITL 确认）
```

### 5.2 知识库 CRUD 数据流

```
创建/更新/删除操作（来自 Agent / REST API / 前端）
     │
     ▼
sync_manager.create() / update() / delete()
     │
     ├─ ① service.create_page() / update_page() / delete_page()
     │     └─ 写入/修改/删除 Markdown 文件
     │
     ├─ ② _sync_to_vector_store()
     │     ├─ chunk_markdown() → 文档分块
     │     ├─ generate_embedding() → 生成向量
     │     ├─ store.delete_by_path() → 清除旧向量
     │     ├─ store.insert_chunks() → 写入新向量
     │     ├─ bm25.add_document() → 更新 BM25
     │     └─ bm25.save() → 持久化 BM25
     │
     └─ ③ git_service.commit_changes()
           └─ git add + git commit
```

### 5.3 评估数据流

```
Wiki Agent 对话执行
     │
     ▼
eval_middleware.py
  ├─ start_session()
  │     ├─ collector.start() → 创建评估 task
  │     ├─ _generate_plan() → LLM 生成结构化计划
  │     └─ collector.record(PLAN, plan_data)
  │
  ├─ wrap_llm() → SDK 包裹 LLM，自动采集:
  │     ├─ LLM 调用 (prompt/response/latency)
  │     └─ 工具决策
  │
  ├─ instrument_graph() → SDK 包裹 Graph，自动采集:
  │     ├─ 节点执行
  │     ├─ 状态变化
  │     └─ 工具调用
  │
  ├─ record_retrieval() → 手动记录检索事件
  │     └─ query, retrieved_docs, source, duration
  │
  └─ finish_session()
        └─ collector.finish() → flush 轨迹 → 触发评估
              │
              ▼
        评估引擎 (6 个并行 LLM-as-Judge)
              │
              ▼
        评估结果 (6 维评分)
```

---

## 六、API 接口一览

### 对话 API (`/api/chat`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/stream` | SSE 流式对话 |
| POST | `/message` | 非流式对话 |
| POST | `/save-knowledge` | 手动保存知识 |
| POST | `/confirm` | HITL 确认/取消 |
| POST | `/sessions` | 创建会话 |
| GET | `/sessions` | 列出会话 |
| GET | `/sessions/{id}` | 会话详情 |
| DELETE | `/sessions/{id}` | 删除会话 |

### Wiki API (`/api/wiki`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/tree` | 目录树 |
| GET | `/search?q=` | 搜索 |
| GET | `/page/{path}` | 读取 |
| POST | `/page/{path}` | 创建 |
| PUT | `/page/{path}` | 更新 |
| DELETE | `/page/{path}` | 删除 |
| GET | `/page/{path}/history` | 变更历史 |
| POST | `/page/{path}/rollback` | 回滚 |
| GET | `/page/{path}/diff` | 版本 diff |
| GET | `/page/{path}/backlinks` | 反向链接 |
| POST | `/import` | 导入 |
| POST | `/auto-tag` | 自动标签 |
| GET | `/export` | 导出 ZIP |
| GET | `/tags` | 所有标签 |
| GET | `/graph` | 知识图谱 |
| GET | `/categories` | 分类树 |
| GET | `/category/{cat}/entries` | 分类词条 |
| GET | `/index` | 词条索引 |
| POST | `/upload` | 上传文件 |
| GET | `/vector-stats` | 向量统计 |
| POST | `/vector-rebuild` | 重建索引 |
| GET | `/vector-paths` | 已索引路径 |
| GET | `/vector-chunks` | 块列表 |

### 调试 API (`/api/debug`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/overview` | 汇总统计 |
| GET | `/sessions` | 会话列表 |
| GET | `/sessions/{id}` | 会话详情 |
| GET | `/checkpoints` | Checkpoint 列表 |
| GET | `/checkpoints/{id}` | Checkpoint 详情 |
| GET | `/bm25` | BM25 统计 |

---

## 七、关键设计决策

### 7.1 为什么用 LangGraph？

- **状态管理**：`WikiState` TypedDict 清晰定义了对话的每一步状态
- **Human-in-the-Loop**：`interrupt()` 机制天然支持 HITL，execute 节点等待用户确认
- **Checkpoint**：`AsyncSqliteSaver` 自动保存每一步的状态，支持中断恢复
- **可扩展性**：新增节点只需 `graph.add_node()` + 添加边

### 7.2 为什么用四端同步？

- **Markdown 文件**：人类可读、可编辑、Git 友好
- **Milvus 向量**：语义检索的核心
- **BM25 索引**：精确关键词匹配的补充
- **Git 版本**：完整的变更历史和回滚能力

四端缺一不可：没有 Milvus 则无法语义搜索，没有 BM25 则精确匹配差，没有 Git 则无法追溯变更。

### 7.3 为什么用 Query 改写？

用户的原始查询往往是：
- **含代词**："它怎么优化？" → 需要指代消解
- **模糊**："那个能存向量的东西" → 需要 HyDE
- **复杂**："比较 A 和 B 的差异" → 需要分解

Query 改写 Pipeline 在检索前优化查询，显著提升召回率。

### 7.4 为什么用三路记忆？

- **External KB**：回答需要引用知识库内容
- **Long-term Memory**：记住用户偏好、项目约束等跨轮次信息
- **Short-term Memory**：理解多轮对话的上下文

三路记忆让 Agent 既能引用知识库，又能记住对话历史中的关键信息。

### 7.5 为什么用评估中间件？

- **解耦**：业务代码（graph.py）不直接依赖 SDK
- **自动采集**：SDK 自动采集 LLM 调用、节点执行、工具调用
- **手动补充**：SDK 无法自动采集的（如检索细节）通过中间件手动记录
- **统一管理**：评估会话的生命周期（start → record → finish）统一在此管理

### 7.6 优雅降级策略

| 组件 | 不可用时的行为 |
|------|--------------|
| Milvus | 跳过向量同步，语义搜索降级为 BM25 |
| Redis | 直接读写 SQLite，无缓存 |
| Reranker | 使用 RRF 排序结果 |
| Git | 跳过版本提交 |
| Query Rewrite | 直接使用原始 query |
