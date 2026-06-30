# Q114: Wiki Agent 的完整请求链路：用户提问 → 检索 → 生成 → 可选知识提取，请逐步说明。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q114 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★★ |

## 问题

Wiki Agent 的完整请求链路：用户提问 → 检索 → 生成 → 可选知识提取，请逐步说明。

## 参考答案

Wiki Agent 采用 LangGraph 状态图编排，整条链路包含 Search、Respond、Decide、Execute 四个节点，每一步的中间状态均写入 `EvaluationTrace` 供自动评估消费。

**第一步：接收用户提问。** 前端通过 SSE 连接 Wiki 聊天端点，后端将用户消息注入 LangGraph state 的 `messages` 列表，随后触发 Search 节点。

**第二步：混合检索（Search 节点）。** `hybrid_search` 函数（`search_tools.py:107-128`）并行发起两路查询：语义检索走 Milvus 向量库，关键词检索走 BM25 倒排索引。两路结果通过 `_rrf_merge`（`search_tools.py:75-104`）做 Reciprocal Rank Fusion 融合排序，公式为 `score(d) = sum(1/(k + rank_i(d)))`，默认 k=60。随后调用 `rerank_results`（`reranker.py:129-157`）使用 BGE cross-encoder 重排，取 Top-K 文档片段作为上下文。

**第三步：生成回答（Respond 节点）。** 将检索到的文档片段注入系统提示词，与用户消息一起发送给 LLM。LLM 生成带有引用来源的回答，通过 SSE 流式推送至前端。

**第四步：判断是否提取知识（Decide 节点）。** LLM 自行评估回答中是否包含 Wiki 中尚不存在的新知识点。如果需要提取，生成 Human-in-the-Loop 确认请求，等待用户同意；如果不需要，直接路由到 END 状态结束链路。

**第五步：执行知识提取（Execute 节点）。** 用户确认后，Agent 从回答中结构化提取知识，写入 Wiki 页面存储，并触发向量索引增量更新，确保后续检索能命中新知识。

整条链路中，`EvaluationTrace` 在每个节点完成后记录输入、输出和耗时，平台可在链路结束后自动调用评估器打分，形成闭环质量监控。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py:107-128` — `hybrid_search` 并行语义+关键词检索
- `app/wiki_agent/agent/tools/search_tools.py:75-104` — `_rrf_merge` Reciprocal Rank Fusion 融合
- `app/wiki_agent/agent/tools/reranker.py:129-157` — `rerank_results` BGE cross-encoder 重排
- `app/wiki_agent/` — LangGraph 图定义，包含 search、respond、decide、execute 四个节点

## 回答要点

- 链路四步：Search（混合检索+RRF融合+重排）→ Respond（上下文增强生成）→ Decide（新知识判断+HITL）→ Execute（知识提取+向量重索引）
- 混合检索是核心：语义（Milvus）+ 关键词（BM25）→ RRF（k=60）→ cross-encoder rerank，四层漏斗保证精度
- Decide 节点引入 Human-in-the-Loop，避免自动写入错误知识
- EvaluationTrace 在每步记录中间状态，支持链路级别的自动评估
- 与六维 LLM-as-Judge 评估链路衔接：轨迹写入后由 evaluation_graph 消费打分

## 常见追问

**Q: RRF 融合的公式是什么？为什么不用加权平均？**

A: RRF 公式为 `score(d) = sum(1/(k + rank_i(d)))`，默认 k=60。RRF 不需要归一化分数，对不同检索器的分数尺度不敏感，比加权平均更鲁棒。

**Q: 如果 Decide 节点判断不需要提取新知识，链路怎么结束？**

A: Decide 节点直接输出 finish，LangGraph 路由到 END 状态，跳过 Execute 节点，链路正常结束。

**Q: 检索和重排各用什么模型？**

A: 语义检索使用 Milvus 存储的 embedding 向量（由 text-embedding 模型生成），重排使用 BGE cross-encoder（`reranker.py:129-157`），属于 BAAI 的开源重排模型。

## 相关题目

- [Q113](../answers/Q113-RAG-ground-truth.md)
- [Q115](../answers/Q115-Chat-SSE.md)
