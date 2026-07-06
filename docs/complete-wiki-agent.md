# Wiki Agent — 完整技术文档（合集版 v3.0）

> 最后更新：2026-07-06
> 本文档整合项目所有技术文档，完整保留原始内容，覆盖背景、架构、实现、难点、面试问答。
> 总计 7 个源文档，包含完整的代码片段、架构图、配置说明。

---

## 目录

1. [第一部分：Wiki Agent 项目全面解析](#第一部分wiki-agent-项目全面解析)
2. [第二部分：技术难点深度解析](#第二部分技术难点深度解析)
3. [第三部分：记忆体系架构](#第三部分记忆体系架构)
4. [第四部分：性能优化报告](#第四部分性能优化报告)
5. [第五部分：学习指南](#第五部分学习指南)
6. [第六部分：双流架构](#第六部分双流架构)
7. [第七部分：技术深度剖析](#第七部分技术深度剖析)

---

# 第一部分：Wiki Agent 项目全面解析

> 来源：`docs/wiki-agent-overview.md`

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
  - [4.4 四端同步机制](#44-四端同步机制)
  - [4.5 四路记忆体系与压缩策略](#45-四路记忆体系与压缩策略)
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

```bash
app/wiki_agent/
├── __init__.py                    # 包初始化（空）
├── config.py                      # 全局配置（路径、模型、参数）
├── bootstrap.py                   # 启动引导（目录创建、种子数据、索引同步）
├── database.py                    # SQLite 数据库初始化（会话表、消息表）
│
├── agent/                         # Agent 智能体层
│   ├── __init__.py
│   ├── graph.py                   # ★ LangGraph 主编排（search → respond → decide → execute）
│   ├── llm_factory.py             # 统一 LLM 创建工厂
│   ├── knowledge_agent.py         # 知识库维护决策器（create/update/delete/none）
│   ├── context_retriever.py       # 统一上下文检索（合并四路记忆）
│   ├── auto_tagger.py             # LLM 自动标签生成
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
1. 调用 `retrieve_context()` 获取四层上下文（Query Rewrite + 混合检索 + 用户/会话记忆 + 对话历史）
2. `build_context_block()` 预算裁剪组装
3. 构建 Prompt（用户消息 + AI 回复 + 四层上下文 + 格式指令）
4. 用 LLM 生成结构化 `KnowledgeDecision`（通过 with_structured_output，降级 PydanticOutputParser）
5. `model_validator` 硬校验必填字段，失败时反馈错误重试（最多 2 次）

#### `agent/context_retriever.py` — 统一上下文检索

**功能**：合并四路记忆源，为 LLM 提供完整的上下文。

**四路记忆**：

| 记忆类型 | 来源 | 说明 |
|----------|------|------|
| User Memory | `user_memory.facts` | 用户级持久事实（跨 session，上限 30 条） |
| Session Memory | `sessions.key_facts` | 会话级事实（当前 session，上限 20 条） |
| External KB (RAG) | `hybrid_search()` | 知识库混合检索结果（top 5） |
| Working Memory | `chat_history` | 最近 10 轮对话消息（200 字/条） |

**预算管理**：总预算约 3000 字符，按优先级分配：
1. User Memory（600 字符，最高优先级）
2. Session Memory（400 字符）
3. wiki_results（1200 字符）
4. history_summary（800 字符，最低优先级）

#### `agent/auto_tagger.py` — 自动标签生成

**功能**：用 LLM 为知识条目自动生成 3-5 个标签。

**特性**：
- 优先复用已有标签
- 标签 2-5 个中文字或英文字
- 输出 JSON 格式

#### `agent/llm_factory.py` — 统一 LLM 工厂

**功能**：统一 LLM 创建逻辑，ZhipuAI 优先、DeepSeek 兜底。

**核心函数**：
- `create_chat_llm(temperature, streaming, max_tokens)` — 创建 ChatOpenAI 实例

#### `hooks.py` — 生命周期钩子接口

**功能**：通过 SDK TrajectoryCollector 提供评估接入点。SDK 不可用或 `EVAL_ENABLED=false` 时自动降级为空操作。

**核心事件**：
- `emit_session_start()` — 会话开始
- `emit_retrieval()` — 检索完成
- `emit_key_facts()` — 记忆提取
- `emit_response()` — 回复生成
- `emit_session_end()` — 会话结束

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
| `get_recent_messages()` | 获取最近 N 条消息（SQL LIMIT，高效部分加载） |
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
│  │  agent/llm_factory.py        —  统一 LLM 工厂              │   │
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

### 4.5 四路记忆体系与压缩策略

```
┌─────────────────────────────────────────────────────────────────────┐
│                    统一上下文检索 + 六层压缩                          │
│                context_retriever.py + graph.py                      │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ① User Memory — 用户级持久事实（优先级 1，600 字符）         │   │
│  │     user_memory.facts，跨 session 共享，上限 30 条           │   │
│  │     LLM 提炼 scope=user 的事实（偏好、习惯）                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ② Session Memory — 会话级事实（优先级 2，400 字符）          │   │
│  │     sessions.key_facts，当前 session 生效，上限 20 条        │   │
│  │     LLM 提炼 scope=session 的事实（项目、约束、目标）        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ③ External KB — 知识库检索（优先级 3，1200 字符）            │   │
│  │     hybrid_search: semantic + BM25 + RRF + CrossEncoder     │   │
│  │     Query Rewrite: 消歧 → 分类 → 多策略改写 → 相似度校验     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ④ Working Memory — 对话历史（优先级 4，800 字符）            │   │
│  │     chat_history，最近 10 轮（20 条），200 字/条              │   │
│  │     六层压缩: SQL LIMIT → 滑动窗口 → 二次截断 →              │   │
│  │              字符预算 → LLM 提炼 → 分块截断                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  总预算: ~3000 字符                                                 │
│  组装顺序: user_facts → session_facts → wiki_results → history      │
└─────────────────────────────────────────────────────────────────────┘
```

**六层压缩策略**：

| 层级 | 机制 | 位置 | 说明 |
|------|------|------|------|
| ① SQL 截断 | `get_recent_messages(limit)` | store.py | 只查最近 20 条，不全量加载 |
| ② 滑动窗口 | `_build_history(max_turns)` | chat.py | 只取最近 10 轮 |
| ③ 二次保护 | `_build_llm_messages` 截断 | graph.py | prior[-20:] + SystemMessage 提示 |
| ④ 字符预算 | `build_context_block()` | context_retriever.py | 按优先级裁剪到 3000 字符 |
| ⑤ LLM 提炼 | `_extract_key_facts()` | graph.py | 对话→结构化事实，替代 SummaryMemory |
| ⑥ 分块截断 | `chunk_markdown()` | chunker.py | 知识条目 500 字/块存储 |

> 详细压缩策略说明见 `docs/wiki-agent-memory-architecture.md`。

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

wiki-agent 通过 SDK TrajectoryCollector 提供生命周期钩子，自动采集评估数据：

```
Wiki Agent 对话执行
     │
     ▼
hooks.py (SDK TrajectoryCollector)
  ├─ emit_session_start() → 创建评估任务
  │
  ├─ emit_retrieval() → 记录检索事件
  │     └─ query, results, duration_ms
  │
  ├─ emit_key_facts() → 记忆提取
  │     └─ facts
  │
  ├─ emit_response() → 回复生成
  │     └─ session_id, response
  │
  └─ emit_session_end() → flush 轨迹 + 触发评估
        │
        ▼
  评估平台 (register(EvalHooks()))
        ├─ 采集轨迹数据
        ├─ 触发 6 个评估器
        │
        ▼
  评估结果 (6 维评分)
```

独立运行时 hooks 为空操作，零开销。

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

### 7.4 为什么用四路记忆 + 六层压缩？

**四路记忆**：
- **User Memory**：记住用户偏好、习惯，跨 session 持久生效
- **Session Memory**：记住当前项目的上下文、技术约束
- **External KB**：回答需要引用知识库内容
- **Working Memory**：理解多轮对话的上下文

**六层压缩**：
- 滑动窗口（①②③）零成本保证最近对话完整
- 字符预算（④）控制 context 长度
- LLM 提炼（⑤）复用 search 节点，零额外调用，替代 LangChain ConversationSummaryMemory
- 分块截断（⑥）写入时一次性处理

四路记忆 + 六层压缩让 Agent 既能引用知识库，又能记住关键信息，同时不会因对话过长而超出 token 限制。

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


---

# 第二部分：技术难点深度解析

> 来源：`docs/wiki-agent-difficult-points.md`

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


---

# 第三部分：记忆体系架构

> 来源：`docs/wiki-agent-memory-architecture.md`

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
│     · with_structured_output 格式说明（Function Calling）     │
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


---

# 第四部分：性能优化报告

> 来源：`docs/wiki-agent-optimization-report.md`

# Wiki Agent 性能优化报告

## 项目概述

**项目名称**: Agent Runtime Evaluation Platform - Wiki Agent  
**优化时间**: 2026年7月  
**优化目标**: 降低对话响应延迟，提升用户体验

---

## 问题诊断

### 原始性能瓶颈

```
[Timing] rewrite_query: 3655ms
[Timing] hybrid_search: 28378ms
[Timing] _extract_key_facts: 22223ms
[Timing] Total time to first content: 55426ms
```

**总响应时间: 55 秒**，用户体验极差。

### 根本原因分析

| 问题 | 影响 | 耗时 |
|------|------|------|
| 串行 LLM 调用过多 | 5-7 次串行 LLM 调用 | ~15s |
| Rerank 计算密集 | Cross-Encoder 在 CPU 上运行 | ~25s |
| 查询改写策略单一 | 所有查询都走完整 pipeline | ~4s |
| 记忆存储阻塞 | 同步写入数据库 | ~1s |
| 冗余 LLM 调用 | 事实提取调用 2 次 LLM | ~2s |
| 流式输出配置错误 | `streaming=False` 导致非流式 | - |

---

## 优化方案

### 1. 流式输出修复

**问题**: `ChatOpenAI` 的 `streaming=False` 导致 `astream()` 不会逐 token 流式输出。

**修复**:
```python
# 修复前
streaming=False,  # ← 导致整个响应作为一个 chunk 返回

# 修复后
streaming=True,   # ← 现在真正逐 token 流式输出
```

**效果**: 用户可以立即看到响应内容，而不是等待完整响应。

---

### 2. 前端错误处理优化

**问题**: 后端返回错误时，前端显示 "..." 永远等待。

**修复**:
```javascript
// 添加 HTTP 状态检查
if (!res.ok) {
  aiMsg.content = `请求失败: HTTP ${res.status}`;
  return;
}

// 添加兜底逻辑
if (!aiMsg.content && !aiMsg.wikiResults && !aiMsg.extraction) {
  aiMsg.content = "抱歉，未能获取到回复内容。";
}
```

**效果**: 错误情况下正确显示错误信息，不再卡在加载状态。

---

### 3. LLM 调用优化

#### 3.1 移除冗余 LLM 调用

**问题**: `_extract_key_facts()` 调用 2 次 LLM（普通 + 结构化）。

**修复**: 只调用 1 次结构化 LLM，失败时降级到普通 LLM。

**效果**: 节省 ~1 秒/请求

#### 3.2 合并查询分类和改写

**问题**: 查询改写需要 3 次串行 LLM 调用（上下文补齐 + 分类 + 改写）。

**修复**: 合并分类和改写为单次 LLM 调用。

```python
_CLASSIFY_AND_REWRITE_PROMPT = """你是一个查询分析专家。请完成两个任务：

## 任务 1: 分类
将查询分为以下类型之一：direct, simple, complex, ambiguous

## 任务 2: 改写
根据分类结果生成改写查询

## 输出格式
返回 JSON 对象：
{
    "type": "分类结果",
    "rewrites": ["改写查询1", "改写查询2", ...]
}
"""
```

**效果**: LLM 调用从 3 次减少到 1-2 次，节省 ~2 秒。

---

### 4. 异步化优化

#### 4.1 评估计划异步化

**问题**: `_generate_plan()` 阻塞主流程 ~1.5 秒。

**修复**: 使用 `asyncio.create_task()` 后台执行。

```python
async def _deferred_plan():
    try:
        plan_data = await _generate_plan(goal)
        # 记录计划...
    except Exception:
        pass  # 计划生成失败不影响主流程

asyncio.create_task(_deferred_plan())
```

**效果**: 主流程不再等待计划生成。

#### 4.2 记忆存储异步化

**问题**: `merge_session_key_facts()` 和 `merge_user_memory()` 阻塞主流程。

**修复**: 使用 `asyncio.create_task()` 后台执行。

**效果**: 记忆存储在后台完成，不阻塞响应生成。

---

### 5. 并行化优化

#### 5.1 搜索并行化

**问题**: `semantic_search` 和 `keyword_search` 串行执行。

**修复**: 使用 `concurrent.futures.ThreadPoolExecutor` 并行执行。

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    semantic_future = executor.submit(semantic_search, query, recall_limit)
    keyword_future = executor.submit(keyword_search, query, recall_limit)
    semantic_results = semantic_future.result()
    keyword_results = keyword_future.result()
```

**效果**: 搜索时间减半，节省 ~0.5 秒。

#### 5.2 多查询并行搜索

**问题**: 多个改写查询的 `hybrid_search` 串行执行。

**修复**: 使用 `asyncio.gather()` 并行执行。

**效果**: 多查询搜索时间从 N×1.5s 降到 ~1.5s。

---

### 6. 复杂度分层策略（核心优化）

**问题**: 所有查询都走完整 RAG pipeline，包括昂贵的 rerank 操作。

**解决方案**: 基于复杂度的分层策略

```python
class QueryComplexity(Enum):
    """查询复杂度分级"""
    TRIVIAL = "trivial"    # 简单问候/闲聊，不需要 RAG
    SIMPLE = "simple"      # 简单查询，单次搜索，不改写
    MEDIUM = "medium"      # 中等查询，1-2 次改写，不 rerank
    COMPLEX = "complex"    # 复杂查询，完整 pipeline
```

#### 分层策略

| 复杂度 | 示例 | 策略 | 预期延迟 |
|--------|------|------|----------|
| **TRIVIAL** | "你好"、"谢谢"、"你是谁" | 跳过 RAG | ~0ms |
| **SIMPLE** | "什么是Python"、"总结知识库" | 单次搜索，不改写，不 rerank | ~1.5s |
| **MEDIUM** | "如何优化数据库查询性能" | 1-2 次改写，不 rerank | ~3-5s |
| **COMPLEX** | "对比 React 和 Vue 的优缺点" | 完整 pipeline + rerank | ~10-15s |

#### 复杂度判断规则

```python
_TRIVIAL_PATTERNS = [
    r'^(你好|hi|hello|hey|嗨|您好)',
    r'^(你是谁|你叫什么|who are you)',
    r'^(谢谢|感谢|thanks)',
    r'^(再见|bye|拜拜)',
]

_SIMPLE_PATTERNS = [
    r'^(什么是|怎么用|如何|解释|说明)',
    r'^(总结|概述|列举|列出)',
    r'^(有哪些|有什么|包含什么)',
]
```

---

### 7. 其他优化

#### 7.1 gRPC 连接优化

**问题**: Milvus Lite 的 gRPC keepalive 设置太激进，导致 `GOAWAY` 错误。

**修复**: 在模块加载时设置环境变量。

```python
os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIME_MS", "120000")
os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIMEOUT_MS", "20000")
```

**效果**: 消除 gRPC 连接错误。

#### 7.2 跳过简单查询的事实提取

**问题**: 简单查询也会调用 LLM 提取事实，浪费资源。

**修复**: 使用正则表达式匹配简单查询模式，直接返回空列表。

**效果**: 简单查询节省 ~1.5 秒。

---

## 优化效果

### 性能对比

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 简单问候 ("你好") | ~55s | ~0ms | **99.9%** |
| 简单查询 ("总结知识库") | ~55s | ~3s | **94.5%** |
| 中等查询 ("如何优化性能") | ~55s | ~5s | **90.9%** |
| 复杂查询 ("对比 React 和 Vue") | ~55s | ~15s | **72.7%** |

### 实际测试日志

```
[QueryRewrite] 复杂度: simple (query: 介绍一下Agent开发)
[Timing] rewrite_query: 2ms (complexity: simple)
[Timing] semantic+keyword search: 1118ms
[Timing] hybrid_search: 1120ms
[Timing] memory_load: 9ms
[Timing] retrieve_context: 1131ms
[Timing] _extract_key_facts: 1ms
[Timing] LLM first token: 1959ms
[Timing] Total time to first content: 3185ms
```

**总响应时间: 3.2 秒**（从 55 秒优化到 3.2 秒，提升 **94.2%**）

---

## 技术栈

- **后端**: Python, FastAPI, LangChain, LangGraph
- **向量数据库**: Milvus Lite
- **搜索引擎**: BM25 + 语义搜索 + Cross-Encoder Rerank
- **LLM**: DeepSeek / ZhipuAI
- **前端**: Vue 3, Vite

---

## 优化总结

### 关键优化点

1. **复杂度分层策略**: 根据查询复杂度选择不同的 RAG 策略
2. **异步化**: 将非关键路径的操作移到后台执行
3. **并行化**: 独立操作并行执行
4. **减少 LLM 调用**: 合并分类和改写，跳过简单查询的事实提取
5. **流式输出**: 修复 streaming 配置，提升用户体验

### 架构改进

```
用户查询
    ↓
复杂度分级 (规则判断，不调用 LLM)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ TRIVIAL    → 跳过 RAG，直接返回                              │
│ SIMPLE     → 单次搜索，不改写，不 rerank                     │
│ MEDIUM     → 1-2 次改写，不 rerank                          │
│ COMPLEX    → 完整 pipeline + rerank                         │
└─────────────────────────────────────────────────────────────┘
    ↓
流式响应生成
```

---

## 简历描述建议

### 项目经历

**Agent Runtime Evaluation Platform - Wiki Agent 性能优化**  
*2026年7月*

- 负责 Wiki Agent 对话系统的性能优化，将响应延迟从 55 秒优化到 3 秒，提升 94%
- 设计并实现基于复杂度的 RAG 分层策略，根据查询类型选择不同的检索和重排策略
- 优化 LLM 调用链路，通过合并分类和改写、异步化非关键路径，减少 60% 的 LLM 调用
- 实现搜索并行化和记忆存储异步化，提升系统吞吐量
- 修复流式输出配置和前端错误处理，改善用户体验

### 技术亮点

- **复杂度分层策略**: 基于规则的快速分类，避免对简单查询执行昂贵的 RAG 操作
- **异步化架构**: 使用 `asyncio.create_task()` 将非关键路径移到后台执行
- **并行化优化**: 使用 `ThreadPoolExecutor` 和 `asyncio.gather()` 并行执行独立操作
- **LLM 调用优化**: 合并分类和改写，减少串行 LLM 调用次数

---

## 附录：代码改动清单

### 主要文件修改

1. `app/wiki_agent/agent/graph.py`
   - 修复 `streaming=False` 问题
   - 移除冗余 LLM 调用
   - 实现异步记忆存储
   - 添加复杂度判断逻辑

2. `app/wiki_agent/agent/tools/query_rewriter.py`
   - 新增 `QueryComplexity` 枚举
   - 实现 `classify_complexity()` 函数
   - 合并分类和改写为单次 LLM 调用

3. `app/wiki_agent/agent/context_retriever.py`
   - 实现复杂度分层策略
   - 并行化搜索操作

4. `app/wiki_agent/agent/tools/search_tools.py`
   - 添加 `enable_rerank` 参数
   - 并行化语义和关键词搜索

5. `app/wiki_agent/hooks.py`
   - 通过 SDK TrajectoryCollector 提供生命周期钩子

6. `app/wiki_agent/frontend/src/wiki/components/ChatView.vue`
   - 修复前端错误处理
   - 添加 HTTP 状态检查

7. `app/wiki_agent/agent/tools/vector_store.py`
   - 修复 gRPC 连接问题
   - 添加重试机制


---

# 第五部分：学习指南

> 来源：`docs/wiki-agent-learning-guide.md`

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


---

# 第六部分：双流架构

> 来源：`docs/two-flow-architecture.md`

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


---

# 第七部分：技术深度剖析

> 来源：`docs/deep-dive-wiki-agent.md`

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


---

