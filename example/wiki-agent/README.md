# Wiki Agent — 模型与参考说明

> **注意：** 早期独立版 Wiki Agent（ChromaDB + 独立前后端）已移除。  
> 生产集成请使用根目录 **`app/wiki_agent/`**（Milvus + 统一 FastAPI 后端 + `frontend/src/wiki/` UI）。

## 本目录保留内容

| 路径 | 用途 |
|------|------|
| `models/` | Embedding / Rerank 模型权重目录（由 `download_reranker.py` 下载） |

## 快速开始

在项目根目录执行：

```bash
# Mock 模式（无需 Docker）
SANDBOX_MOCK_MODE=true python -m app.main

# 前端
cd frontend && npm run dev
```

访问 http://localhost:3000/wiki-agent 使用 Wiki Agent，http://localhost:8000/docs 查看 API。

详细说明见 [快速开始指南](../../docs/getting_started.md) 与 [架构文档](../../docs/architecture.md)。
