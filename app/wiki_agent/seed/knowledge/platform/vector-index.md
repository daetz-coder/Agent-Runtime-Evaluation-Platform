---
title: Wiki 向量索引
tags:
  - wiki
  - milvus
  - rag
source: seed
---

# Wiki 向量索引（Milvus）

Wiki Agent 使用 **Milvus** 存储 Markdown 分块后的语义向量，配合 **BM25** 做关键词检索，并通过 **RRF** 融合为混合搜索。

## 四路同步

每次增删改 Wiki 页面时，系统会同步：

1. Markdown 原文（`data/wiki_agent/knowledge/`）
2. Milvus 向量索引
3. BM25 倒排索引
4. Git 版本记录

## 管理入口

- 前端：**向量管理** 页面（`/vector-admin`）
- API：`GET /api/wiki/vector-stats`
- 重建：`POST /api/wiki/vector-rebuild`

## Embedding 模型

默认使用 HuggingFace 模型 `BAAI/bge-small-zh-v1.5`（512 维）。若本地存在 `example/wiki-agent/models/bge-small-zh-v1.5`，将优先使用本地权重。
