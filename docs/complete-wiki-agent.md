# Wiki Agent — 完整技术文档

> 版本：v1.0 | 最后更新：2026-07-06
> 本文档整合项目所有技术文档，覆盖背景、架构、实现、难点、面试问答。

---

## 目录

1. [项目背景与定位](#1-项目背景与定位)
2. [技术选型与理由](#2-技术选型与理由)
3. [系统架构](#3-系统架构)
4. [LangGraph 图结构详解](#4-langgraph-图结构详解)
5. [四级混合检索管线](#5-四级混合检索管线)
6. [知识管理系统](#6-知识管理系统)
7. [三层记忆架构](#7-三层记忆架构)
8. [预算感知上下文组装](#8-预算感知上下文组装)
9. [Human-in-the-Loop](#9-human-in-the-loop)
10. [SSE 流式对话](#10-sse-流式对话)
11. [Query 改写与复杂度分类](#11-query-改写与复杂度分类)
12. [分块策略与 Embedding](#12-分块策略与-embedding)
13. [Milvus 向量存储](#13-milvus-向量存储)
14. [Git 集成与版本管理](#14-git-集成与版本管理)
15. [与评估平台的集成](#15-与评估平台的集成)
16. [核心难点与解决方案](#16-核心难点与解决方案)
17. [面试高频问答](#17-面试高频问答)
18. [常见陷阱与避坑指南](#18-常见陷阱与避坑指南)
19. [性能指标](#19-性能指标)

---

## 1. 项目背景与定位

### 1.1 双重身份

Wiki Agent 有两个身份：
1. **独立产品**：团队知识库管理 + 智能问答
2. **评估平台的试验田**：提供真实的 Agent 轨迹数据，验证评估体系的有效性

### 1.2 核心业务场景

| 场景 | 用户操作 | Agent 行为 |
|------|----------|------------|
| 知识问答 | "认证机制怎么实现的？" | 检索 → 生成回答 → 自动提取新知识 |
| 知识创建 | "记录今天的会议决定" | LLM 生成 → HITL 确认 → 写入 → 同步索引 |
| 知识更新 | "更新 OAuth 文档" | 检索现有 → LLM 修改 → HITL 确认 → 更新 |
| 知识图谱 | 浏览知识关联 | 构建 wikilink 有向图 → 前端可视化 |

### 1.3 与传统 RAG 的区别

| 方面 | 传统 RAG | Wiki Agent |
|------|----------|------------|
| 检索 | 单一向量搜索 | 四级混合（语义 + BM25 + RRF + Rerank） |
| 记忆 | 无 | 三层（用户 + 会话 + 工作记忆） |
| 写入 | 只读 | CRUD 全支持 + HITL 确认 |
| 一致性 | N/A | 四路同步（Markdown + Milvus + BM25 + Git） |
| 上下文 | 固定 token | 预算感知优先级裁剪 |

---

## 2. 技术选型与理由

### 2.1 技术栈

| 类别 | 技术 | 选型理由 |
|------|------|----------|
| 编排 | LangGraph | 条件边、状态持久化、HITL 支持 |
| LLM | DeepSeek | 成本低，中文效果好 |
| 向量库 | Milvus Lite | 嵌入式，零配置，gRPC 性能好 |
| 关键词检索 | BM25 (rank_bm25) | 成熟算法，配合 jieba 中文分词 |
| Reranker | bge-reranker-base | 中文效果好，开源免费 |
| Embedding | bge-small-zh-v1.5 | 512 维，中文优化，体积小 |
| 分块 | RecursiveCharacterTextSplitter | 中文感知分隔符 |
| 持久化 | SQLite + YAML frontmatter | 零配置，文件即数据库 |
| 版本控制 | Git | 知识变更历史 |
| 前端 | Vue 3 | 轻量，组件化 |

### 2.2 为什么选 Milvus Lite 而不是 Milvus Server？

- 零配置：嵌入式运行，不需要 Docker
- 单文件：数据存储在 `data/milvus.db`
- 够用：个人知识库规模（<10k 文档）完全够用
- 可升级：代码兼容 Milvus Server，换 URI 即可

---

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3)                          │
│  ChatView · WikiPage · EntryList · Sidebar · LinkGraph      │
└──────────────────────────┬──────────────────────────────────┘
                           │ SSE / REST
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI Server                             │
│  /api/chat/* · /api/wiki/* · /api/wiki/vector-admin         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    LangGraph 编排                             │
│  search → respond → decide → execute (HITL)                 │
│  AsyncSqliteSaver checkpoint                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Context     │  │  Knowledge   │  │  Trajectory  │
│  Retriever   │  │  Service     │  │  Collector   │
│ (4路记忆)    │  │ (CRUD+同步)  │  │ (评估轨迹)   │
└──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │
  ┌────┴────┐     ┌──────┴──────┐
  │ Milvus  │     │  Markdown   │
  │ BM25    │     │  Git        │
  │ Reranker│     │  Frontmatter│
  └─────────┘     └─────────────┘
```

### 3.2 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| Graph | `graph.py` | LangGraph 编排，状态管理，HITL |
| Context Retriever | `context_retriever.py` | 四路记忆检索 + 预算裁剪 |
| Search Tools | `search_tools.py` | 四级混合检索管线 |
| Knowledge Agent | `knowledge_agent.py` | LLM 决策（是否需要 CRUD） |
| Sync Manager | `sync_manager.py` | 四路存储同步 |
| CRUD Tools | `crud_tools.py` | 知识 CRUD 操作 |
| Wiki Service | `wiki/service.py` | 文件级 CRUD + YAML frontmatter |
| Chat Router | `routers/chat.py` | SSE 流式对话 API |

---

## 4. LangGraph 图结构详解

### 4.1 图结构

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

### 4.2 各节点详解

**search 节点**：
- 查询复杂度分类（TRIVIAL/SIMPLE/MEDIUM/COMPLEX）
- 并行加载用户记忆 + 会话记忆
- TRIVIAL 跳过 RAG，COMPLEX 走完整四级管线
- Query Rewriter 改写查询

**respond 节点**：
- 预算感知上下文组装
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

### 4.3 状态定义

```python
class WikiState(TypedDict):
    user_message: str
    chat_history: list[BaseMessage]
    context: RetrievedContext
    response: str
    wiki_action: str  # "none" / "create" / "update" / "delete"
    wiki_target: str
    wiki_content: str
    confirmed: bool
```

### 4.4 SQLite Checkpoint

每个节点执行后状态持久化到 `checkpoints.db`。`interrupt()` 调用时整个 WikiState 被序列化，支持暂停/恢复。

---

## 5. 四级混合检索管线

### 5.1 流程图

```
用户查询
    ↓ Query Rewriter（LLM 改写，生成 2-3 个语义等价 query）
    ↓ 并行执行
    ┌─────────────────┐    ┌─────────────────┐
    │  语义搜索        │    │  BM25 关键词搜索  │
    │  (Milvus 向量库) │    │  (jieba 分词)     │
    │  BGE-small-zh   │    │  Okapi BM25      │
    └────────┬────────┘    └────────┬────────┘
             └──────┬───────────────┘
                    ↓
            RRF 融合（k=60）
            score(d) = Σ 1/(k + rank_i(d) + 1)
                    ↓
            Cross-Encoder 重排序（可选）
            bge-reranker-base (~1GB)
                    ↓
            路径去重（同一文档多个 chunk 只保留最高分）
                    ↓
            Top-K 结果
```

### 5.2 为什么用 RRF 而不是加权融合？

RRF 只看排名不看原始分数，完美解决了 cosine similarity（0-1）和 BM25 TF-IDF 分数（无界）的量纲不一致问题。公式：`score(d) = Σ 1/(k + rank_i(d) + 1)`，k=60。

### 5.3 候选集过采样

```python
recall_limit = max(limit * RERANK_CANDIDATE_MULTIPLIER, limit * 2)
# 返回 10 个结果时，先取 20-30 个候选给 reranker
```

### 5.4 优雅降级

| 组件 | 降级策略 |
|------|----------|
| 语义搜索失败 | 降级到关键词搜索 |
| Reranker 不可用 | 跳过 rerank，返回 RRF 顺序 |
| Embedding 模型加载失败 | 返回零向量，语义搜索返回空，BM25 仍可用 |

---

## 6. 知识管理系统

### 6.1 CRUD 操作

| 操作 | 流程 |
|------|------|
| Create | LLM 生成内容 → HITL 确认 → 写 Markdown → 同步 Milvus/BM25 → Git commit |
| Read | 读 Markdown → 解析 YAML frontmatter → 返回 Entry |
| Update | 读现有 → LLM 修改 → HITL 确认 → 写 Markdown → Delete-then-insert Milvus → Git commit |
| Delete | 删除 Markdown → 删除 Milvus chunk → 删除 BM25 条目 → Git commit |

### 6.2 四路同步（Sync Manager）

```python
async def sync_all(entry, content, category, tags):
    # 1. 写 Markdown（失败则后续全部跳过）
    await write_markdown_file(entry, content)

    # 2. 同步向量库（失败不回滚 Markdown）
    try:
        await sync_to_vector_store(entry, content)
    except Exception:
        logger.error("Vector sync failed")

    # 3. 同步 BM25（失败不回滚前两步）
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

**设计选择**：明确选择最终一致性，不追求强一致性。四个存储系统的事务语义不同，强行统一会增加大量复杂度。

### 6.3 YAML Frontmatter

```yaml
---
title: OAuth 认证机制
summary: 项目的 OAuth 2.0 实现说明
category: development/auth
aliases: [oauth, 认证]
tags: [security, api]
source: manual
created: 2026-06-01
updated: 2026-07-01
---
```

### 6.4 Wikilink 解析

支持 Obsidian 风格 `[[page name]]` 链接。三级匹配优先级：精确路径 → 文件名 → 标题。

---

## 7. 三层记忆架构

### 7.1 架构图

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

### 7.2 事实提取流程

```python
# 1. 正则预过滤：简单消息跳过 LLM 调用
if is_simple_query(message):  # "你好"、"谢谢"
    return

# 2. LLM 提取事实 + 判定范围
facts = await llm.extract_facts(message, existing_memory)
# 每个 fact 有 scope: user（跨会话）或 session（当前会话）

# 3. 异步写入（不阻塞主响应流）
asyncio.create_task(_store_memories(facts))
```

### 7.3 冲突感知提取

prompt 中包含现有记忆，让 LLM 处理矛盾：
- 偏好变化：用户说"我现在用 Go 了"→ 更新 user memory
- 不同上下文：同一问题在不同项目中有不同答案 → 分别存储

---

## 8. 预算感知上下文组装

### 8.1 优先级裁剪

```
总预算 = 3000 字符
    ↓
优先级 1: 用户记忆        600 字符  ← 永不截断
优先级 2: 会话记忆        400 字符  ← 永不截断
优先级 3: 外部知识库     1200 字符  ← 可能被截断
优先级 4: 工作记忆        800 字符  ← 最先被截断
```

高优先级的记忆永不被截断，低优先级的在预算不足时被裁剪。

### 8.2 查询复杂度自适应

```python
complexity = classify_complexity(query)
if complexity == "TRIVIAL":
    # "你好"、"谢谢" → 跳过 RAG，只加载记忆
    pass
elif complexity == "SIMPLE":
    # "什么是 OAuth" → 语义搜索，跳过 rerank
    results = await semantic_search(query)
elif complexity == "COMPLEX":
    # "认证机制有哪些安全考虑" → 完整四级管线 + rerank
    results = await hybrid_search(query, with_rerank=True)
```

---

## 9. Human-in-the-Loop

### 9.1 暂停/恢复流程

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

### 9.2 关键技术细节

- **SQLite checkpointing**：AsyncSqliteSaver 在每个节点执行后持久化状态
- **SSE 解耦**：Graph 在后台 task 执行，通过 asyncio.Queue 推送 token
- **CRUD 失败自动重规划**：create 失败→重试 update，update 失败→重试 create

---

## 10. SSE 流式对话

### 10.1 事件类型

| 事件 | 说明 |
|------|------|
| `content` | LLM 生成的 token |
| `wiki_results` | 知识库检索结果 |
| `extraction` | 提取的知识（待确认） |
| `status` | 进度信息 |
| `done` | 完成 |
| `error` | 错误 |

### 10.2 会话管理

- 消息截断：只加载最近 10 轮对话（20 条消息）
- 自动命名：第一条消息作为会话名（截断到 30 字符）

---

## 11. Query 改写与复杂度分类

### 11.1 Query Rewriter

LLM 将用户查询改写为 2-3 个语义等价的搜索 query，提高召回率。

```
用户："认证机制怎么实现的？"
改写后：
  1. "OAuth 2.0 认证流程"
  2. "JWT token 验证"
  3. "用户登录认证实现"
```

### 11.2 复杂度分类

| 级别 | 示例 | 处理方式 |
|------|------|----------|
| TRIVIAL | "你好"、"谢谢" | 跳过 RAG |
| SIMPLE | "什么是 OAuth" | 语义搜索，跳过 rerank |
| MEDIUM | "项目的认证方式" | 语义 + BM25 |
| COMPLEX | "认证机制的安全考虑和优化方案" | 完整四级管线 + rerank |

---

## 12. 分块策略与 Embedding

### 12.1 分块参数

- chunk_size: 500 字符
- chunk_overlap: 50 字符
- 分隔符优先级：`\n\n` → `\n` → `。` → `！` → `？` → `；` → `，`
- `keep_separator=True`：在中文句子边界断开

### 12.2 Embedding

- 模型：BAAI/bge-small-zh-v1.5（512 维）
- 拼接策略：`title + chunk` 作为输入，确保向量同时捕获主题和内容
- 本地优先：先检查本地目录，再 fallback 到 HuggingFace

---

## 13. Milvus 向量存储

### 13.1 gRPC 调优

```python
# 在任何 gRPC import 之前设置
os.environ["GRPC_KEEPALIVE_TIME_MS"] = "120000"  # 默认 10s → 120s
```

Milvus Lite 的默认 keepalive 过于激进（10s），导致频繁 GOAWAY 错误。

### 13.2 重试机制

gRPC GOAWAY 或 ENHANCE_YOUR_CALM 错误时，重置客户端连接并重试最多 2 次。

### 13.3 Delete-then-insert

更新时先删除旧 chunk，再插入新 chunk。处理 chunk 数量变化的情况。

---

## 14. Git 集成与版本管理

### 14.1 自动 commit

每次知识变更自动 Git commit，保留变更历史。

### 14.2 回滚机制

```python
async def rollback(entry, commit_hash):
    # 1. 用 Git 恢复文件到指定 commit
    git checkout {commit_hash} -- {file_path}
    # 2. 重新索引该页面
    await reindex_page(entry)
```

### 14.3 全量重建

`reindex_all()` 遍历所有 `.md` 文件，从头重建 Milvus 和 BM25。用于 bootstrap 和故障恢复。

---

## 15. 与评估平台的集成

### 15.1 轨迹采集

Wiki Agent 的每一步都通过 TrajectoryCollector 记录：

```python
# search 节点
collector.record("retrieval", query=query, result_count=len(results))
collector.record("evidence", evidence_type="rag", sources={...})

# respond 节点
collector.record("think", thought=llm_response)
collector.record("memory_write", key="user_pref", value="Python")

# execute 节点
collector.record("tool_call", tool_name="create_knowledge", input={...})
collector.record("tool_result", success=True, duration_ms=120)
```

### 15.2 数据流

```
Wiki Agent 产生轨迹 → SDK Collector → 评估平台 API → 6 维评估 → 质量分数
```

这就是"评估平台的试验田"——Wiki Agent 的真实轨迹数据驱动了评估体系的验证和迭代。

---

## 16. 核心难点与解决方案

### 16.1 四级混合检索的精度问题

**问题**：纯向量搜索对中文短查询效果差，纯关键词搜索无法处理同义词。

**解决方案**：RRF 融合语义搜索和 BM25，再用 Cross-Encoder rerank。RRF 只看排名不看分数，解决量纲不一致问题。

### 16.2 四路存储一致性

**问题**：Markdown + Milvus + BM25 + Git 四个存储系统，没有分布式事务。

**解决方案**：最终一致性 + 顺序写入。Markdown 先写（失败则后续跳过），其他系统逐个同步（失败不回滚）。提供全量重建能力作为恢复手段。

### 16.3 HITL 暂停/恢复

**问题**：HTTP 请求-响应周期中如何实现"暂停等待用户确认"？

**解决方案**：LangGraph interrupt + SQLite checkpoint。Graph 在后台 task 执行，interrupt() 暂停并序列化状态，用户确认后从 checkpoint 恢复。

### 16.4 预算感知上下文

**问题**：4 个记忆来源竞争有限的 token 预算。

**解决方案**：优先级裁剪。用户记忆（600 字符）> 会话记忆（400）> 知识库（1200）> 工作记忆（800）。高优先级永不截断。

### 16.5 Milvus Lite gRPC 稳定性

**问题**：默认 keepalive 10s 过于激进，频繁 GOAWAY。

**解决方案**：环境变量调优到 120s + GOAWAY 重试机制。

### 16.6 Reranker 模型下载

**问题**：ModelScope 下载有时把权重留在临时目录。

**解决方案**：检测 `._____temp` 目录，将 ≥900MB 的文件提升到模型根目录。加载失败时静默降级。

### 16.7 BM25 中文分词

**问题**：通用分词器对技术文档效果差。

**解决方案**：jieba 分词 + 50+ 中文停用词 + 过滤单字符 token。惰性重建（_dirty 标记）+ pickle 持久化。

### 16.8 记忆冲突

**问题**：用户偏好变化时，新旧记忆矛盾。

**解决方案**：冲突感知提取。prompt 中包含现有记忆，让 LLM 判断是"偏好变化"还是"不同上下文"。

### 16.9 CRUD 失败恢复

**问题**：create 时文档已存在，update 时文档不存在。

**解决方案**：自动重规划。create 失败（"已存在"）→ 重试 update，update 失败（"不存在"）→ 重试 create。

### 16.10 知识图谱构建

**问题**：如何从 Markdown 文件构建知识关联图？

**解决方案**：解析所有 `[[wikilink]]`，构建有向图（source→target）。支持反向链接查询（谁引用了这个页面）。

---

## 17. 面试高频问答

### Q1：Wiki Agent 和普通 RAG 有什么区别？

**A**：三个核心差异。第一，检索方式——我们是四级混合（语义 + BM25 + RRF + Rerank），普通 RAG 通常只有向量搜索。第二，记忆系统——我们有三层记忆（用户/会话/工作），普通 RAG 无记忆。第三，写入能力——我们支持 CRUD 全操作 + HITL 确认，普通 RAG 是只读的。

### Q2：四路同步的一致性怎么保证？

**A**：我们选择最终一致性而不是强一致性。Markdown 先写（作为 source of truth），然后依次同步 Milvus、BM25、Git。每步独立 try-catch，失败不回滚前面的步骤。提供全量重建能力作为恢复手段。这个设计是明确的 trade-off：牺牲强一致性换取简单性和可用性。

### Q3：HITL 的暂停/恢复是怎么实现的？

**A**：LangGraph 的 interrupt + SQLite checkpoint。Graph 在后台 task 中执行，到 execute 节点时调用 interrupt()，整个 WikiState 被序列化到 checkpoints.db。前端通过 SSE 收到暂停信号后显示确认对话框。用户确认后，调用 graph.ainvoke(Command(resume=True), config) 从 checkpoint 恢复执行。

### Q4：为什么用 RRF 而不是加权融合？

**A**：RRF 只看排名不看原始分数。cosine similarity 范围是 0-1，BM25 TF-IDF 分数是无界的，直接加权融合需要归一化，而且归一化后的权重很难调。RRF 用 `score(d) = Σ 1/(k + rank_i(d) + 1)` 公式，k=60，完全消除了量纲问题。

### Q5：预算感知上下文是怎么裁剪的？

**A**：4 个记忆来源按优先级排列：用户记忆（600 字符）> 会话记忆（400）> 知识库（1200）> 工作记忆（800）。总预算 3000 字符。高优先级的记忆先分配预算，永不截断。低优先级的在预算不足时被裁剪。这样确保用户偏好永远不会被截断。

### Q6：Milvus Lite 的 gRPC 问题怎么解决的？

**A**：Milvus Lite 的默认 keepalive 是 10 秒，过于激进，导致频繁 GOAWAY 错误。我们在任何 gRPC import 之前通过环境变量调优到 120 秒。同时实现了重试机制：检测到 GOAWAY 或 ENHANCE_YOUR_CALM 错误时，重置客户端连接并重试最多 2 次。

### Q7：Query Rewriter 的作用是什么？

**A**：将用户查询改写为 2-3 个语义等价的搜索 query，提高召回率。比如"认证机制怎么实现的"会被改写为"OAuth 2.0 认证流程"、"JWT token 验证"、"用户登录认证实现"。每个改写后的 query 分别做语义搜索和 BM25，然后 RRF 融合。

### Q8：三层记忆的区别是什么？

**A**：用户记忆跨会话永久存储，记录用户偏好和技术栈。会话记忆单次会话有效，记录当前任务的上下文和发现。工作记忆是内存中的最近 10 条消息，用于短期对话上下文。LLM 在提取事实时会判断 scope（user 或 session），决定存到哪一层。

### Q9：CRUD 失败时的自动重规划是怎么做的？

**A**：简单的错误恢复策略。create 失败且错误是"已存在"→ 自动重试为 update。update 失败且错误是"不存在"→ 自动重试为 create。这是在 graph.py 的 execute 节点中实现的，不需要额外的重规划逻辑。

### Q10：分块策略为什么用中文分隔符优先？

**A**：RecursiveCharacterTextSplitter 的默认分隔符是英文的（\n\n, \n, . 等）。中文文档用这些分隔符会在句子中间断开，破坏语义完整性。我们把中文分隔符（。！？；，）放在优先位置，确保 chunk 在中文句子边界断开。keep_separator=True 保留分隔符在 chunk 中。

### Q11：Embedding 时为什么拼接 title？

**A**：单独的 chunk 文本可能缺少上下文（比如一个代码片段不知道属于哪个主题）。拼接 `title + chunk` 后，向量同时捕获主题和内容信息，检索时效果更好。

### Q12：BM25 的惰性重建是什么？

**A**：BM25Okapi 实例在内存中维护。每次写入操作设置 `_dirty = True`，下次搜索时检查 dirty 标记，如果 dirty 则重建索引，否则直接使用缓存的实例。避免每次搜索都重新计算。BM25 索引通过 pickle 持久化到磁盘，冷启动时直接加载。

### Q13：知识图谱是怎么构建的？

**A**：解析所有 Markdown 文件中的 `[[wikilink]]`，构建有向图（source→target）。节点是页面，边是 wikilinks。支持反向链接查询（`get_backlinks`）：扫描所有文件找到指向目标页面的链接，提取周围行作为 snippet。

### Q14：Wiki Agent 的轨迹数据怎么被评估平台使用？

**A**：Wiki Agent 的每一步（search、respond、decide、execute）都通过 TrajectoryCollector 记录为标准的 ActionType（retrieval、think、tool_call 等）。这些轨迹数据被发送到评估平台的 API，由 6 个评估器分析，形成质量分数。这就是"评估平台的试验田"的含义。

### Q15：系统中有哪些优雅降级？

**A**：四处。Milvus 不可用时语义搜索返回空，BM25 仍可用。Reranker 模型不可用时跳过 rerank，返回 RRF 顺序。Embedding 模型加载失败时返回零向量。Redis 不可用时缓存操作静默返回 None。系统在任何单一组件故障时都能继续工作。

---

## 18. 常见陷阱与避坑指南

### 陷阱 1：Milvus Lite 的 gRPC 环境变量必须在 import 前设置

```python
# ❌ 错误：先 import pymilvus 再设置环境变量
from pymilvus import MilvusClient
os.environ["GRPC_KEEPALIVE_TIME_MS"] = "120000"  # 已经太晚了

# ✅ 正确：先设置环境变量再 import
os.environ["GRPC_KEEPALIVE_TIME_MS"] = "120000"
from pymilvus import MilvusClient
```

### 陷阱 2：LangGraph interrupt 后必须用 Command resume

```python
# ❌ 错误：用普通 input 重新调用
result = await graph.ainvoke({"confirmed": True}, config)

# ✅ 正确：用 Command(resume=...)
result = await graph.ainvoke(Command(resume=True), config)
```

### 陷阱 3：BM25 搜索结果需要路径去重

同一个 wiki 页面可能产生多个 chunk，搜索结果需要按路径去重，只保留最高分的 chunk。否则同一个页面会多次出现在结果中。

### 陷阱 4：asyncio.create_task 的异常处理

```python
# ❌ 错误：fire-and-forget 不处理异常
asyncio.create_task(_store_memories(facts))  # 异常会被静默吞掉

# ✅ 正确：添加回调处理异常
task = asyncio.create_task(_store_memories(facts))
task.add_done_callback(lambda t: t.exception() and logger.error(...))
```

### 陷阱 5：SQLite 的并发写入限制

SQLite 在写入时会锁表。Wiki Agent 的 checkpoint 写入和知识 CRUD 写入可能冲突。解决方案：使用 WAL 模式（`PRAGMA journal_mode=WAL`）或切换到 PostgreSQL。

### 陷阱 6：YAML frontmatter 解析的正则边界

```python
# ❌ 错误：贪婪匹配
re.match(r'^---\n(.*?)\n---', content, re.DOTALL)  # 可能匹配到正文中的 ---

# ✅ 正确：非贪婪 + 严格锚定
re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
```

### 陷阱 7：Reranker 模型的内存占用

bge-reranker-base 约 1GB，加载到内存后常驻。如果服务器内存不足，需要在配置中禁用 rerank（`RERANK_ENABLED=false`）。

---

## 19. 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 检索 Top-1 准确率 | 75% | BGE-small-zh + RRF 混合检索 |
| MRR | 0.825 | Mean Reciprocal Rank |
| 首 token 延迟 | <500ms | SSE 流式输出 |
| 单次检索耗时 | ~200ms | 语义搜索 + BM25 并行 |
| Rerank 额外开销 | ~300ms | bge-reranker-base 推理 |
| 知识库规模 | ~1000 篇文档 | Milvus Lite + BM25 pickle |
| 记忆提取开销 | ~1s | LLM 调用，异步不阻塞响应 |
| Embedding 维度 | 512 | bge-small-zh-v1.5 |
| Chunk 大小 | 500 字符 | 50 字符 overlap |
| RRF k 参数 | 60 | 标准值 |
