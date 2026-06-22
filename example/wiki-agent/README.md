<div align="center">

# Wiki Agent

> *你的个人知识库，会自己长大。*

**AI 驱动的知识管理系统 — 对话即录入，搜索即召回。**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-green.svg)](https://fastapi.tiangolo.com)
[![Vue 3](https://img.shields.io/badge/Vue-3-brightgreen.svg)](https://vuejs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 这是什么

Wiki Agent 是一个 **AI 驱动的个人知识库管理系统**。它与传统笔记工具的核心区别：

- **对话即录入** — 聊天中提到的知识点，AI 自动判断是否存下来
- **混合检索** — BM25 精确匹配 + 向量语义理解，两路召回、RRF 融合排序
- **自动版本控制** — 每次修改自动 Git 提交，改错随时回滚
- **Agent 思考** — 不只是搜，还会判断"要不要更新知识库"

## 实测指标

| 指标 | 数值 |
|------|------|
| 检索测试集 | **20 条** 中文查询 |
| Semantic Top-1 / MRR | **85.0%** / **0.91** |
| BM25 Top-1 / MRR | **80.0%** / **0.85** |
| Hybrid Top-1 / MRR | **85.0%** / **0.87** |
| 搜索策略 | **3 种** (ChromaDB 向量 / BM25 关键词 / RRF 融合) |
| StateGraph 节点 | **4 个** (search → respond → decide → execute) |
| 同步链路 | **4 路** (Markdown → ChromaDB → BM25 → Git) |
| SSE 事件类型 | **7 种** |

*数据来源: `tests/eval_retrieval_standalone.py`，17 篇知识库文档。*

## 快速开始

```bash
# 配置
cp .env.example .env
# 编辑 .env: 填入 DEEPSEEK_API_KEY

# 安装
pip install -e ".[dev]"

# 启动（Wiki-Agent 集成在主平台中）
python -m app.main
```

访问: http://localhost:3000/wiki-agent

## 架构概览

```
用户提问
    │
    ▼
┌─────────────────────────────────────────┐
│         LangGraph Agent                  │
│                                          │
│  search ──→ respond ──→ decide ──→ execute
│    │           │           │          │
│    │      条件路由:       │    Human-in-the-Loop
│    │    >50 chars→decide  │    CRUD 确认
│    │    else→END          │          │
│    │                  create/update/   │
│    │                  delete/none      │
│    ▼                                    │
│  AsyncSqliteSaver Checkpoint            │
│  (中断恢复)                              │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│         三级混合检索                      │
│                                          │
│  Semantic (BGE-M3 + cosine)              │
│       + BM25 (jieba + rank_bm25)         │
│       + RRF 融合 (k=60)                  │
│       → 去重保留最高分 chunk              │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│         四路实时同步                      │
│                                          │
│  Markdown ←→ ChromaDB ←→ BM25 ←→ Git    │
│  (500 字符 chunk · 50 重叠 · 句边界感知)  │
└─────────────────────────────────────────┘
```

## 检索原理

### BM25 关键词搜索
- jieba 分词 → 去除停用词 (25 词) → rank_bm25 倒排索引
- 适用: 精确术语匹配 (如 "Kubernetes 容器编排")

### ChromaDB 语义搜索
- SentenceTransformer BGE-M3 向量嵌入 → cosine 距离
- 适用: 语义相似查询 (如 "怎么管理集群" 匹配 Kubernetes 文档)

### RRF 倒数秩融合
- 两路结果取 rank → RRF score = Σ 1/(k + rank), k=60
- 按文档去重，保留每个文档最高分 chunk

## 知识自动提取

对话结束后，Agent 自动分析对话内容：

```
对话记录 → PydanticOutputParser → KnowledgeDecision
                                      │
                          ┌───────────┼───────────┐
                          ▼           ▼           ▼
                       create      update      delete/none
                          │           │
                    人工确认 ←─────┘
                          │
                    四路同步写入
```

## API 接口

### 知识管理
```http
GET    /api/wiki/tree                      # 知识库目录树
GET    /api/wiki/page/{path}               # 获取页面内容
POST   /api/wiki/create                    # 创建页面
PUT    /api/wiki/update/{path}             # 更新页面
DELETE /api/wiki/page/{path}               # 删除页面
POST   /api/wiki/rollback/{path}           # Git 回滚
GET    /api/wiki/history/{path}            # 版本历史
GET    /api/wiki/search?q={query}          # 搜索
```

### 对话
```http
POST   /api/chat/stream                    # SSE 流式对话 (7 种事件)
POST   /api/chat/confirm                   # Human-in-the-Loop 确认
GET    /api/chat/sessions                  # 会话列表
```

### SSE 事件类型

| 事件 | 说明 |
|------|------|
| `content` | LLM 流式文本 |
| `wiki_results` | 知识库检索结果 |
| `status` | 状态消息 |
| `extraction` | 知识提取决策 |
| `evaluation_task` | 评估追踪 ID |
| `error` | 错误事件 |
| `done` | 流结束 |

## 技术栈

**后端**: Python 3.11+ · FastAPI · LangGraph · LangChain · ChromaDB · SentenceTransformers · jieba · rank-bm25 · GitPython · aiosqlite

**前端**: Vue 3 · TypeScript · Element Plus · Markdown 渲染

**LLM**: DeepSeek (ChatOpenAI 兼容)
