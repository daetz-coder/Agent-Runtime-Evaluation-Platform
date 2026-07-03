# Wiki Agent

基于 RAG（检索增强生成）的个人知识库问答系统，支持自动知识沉淀、四路记忆、四端同步。

---

## 核心能力

- **智能问答**：LangGraph 编排，四路记忆检索，流式对话
- **知识沉淀**：对话中自动识别有价值的知识，Human-in-the-Loop 确认后写入
- **四端同步**：Markdown + Milvus + BM25 + Git 最终一致性
- **六层压缩**：SQL 截断 → 滑动窗口 → 二次保护 → 字符预算 → LLM 提炼 → 分块截断

---

## 快速开始

### 1. 环境准备

```bash
# Python 3.10+
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 或 ZHIPUAI_API_KEY
```

### 2. 启动后端

```bash
# 方式 1：作为评估平台子系统启动（推荐）
cd ../.. && python -m uvicorn app.main:app --reload --port 8000

# 方式 2：独立启动（需要创建启动脚本，见下方）
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`

---

## 项目结构

```
wiki_agent/
├── config.py                    # 全局配置（读取 .env）
├── database.py                  # SQLite 初始化
├── bootstrap.py                 # 启动引导（目录、种子数据、索引同步）
│
├── agent/                       # 智能体层
│   ├── graph.py                 # LangGraph 编排（search → respond → decide → execute）
│   ├── knowledge_agent.py       # 知识库 CRUD 决策器
│   ├── context_retriever.py     # 四路记忆检索 + 预算裁剪
│   ├── auto_tagger.py           # LLM 自动标签
│   ├── eval_middleware.py       # 评估中间件
│   └── tools/                   # 工具集
│       ├── search_tools.py      # 混合搜索（semantic + BM25 + RRF + Rerank）
│       ├── vector_store.py      # Milvus 向量存储
│       ├── bm25_index.py        # BM25 倒排索引
│       ├── chunker.py           # 文档分块器
│       ├── embeddings.py        # Embedding 模型
│       ├── reranker.py          # Cross-Encoder 重排
│       ├── query_rewriter.py    # Query 改写 Pipeline
│       ├── crud_tools.py        # 知识条目 CRUD
│       ├── sync_manager.py      # 四端同步管理器
│       └── env_monitor.py       # 文件变化监控
│
├── wiki/                        # 知识管理层
│   ├── service.py               # Markdown CRUD 服务
│   ├── git_service.py           # Git 版本管理
│   └── schemas.py               # Pydantic 数据模型
│
├── session/                     # 会话管理层
│   └── store.py                 # SQLite + Redis 缓存
│
├── routers/                     # API 路由层
│   ├── chat.py                  # 对话 API（流式 / 非流式 / HITL）
│   ├── wiki.py                  # Wiki CRUD API
│   ├── debug.py                 # 调试 API
│   └── vector_admin.py          # 向量管理 API
│
├── frontend/                    # 独立前端（Vue 3 + Vite）
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│
├── seed/                        # 种子知识库
├── static/                      # 静态资源
├── .env.example                 # 环境变量模板
└── README.md
```

---

## 架构概览

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│  FastAPI      │────▶│  LangGraph   │
│  Vue 3 SPA  │ SSE │  Routers     │     │  编排引擎     │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                │
                    ┌───────────────────────────┼────────────────────┐
                    │                           │                    │
              ┌─────▼─────┐            ┌────────▼────────┐   ┌──────▼──────┐
              │  检索层     │            │  决策层          │   │  执行层      │
              │            │            │                 │   │             │
              │ Query      │            │ knowledge_      │   │ sync_       │
              │ Rewrite    │            │ agent           │   │ manager     │
              │ + 混合检索  │            │ (create/update/ │   │ (Markdown+  │
              │ + 四路记忆  │            │  delete/none)   │   │  Milvus+    │
              └────────────┘            └─────────────────┘   │  BM25+Git)  │
                                                              └─────────────┘
```

详细架构文档见 `docs/wiki-agent-memory-architecture.md`。

---

## API 接口

### 对话 API (`/api/chat`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/stream` | SSE 流式对话 |
| POST | `/message` | 非流式对话 |
| POST | `/confirm` | HITL 确认/取消 |
| POST | `/save-knowledge` | 手动保存知识 |
| POST/GET | `/sessions` | 会话管理 |

### Wiki API (`/api/wiki`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/tree` | 目录树 |
| GET | `/search?q=` | 搜索 |
| CRUD | `/page/{path}` | 条目增删改查 |
| GET | `/graph` | 知识图谱 |
| GET | `/tags` | 标签列表 |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek 模型名 |
| `ZHIPUAI_API_KEY` | — | 智谱 API Key（可选，优先） |
| `ZHIPUAI_CHAT_MODEL` | `glm-4-flash` | 智谱模型名 |
| `HISTORY_MAX_TURNS` | `10` | 对话历史窗口轮数 |
| `QUERY_REWRITE_ENABLED` | `true` | 启用 Query 改写 |
| `RERANK_ENABLED` | `true` | 启用 Cross-Encoder 重排 |
| `GIT_ENABLED` | `true` | 启用 Git 版本管理 |

完整配置见 `.env.example`。

---

## License

本项目采用 [MIT License](LICENSE) 开源协议。
