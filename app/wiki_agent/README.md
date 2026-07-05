# Wiki Agent

基于 RAG（检索增强生成）的个人知识库问答系统，支持自动知识沉淀、四路记忆、四端同步。

独立运行项目，不依赖外部评估平台。可通过 Hook 接口低侵入接入评估系统。

---

## 核心能力

- **智能问答**：LangGraph 编排，四路记忆检索，流式对话
- **知识沉淀**：对话中自动识别有价值的知识，Human-in-the-Loop 确认后写入
- **四端同步**：Markdown + Milvus + BM25 + Git 最终一致性
- **四路记忆**：KB 检索 + User Memory + Session Memory + 对话历史

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 下载模型

需要下载两个 ML 模型到 `models/` 目录：

| 模型 | 用途 | 大小 | 下载地址 |
|------|------|------|----------|
| `bge-small-zh-v1.5` | Embedding 向量化 | ~90MB | [ModelScope](https://modelscope.cn/models/BAAI/bge-small-zh-v1.5) / [HuggingFace](https://huggingface.co/BAAI/bge-small-zh-v1.5) |
| `bge-reranker-base` | Cross-Encoder 重排 | ~1.1GB | [ModelScope](https://modelscope.cn/models/BAAI/bge-reranker-base) / [HuggingFace](https://huggingface.co/BAAI/bge-reranker-base) |

**方式 A：自动下载（推荐）**

```bash
python -m app.wiki_agent.tools.download_models
```

**方式 B：手动下载**

```bash
# 从 ModelScope 下载（国内推荐）
pip install modelscope
python -c "from modelscope import snapshot_download; snapshot_download('BAAI/bge-small-zh-v1.5', local_dir='app/wiki_agent/models/bge-small-zh-v1.5')"
python -c "from modelscope import snapshot_download; snapshot_download('BAAI/bge-reranker-base', local_dir='app/wiki_agent/models/bge-reranker-base')"

# 或从 HuggingFace 下载
# pip install huggingface_hub
# huggingface-cli download BAAI/bge-small-zh-v1.5 --local-dir app/wiki_agent/models/bge-small-zh-v1.5
# huggingface-cli download BAAI/bge-reranker-base --local-dir app/wiki_agent/models/bge-reranker-base
```

下载完成后目录结构：

```
app/wiki_agent/models/
├── bge-small-zh-v1.5/
│   ├── model.safetensors
│   ├── config.json
│   ├── tokenizer.json
│   └── ...
└── bge-reranker-base/
    ├── pytorch_model.bin (或 model.safetensors)
    ├── config.json
    └── ...
```

> 如果本地模型不存在，程序会自动从 HuggingFace Hub 在线下载（需要网络）。

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 或 ZHIPUAI_API_KEY
```

### 4. 启动

```bash
# 独立启动
python -m app.wiki_agent --port 8000

# 开发模式（热重载）
python -m app.wiki_agent --reload --port 8000
```

### 5. 启动前端（可选）

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
├── hooks.py                     # 生命周期钩子接口（评估平台接入点）
├── cache.py                     # Redis 缓存层（可选）
│
├── agent/                       # 智能体层
│   ├── graph.py                 # LangGraph 编排（search → respond → decide → execute）
│   ├── llm_factory.py           # 统一 LLM 创建工厂
│   ├── knowledge_agent.py       # 知识库 CRUD 决策器
│   ├── context_retriever.py     # 四路记忆检索 + 预算裁剪
│   ├── auto_tagger.py           # LLM 自动标签
│   └── tools/                   # 工具集
│       ├── search_tools.py      # 混合搜索（semantic + BM25 + RRF + Rerank）
│       ├── vector_store.py      # Milvus 向量存储
│       ├── bm25_index.py        # BM25 倒排索引
│       ├── chunker.py           # 文档分块器
│       ├── embeddings.py        # Embedding 模型加载
│       ├── reranker.py          # Cross-Encoder 重排
│       ├── query_rewriter.py    # Query 改写 Pipeline
│       ├── crud_tools.py        # 知识条目 CRUD
│       ├── sync_manager.py      # 四端同步管理器
│       ├── env_monitor.py       # 文件变化监控
│       └── download_models.py   # 模型下载脚本
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
├── models/                      # ML 模型权重（需下载，不入 git）
│   ├── bge-small-zh-v1.5/       # Embedding 模型
│   └── bge-reranker-base/       # Reranker 模型
├── data/                        # 运行时数据（自动生成，不入 git）
├── seed/                        # 种子知识库
├── static/                      # 静态资源
├── requirements.txt             # Python 依赖
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

### 健康检查

```
GET /health
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek 模型名 |
| `ZHIPUAI_API_KEY` | — | 智谱 API Key（可选，优先使用） |
| `ZHIPUAI_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | 智谱 API 地址 |
| `ZHIPUAI_CHAT_MODEL` | `glm-4-flash` | 智谱模型名 |
| `HISTORY_MAX_TURNS` | `10` | 对话历史窗口轮数 |
| `QUERY_REWRITE_ENABLED` | `true` | 启用 Query 改写 |
| `RERANK_ENABLED` | `true` | 启用 Cross-Encoder 重排 |
| `GIT_ENABLED` | `true` | 启用 Git 版本管理 |
| `REDIS_URL` | — | Redis 地址（可选，不配则不用缓存） |

完整配置见 `.env.example`。

---

## 评估平台集成

wiki-agent 通过 `hooks.py` 委托给 SDK `TrajectoryCollector` 实现评估数据采集。

### 采集事件

| 事件 | 触发时机 | SDK 方法 |
|------|----------|----------|
| `emit_session_start` | 对话开始 | `collector.start_async()` |
| `emit_retrieval` | 检索完成 | `collector.record_retrieval()` |
| `emit_key_facts` | 提取关键事实 | `collector.record_memory_write()` |
| `emit_response` | 回复生成完成 | `collector.record(EVIDENCE, ...)` |
| `emit_session_end` | 对话结束 | `collector.finish_async()` |

### 运行模式

- **评估平台运行中**：SDK 自动推送轨迹数据到平台（HTTP 或进程内直写）
- **评估平台未运行**：SDK 自动缓冲到本地，不阻塞 Agent 运行
- **EVAL_ENABLED=false**：所有操作静默跳过，零开销

---

## License

本项目采用 [MIT License](LICENSE) 开源协议。
