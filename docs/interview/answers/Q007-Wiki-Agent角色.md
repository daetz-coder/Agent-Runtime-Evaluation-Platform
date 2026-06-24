# Q7: Wiki Agent 在本项目中的角色是什么？是核心产品还是 Demo？为什么要把 RAG Agent 和评估平台放在同一个仓库？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q007 |
| 分类 | 项目理解与动机 |
| 难度 | ★ |

## 问题

Wiki Agent 在本项目中的角色是什么？是核心产品还是 Demo？为什么要把 RAG Agent 和评估平台放在同一个仓库？

## 参考答案

Wiki Agent 是同仓库的 RAG Demo 与评估样例：graph.py 中 search→respond→decide→execute，hybrid_search（Milvus+BGE+BM25+RRF）检索知识库，EvaluationTrace 显式 record_retrieval。EVAL_AUTO_RUN 在对话结束后自动 POST 评估。与评估平台放同一仓库是为零拷贝集成：trajectory schema、ActionType、RetrievalEvaluator 字段与 search 节点输出对齐，新工程师可跑通「提问→检索→回答→六维报告」全链路。它是 Demo 也是集成测试夹具。

> Wiki Agent 不是核心产品，核心产品是 Agent Runtime Evaluation Platform。Wiki Agent 的定位更像一个 Reference Implementation，它同时承担 Demo、Benchmark 和 Integration Test 的角色。一方面它通过 search→respond→decide→execute 的完整 RAG Agent 流程，为平台提供真实的 Trajectory 数据；另一方面它的 EvaluationTrace 与平台的 ActionType 和 Trajectory Schema 完全对齐，因此可以直接触发 RetrievalEvaluator、ToolUseEvaluator 等六维评估器，实现从提问、检索、回答到生成评估报告的完整闭环。之所以放在同一个仓库，是为了避免 Trajectory Schema 漂移、降低集成成本，并提供一个可重复运行的标准测试对象。因此评估平台是核心产品，而 Wiki Agent 更像是官方 Demo 和集成测试夹具（Test Fixture）。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/wiki_agent/evaluation.py`
- `app/main.py`

## 回答要点

- Demo + 集成测试 + RAG 评估样例
- EvaluationTrace 与 sdk 格式对齐
- EVAL_AUTO_RUN 自动触发评估
- 同仓避免 schema 漂移

## 常见追问

**Q: 能拆成两个 repo 吗？**

A: 可以，但 ActionType 与 API 版本需严格同步。

**Q: 是核心产品吗？**

A: 评估平台是核心，Wiki 是 reference implementation。

## 相关题目

- [Q006](../answers/Q006-单调性基准解释.md)
- [Q008](../answers/Q008-为何选LangGraph.md)
