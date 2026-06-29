# 端口配置说明

> **入口**: [README.md](../README.md) · **快速开始**: [getting_started.md](getting_started.md)

---

## 整合后（推荐）

整合后只需启动 **2 个进程**（或运行根目录 `start.bat` 一键启动）：

| 服务 | 端口 | 说明 |
|------|------|------|
| 统一后端 | 8000 | 评估平台 API + Wiki Agent API |
| 统一前端 | 3000 | 评估平台 UI + Wiki Agent 页面 |

## 常用地址

| 服务 | 地址 |
|------|------|
| 评估平台前端 | http://localhost:3000 |
| 评估平台仪表板 | http://localhost:3000/dashboard |
| Wiki Agent | http://localhost:3000/wiki-agent |
| 统一后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| Wiki API | http://localhost:8000/api/wiki |
| Chat API | http://localhost:8000/api/chat |
| 向量管理 | http://localhost:3000/vector-admin |
| 健康检查 | http://localhost:8000/health |

## 一键启动

```bat
start.bat
```

会打开两个窗口：后端（8000）和前端（3000）。

## 手动启动

```bat
REM 1. 启动统一后端
python -m app.main

REM 2. 启动统一前端
cd frontend
npm run dev
```

## 可配置项

根目录 `.env` 同时配置评估平台与 Wiki Agent：

```env
HOST="0.0.0.0"
PORT=8000
DEEPSEEK_API_KEY="sk-..."
DEEPSEEK_MODEL="deepseek-chat"
EVAL_API_BASE_URL="http://127.0.0.1:8000"
```

## 数据目录

| 路径 | 说明 |
|------|------|
| `example/wiki-agent/knowledge/` | Wiki 知识库 Markdown |
| `example/wiki-agent/milvus.db` | Milvus 向量索引（Milvus Lite 本地模式） |
| `example/wiki-agent/models/` | 本地 Embedding 模型 |
| `data/wiki_agent/` | Wiki 会话、BM25 索引、Checkpoint |
| `agent_eval.db` | SQLite 数据库（开发模式） |

## 旧版独立启动（已弃用）

`example/wiki-agent/start.bat` 仍可单独启动示例，但推荐使用根目录整合后的 `start.bat`。
