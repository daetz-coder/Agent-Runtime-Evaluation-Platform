<div align="center">

# Wiki Agent

> *你的个人知识库，会自己长大。*

**AI 驱动的知识管理系统 — 对话即录入，搜索即召回。**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green.svg)](https://fastapi.tiangolo.com)
[![Vue 3](https://img.shields.io/badge/Vue-3-brightgreen.svg)](https://vuejs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<br>

聊天中随口提到的知识点，AI 自动判断要不要存下来。<br>
搜一个问题，BM25 精确匹配 + 向量语义理解，两路召回、融合排序。<br>
每次修改自动 Git 提交，改错了随时回滚。<br>

**不是笔记工具，是一个会思考的知识助手。**

<br>

[功能特性](#功能特性) · [快速开始](#快速开始) · [架构概览](#架构概览) · [检索原理](#检索架构) · [API 接口](#api-接口)

</div>

---

## 功能特性

| 能力 | 说明 |
|------|------|
| **知识条目管理** | 创建、编辑、删除 Markdown 知识条目，支持多级目录分类 |
| **Git 版本控制** | 每次修改自动提交，支持历史查看和版本回滚 |
| **混合检索** | BM25 关键词检索（jieba 分词 + TF-IDF）+ BGE 向量语义搜索，RRF 融合排序 |
| **AI 对话** | 基于 GLM-4 的流式对话（SSE），自动搜索知识库作为上下文 |
| **知识自动提取** | LangGraph Agent 分析对话，决策是否需要创建/更新/删除知识条目 |
| **Human-in-the-Loop** | Agent 决策后暂停等待用户确认，确认后才执行操作 |
| **三端同步** | 每次写操作同步更新 Markdown + ChromaDB + BM25 + Git |
| **持久化 Checkpoint** | Agent 状态持久化到 SQLite，重启不丢失中断上下文 |
| **启动自检** | 首次启动自动同步 ChromaDB 和 BM25 索引，按需补齐 |

---

## 快速开始

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
# 编辑 .env 文件，填入 ZhipuAI API Key

# 启动服务
# 首次启动自动同步知识库到 ChromaDB 向量索引 + BM25 倒排索引
# LangGraph Checkpoint 自动初始化到 backend/data/checkpoints.db
python run_server.py
```

后端运行在 `http://localhost:8001`

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端运行在 `http://localhost:5173`，API 请求自动代理到后端 8001 端口。

### 3. 一键启动（Windows）

```bash
start.bat
```

---

## 架构概览

```
用户消息 → FastAPI (SSE)
              │
              ▼
         LangGraph Agent
         ┌─────────────────────────────────────────┐
         │ search → respond → decide → [interrupt] → execute │
         └─────────────────────────────────────────┘
              │                          │
         混合检索                    用户确认后执行
         ┌────┴────┐                ┌────┴────┐
     BM25 搜索  向量搜索        Markdown  ChromaDB
     (jieba)   (BGE+ChromaDB)    + Git    + BM25
         └────┬────┘                └────┬────┘
         RRF 融合排序               WikiSyncManager
```

### 项目结构

```
wiki-agent/
├── backend/                        # Python 后端
│   ├── app/
│   │   ├── agent/
│   │   │   ├── graph.py            # LangGraph 状态机编排
│   │   │   ├── knowledge_agent.py  # 知识决策 Agent（LLM 结构化输出）
│   │   │   └── tools/
│   │   │       ├── search_tools.py # 混合检索（语义 + BM25 + RRF）
│   │   │       ├── bm25_index.py   # BM25 倒排索引（jieba + rank_bm25）
│   │   │       ├── crud_tools.py   # 知识库 CRUD 操作
│   │   │       ├── chunker.py      # 文本分块（Markdown 结构感知）
│   │   │       └── sync_manager.py # 三端同步管理器
│   │   ├── routers/
│   │   │   ├── wiki.py             # 知识库 REST API
│   │   │   └── chat.py             # 对话 API（SSE 流式 + 确认）
│   │   ├── wiki/
│   │   │   ├── service.py          # Markdown 文件 CRUD
│   │   │   ├── git_service.py      # Git 版本管理
│   │   │   └── schemas.py          # Pydantic 数据模型
│   │   ├── session/
│   │   │   └── store.py            # 会话存储（SQLite）
│   │   ├── config.py               # 配置（路径、API Key）
│   │   ├── database.py             # SQLite 初始化
│   │   └── main.py                 # FastAPI 入口
│   ├── requirements.txt
│   └── .env                        # 环境变量
├── frontend/                       # Vue 3 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── App.vue             # 根组件（Wiki/Chat 模式切换）
│   │   │   ├── Sidebar.vue         # 目录树侧边栏
│   │   │   ├── WikiPage.vue        # 知识条目查看/编辑
│   │   │   ├── ChatView.vue        # AI 对话界面（SSE + 知识提取卡片）
│   │   │   ├── HistoryPanel.vue    # Git 历史面板
│   │   │   ├── CreateDialog.vue    # 新建条目弹窗
│   │   │   └── ImportDialog.vue    # 导入弹窗
│   │   └── api/
│   │       └── index.js            # API 封装
│   ├── vite.config.js
│   └── package.json
├── knowledge/                      # 知识库文件（Git 管理）
├── models/                         # 本地 Embedding 模型
│   └── bge-small-zh-v1.5/          # BAAI BGE 中文小模型（512 维）
├── chroma_db/                      # ChromaDB 向量存储
├── start.bat                       # Windows 一键启动
└── README.md
```

---

## Demo

### 知识库管理

多级目录分类，Markdown 编辑，Git 版本控制。

![知识库管理](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260527202032020.png)

### AI 对话

基于知识库上下文的流式对话，SSE 实时推送。

![AI 对话](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260527202105795.png)

### 知识自动提取

Agent 分析对话内容，自动发现可保存的知识，用户确认后写入知识库。

![知识自动提取](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260527202132412.png)

### 混合检索

BM25 关键词精确匹配 + BGE 向量语义搜索，RRF 融合排序。

![混合检索](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260527202245624.png)

---

## 检索架构

### 混合检索（Hybrid Search）

```
用户查询
   │
   ├── jieba 分词 → BM25 搜索 → 排名列表
   │                              │
   └── BGE 编码 → ChromaDB 余弦搜索 → 排名列表
                                           │
                                    RRF 融合 (k=60)
                                    score = Σ 1/(k + rank_i)
                                           │
                                     最终排序结果
```

| 检索方式 | 原理 | 擅长场景 |
|----------|------|----------|
| **BM25** | jieba 分词 + TF-IDF 加权 + 长度归一 | 精确关键词匹配（函数名、专有名词） |
| **向量搜索** | bge-small-zh-v1.5 编码 + ChromaDB 余弦相似度 | 语义理解（"土豆"→"马铃薯"） |
| **RRF 融合** | 抛弃绝对分数，只看排名：`1/(60+rank)` | 解决两路分数尺度不同的问题 |

### 文本分块策略

采用 Markdown 结构感知分块：
1. 按 `#` 标题切分章节
2. 每个章节按 500 字符切块，保留句子边界
3. 标题注入到第一块，保留上下文

---

## Human-in-the-Loop 流程

```
用户提问 → Agent 搜索 + 回复 + 决策
                         │
                    interrupt() 暂停
                         │
              Checkpoint 保存到 SQLite
                         │
               SSE 推送 extraction 事件给前端
                         │
              前端渲染确认卡片（含 thread_id）
                    ┌────┴────┐
                 确认保存    忽略
                    │         │
           POST /confirm   POST /confirm
           (confirm=true)  (confirm=false)
                    │         │
         Command(resume=True)  Command(resume=False)
                    │         │
              执行 CRUD     取消操作
                    │         │
         extraction 状态写回 DB（confirmed / rejected）
```

Checkpoint 持久化到 `backend/data/checkpoints.db`（SQLite），后端重启后仍可恢复中断状态。

---

## 数据持久化

```
wiki-agent/
├── knowledge/                      # Markdown 源文件（Git 管理）
├── chroma_db/                      # ChromaDB 向量索引
├── models/bge-small-zh-v1.5/       # 本地 Embedding 模型
└── backend/data/
    ├── chat.db                     # 会话 + 消息存储
    ├── checkpoints.db              # LangGraph Agent 状态（interrupt 恢复）
    └── bm25_index.pkl              # BM25 倒排索引
```

| 文件 | 说明 |
|------|------|
| `chat.db` | 存储会话和消息，含 extraction 状态（confirmed/rejected） |
| `checkpoints.db` | 存储 LangGraph 图的 checkpoint，支持 interrupt 后重启恢复 |
| `bm25_index.pkl` | jieba 分词后的 BM25 索引，启动时自动从 knowledge 目录构建 |

---

## 配置说明

在 `backend/.env` 中配置：

```env
# LLM 配置（智谱 GLM-4）
ZHIPUAI_API_KEY=your-api-key
ZHIPUAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZHIPUAI_CHAT_MODEL=glm-4

# Git 版本管理
GIT_ENABLED=true
```

路径配置在 `backend/app/config.py`，默认：

| 配置项 | 默认路径 | 说明 |
|--------|----------|------|
| `KNOWLEDGE_DIR` | `wiki-agent/knowledge/` | 知识库 Markdown 文件 |
| `CHROMA_DIR` | `wiki-agent/chroma_db/` | ChromaDB 向量存储 |
| `EMBEDDING_MODEL_PATH` | `wiki-agent/models/bge-small-zh-v1.5/` | 本地 Embedding 模型 |
| `DB_PATH` | `wiki-agent/backend/data/chat.db` | SQLite 会话数据库 |
| `BM25_INDEX_PATH` | `wiki-agent/backend/data/bm25_index.pkl` | BM25 索引持久化文件 |
| `CHECKPOINT_DB` | `wiki-agent/backend/data/checkpoints.db` | LangGraph Agent 状态持久化（自动） |

---

## API 接口

### 知识库 API (`/api/wiki`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tree` | 获取目录树 |
| GET | `/page/{path}` | 读取条目 |
| POST | `/page/{path}` | 创建条目 |
| PUT | `/page/{path}` | 更新条目 |
| DELETE | `/page/{path}` | 删除条目 |
| GET | `/search?q=xxx` | 搜索条目 |
| GET | `/page/{path}/history` | 获取 Git 历史 |
| POST | `/page/{path}/rollback` | 回滚版本 |
| POST | `/import` | 导入 Markdown |

### 对话 API (`/api/chat`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/stream` | SSE 流式对话 |
| POST | `/message` | 非流式对话 |
| POST | `/confirm` | 确认/取消知识操作 |
| POST | `/save-knowledge` | 手动保存知识 |
| GET/POST | `/sessions` | 会话管理 |

### SSE 事件类型（`/api/chat/stream`）

| type | 说明 |
|------|------|
| `wiki_results` | 知识库搜索结果 |
| `content` | 流式回复文本片段 |
| `status` | 状态信息（如"正在分析对话内容..."） |
| `extraction` | 知识提取结果（含 `thread_id`，等待用户确认） |
| `done` | 流式结束 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| Agent 编排 | LangGraph（状态机 + interrupt） |
| LLM | 智谱 GLM-4（结构化输出 / PydanticOutputParser 双策略） |
| 向量存储 | ChromaDB（余弦相似度） |
| Embedding | bge-small-zh-v1.5（本地推理，512 维） |
| 关键词检索 | jieba 分词 + rank_bm25（BM25Okapi） |
| 融合策略 | RRF（Reciprocal Rank Fusion, k=60） |
| 版本管理 | GitPython |
| Checkpoint 存储 | AsyncSqliteSaver（SQLite 持久化，重启不丢失） |
| 会话存储 | SQLite + aiosqlite |
| 前端 | Vue 3 + Vite + vue-router |
| 流式传输 | SSE（Server-Sent Events） |
