# Changelog

本文件记录 Wiki Agent 的重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased]

### Added
- 独立前端项目 (`frontend/`)，与评估平台解耦
- 独立配置文件支持 (`.env` 优先级：本地 > 项目根目录)
- 六层对话历史压缩策略
- `get_recent_messages()` 高效部分加载
- Knowledge Decision `model_validator` 硬校验 + 重试机制
- 四路记忆架构文档 (`docs/wiki-agent-memory-architecture.md`)

### Changed
- `_build_history` 支持 `max_turns` 滑动窗口截断
- `_build_llm_messages` 二次截断保护 + SystemMessage 提示
- `decide_action` 使用四层上下文检索替代单一 hybrid_search
- 知识库 CRUD 决策器接入 `retrieve_context` 全量上下文

### Fixed
- 对话历史全量传入 LLM 导致 token 溢出

## [0.1.0] - 2025-07-01

### Added
- LangGraph 编排 (search → respond → decide → execute)
- 四端同步管理器 (Markdown + Milvus + BM25 + Git)
- 四路记忆检索 (User Memory / Session Memory / External KB / Working Memory)
- Query Rewrite Pipeline (Contextualizer / Classifier / Multi-Query / HyDE / Decompose)
- 混合检索 (Semantic + BM25 + RRF + Cross-Encoder Rerank)
- Human-in-the-Loop 知识沉淀
- 知识图谱可视化
- SSE 流式对话
- 运行时评估 SDK 集成
