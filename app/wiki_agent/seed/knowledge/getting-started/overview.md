---
title: 平台概览
tags:
  - getting-started
  - platform
source: seed
---

# Agent Runtime Evaluation Platform

本平台用于评估 AI Agent 在真实任务运行时的行为质量，覆盖六个维度：

- **Planning** — 计划是否合理、完整
- **Tactical** — 下一步决策是否恰当
- **Tool Use** — 工具选择与参数是否正确
- **Memory** — 上下文记忆是否一致
- **Replan** — 失败后的重规划能力
- **Retrieval** — RAG 检索质量与幻觉检测

## 快速体验

1. 启动后端：`python -m app.main`
2. 启动前端：`cd frontend && npm run dev`
3. 打开 Wiki Agent，搜索「评估维度」或「Milvus」

## 数据流

任务创建 → 轨迹上报 → 六维并行评估 → 聚合得分 → 报告与对比分析。
