# Agent 开发工程师 — 项目面试问题集

> 基于「Agent Runtime Evaluation Platform + Wiki Agent」项目，面向 Agent 开发工程师岗位的面试问题整理。

---

## 目录

1. [项目整体架构](#1-项目整体架构)
2. [Agent 核心设计（LangGraph）](#2-agent-核心设计langgraph)
3. [RAG 与知识检索](#3-rag-与知识检索)
4. [Embedding 与向量数据库](#4-embedding-与向量数据库)
5. [BM25 与混合搜索](#5-bm25-与混合搜索)
6. [LLM 集成与多模型支持](#6-llm-集成与多模型支持)
7. [评估系统设计](#7-评估系统设计)
8. [Human-in-the-Loop（HITL）](#8-human-in-the-loophitl)
9. [数据一致性与同步](#9-数据一致性与同步)
10. [流式输出与实时通信](#10-流式输出与实时通信)
11. [SDK 设计与可观测性](#11-sdk-设计与可观测性)
12. [工程实践与系统设计](#12-工程实践与系统设计)
13. [安全与权限](#13-安全与权限)
14. [性能与优化](#14-性能与优化)
15. [开放性与深度追问](#15-开放性与深度追问)

---

## 1. 项目整体架构

### Q1.1 请介绍一下你做的这个项目，整体架构是怎样的？
**考察点：** 全局视野、表达能力、是否能清晰描述系统边界

### Q1.2 你们项目为什么分成"评估平台"和"Wiki Agent"两个子系统？它们的职责边界是什么？
**考察点：** 模块划分的设计思维

### Q1.3 评估平台和 Wiki Agent 之间是怎么交互的？数据怎么流转的？
**考察点：** 理解 EvaluationTrace → HTTP 上传 → 评估流水线的链路

### Q1.4 你们的技术选型是怎么做的？为什么用 FastAPI + LangGraph + Milvus 这套组合？有没有考虑过其他方案？
**考察点：** 技术选型的决策过程

### Q1.5 项目的前后端是怎么分的？前端用了什么技术栈？你在前端做了哪些工作？
**考察点：** 全栈能力

---

## 2. Agent 核心设计（LangGraph）

### Q2.1 你们的 Agent 是基于 LangGraph 实现的，能画一下你们的 Graph 结构吗？有几个节点？几条边？
**考察点：** 对 `search → respond → decide → execute` 四节点流程的掌握程度

### Q2.2 为什么你们的 Agent 图是 4 个节点（search、respond、decide、execute）而不是一个节点搞定所有事？这样拆分的好处是什么？
**考察点：** 理解关注点分离、可测试性、可观测性

### Q2.3 `decide` 节点判断是否需要执行知识 CRUD 操作，它的决策逻辑是怎样的？用了什么 prompt？
**考察点：** KnowledgeDecision 的 Pydantic 结构化输出 + PydanticOutputParser

### Q2.4 你们的 Agent State（WikiState）包含哪些字段？为什么这样设计？
**考察点：** TypedDict 状态设计：user_message, wiki_results, wiki_text, ai_response, decision, action_result, stage

### Q2.5 LangGraph 的 StateGraph 和传统的 if-else 流程控制有什么本质区别？用 StateGraph 的优势在哪？
**考察点：** 状态持久化、条件路由、可中断恢复、可观测性

### Q2.6 你们的条件边（conditional edges）是怎么设计的？什么情况下走 `decide`，什么情况下直接 END？
**考察点：** `respond` 后判断 response > 50 chars → decide，否则 END；`decide` 后判断 action != "none" → execute

### Q2.7 LangGraph 的 Checkpointer（AsyncSqliteSaver）在你们项目中起什么作用？如果去掉 Checkpointer 会怎样？
**考察点：** 状态持久化对 HITL 的重要性——没有 Checkpointer 就无法在中断后恢复

### Q2.8 你们的 Agent 支持流式和非流式两种模式，它们的实现有什么区别？
**考察点：** `run_chat_stream()`（asyncio.Queue + SSE）vs `run_chat_invoke()`（同步 invoke）

### Q2.9 如果让你重新设计这个 Agent 的 Graph，你会怎么改？有哪些你觉得目前设计不合理的地方？
**考察点：** 反思能力、架构演进思维

### Q2.10 LangGraph 的 `Command(resume=...)` 是怎么工作的？为什么用它来实现 Human-in-the-Loop？
**考察点：** 理解 interrupt + resume 的中断恢复机制

### Q2.11 你们 Agent 的 `search` 节点执行检索时，如果检索结果为空怎么办？有没有做 fallback？
**考察点：** 鲁棒性设计——semantic_search 失败时 fallback 到 keyword_search

### Q2.12 如果 Agent 在执行过程中某个节点抛异常了，你们是怎么处理的？有没有重试或降级机制？
**考察点：** 错误处理策略

### Q2.13 你们的 Agent 有没有做"多轮对话"？对话历史是怎么管理的？
**考察点：** chat history 的存取、上下文窗口管理、token 限制处理

> 在 LangGraph 架构中，session_id 通常表示用户的一段连续使用范围，thread_id 表示其中某一条具体对话线程，而 checkpointer 实际以 thread_id 为粒度保存和恢复 Graph State。多轮对话发生在同一个 thread 内，依赖 state 累积实现上下文连续；而新 thread 则代表全新的 state 初始化，因此上下文完全隔离，不共享 messages、tool results 或 retrieval history。

### Q2.14 你们的 Agent 有没有"规划（Planning）"能力？如果没有，你会怎么加？
**考察点：** 对 ReAct、Plan-and-Execute 等 Agent 范式的理解

### Q2.15 LangGraph 中的 `interrupt()` 和 Python 的 `breakpoint()` 有什么区别？为什么不能用 breakpoint 代替 interrupt？
**考察点：** 理解 interrupt 是框架级的状态挂起，不是调试断点

---

## 3. RAG 与知识检索

### Q3.1 什么是 RAG？你们项目是怎么实现 RAG 的？
**考察点：** Retrieval-Augmented Generation 的基本概念 + 项目中的具体实现链路

### Q3.2 RAG 的核心挑战有哪些？你们在项目中遇到了哪些？是怎么解决的？
**考察点：** chunk 质量、检索精度、上下文窗口限制、hallucination 检测

### Q3.3 你们的知识文档是怎么切块（chunking）的？chunk_size 和 chunk_overlap 是怎么定的？
**考察点：** `chunk_markdown(content, chunk_size=500, chunk_overlap=50)` + RecursiveCharacterTextSplitter

### Q3.4 为什么 chunk_size 选 500？overlap 选 50？有没有做过实验对比不同参数的效果？
**考察点：** 参数调优的经验、是否有量化评估

### Q3.5 你们切块的时候是怎么处理 Markdown 结构的？标题层级、代码块、表格有没有特殊处理？
**考察点：** 对文档结构感知的 chunking 策略

### Q3.6 除了 Markdown，你们还支持哪些文档格式的导入？怎么处理的？
**考察点：** chunker.py 中的 PDF（PyPDF2）、Word（python-docx）支持

### Q3.7 你们检索出来的知识片段是怎么注入到 LLM 的 prompt 中的？用的什么 prompt 模板？
**考察点：** system prompt 中拼接 wiki_text 上下文的方式

### Q3.8 如果检索出来的内容和用户问题不相关怎么办？有没有做相关性过滤或 rerank？
**考察点：** 检索质量控制——目前通过 hybrid_search + 多返回再过滤

### Q3.9 你们的 RAG 系统有没有做 query rewriting 或 query expansion？
**考察点：** 对高级 RAG 技术的了解

### Q3.10 你们的 `semantic_search` 返回结果时做了去重（按 path 去重取最高分），为什么需要去重？
**考察点：** 同一个页面被切成多个 chunk，可能多个 chunk 都命中，但只取最相关的一个

### Q3.11 RAG 中常见的"hallucination"问题，你们是怎么检测和缓解的？
**考察点：** RetrievalEvaluator 中的 hallucination_detected 字段

### Q3.12 你们有没有评估过 RAG 的检索质量？怎么评估的？
**考察点：** tests/eval_retrieval.py 和 RetrievalEvaluator 的设计

---

## 4. Embedding 与向量数据库

### Q4.1 你们用的 Embedding 模型是什么？为什么选 `BAAI/bge-small-zh-v1.5`？有没有对比过其他模型？
**考察点：** 模型选型的理由——中文优化、512 维小模型、推理速度快

### Q4.2 bge-small-zh-v1.5 的 512 维是什么意思？维度越高越好吗？
**考察点：** 向量维度与表达能力、存储成本、搜索速度的 trade-off

### Q4.3 Embedding 模型是本地运行还是调 API？本地运行有什么优缺点？
**考察点：** sentence-transformers 本地加载 vs API 调用（延迟、成本、隐私）

### Q4.4 你们的 Embedding 模型是懒加载（lazy load）的，为什么要这样做？有什么好处？
**考察点：** `get_embedding_model()` 单例 + 延迟加载——避免启动时加载大模型拖慢服务

### Q4.5 如果 Embedding 模型加载失败，你们的 fallback 策略是什么？返回全零向量会有什么问题？
**考察点：** `return [0.0] * settings.EMBEDDING_DIM` — 全零向量在 COSINE 相似度下无意义，可能导致检索质量崩溃

### Q4.6 Embedding 的输入是什么？你们在文本前面拼了 title，为什么？
**考察点：** `f"{title}\n{chunk}"` — 加入标题信息增强语义表达

### Q4.7 Milvus Lite 和 Milvus Server 有什么区别？你们为什么选择 Lite 模式？
**考察点：** 嵌入式文件模式 vs 分布式服务模式——部署复杂度、数据量级

### Q4.8 Milvus 的 COSINE 相似度是怎么计算的？和 L2 距离、内积有什么区别？什么时候用哪个？
**考察点：** 向量相似度度量的数学基础

### Q4.9 Milvus 在创建 collection 时设置了 `id_type="string", max_length=512`，为什么 ID 用字符串而不是自增整数？
**考察点：** chunk_id 格式 `{path}#chunk{i}` 需要字符串，便于溯源和去重

### Q4.10 Milvus 中的向量索引类型有哪些？你们用的什么索引？Milvus Lite 默认用的是什么？
**考察点：** HNSW、IVF_FLAT、IVF_PQ 等索引类型的了解

### Q4.11 如果知识库有 100 万条 chunk，Milvus Lite 还能扛得住吗？什么时候应该切换到 Milvus Server？
**考察点：** 对扩展性的思考

### Q4.12 你们的 collection 中没有设置 `index_params`（如 HNSW 的 M 和 efConstruction），这对搜索性能有什么影响？
**考察点：** 对向量索引参数调优的理解

### Q4.13 除了 Milvus，你还了解哪些向量数据库？它们各自的特点是什么？
**考察点：** FAISS、ChromaDB、Pinecone、Weaviate、Qdrant 的对比

### Q4.14 Embedding 模型如果升级了（比如换成 bge-large），已有的向量数据怎么办？需要重建索引吗？
**考察点：** 维度变更时需要 drop_collection + 全量 reindex

---

## 5. BM25 与混合搜索

### Q5.1 BM25 是什么算法？它和 TF-IDF 有什么区别？
**考察点：** BM25Okapi 的原理——词频饱和度、文档长度归一化

### Q5.2 为什么你们同时用向量搜索和 BM25？它们各自的优劣势是什么？
**考察点：** 向量搜索擅长语义匹配，BM25 擅长精确关键词匹配，互补

### Q5.3 RRF（Reciprocal Rank Fusion）是怎么工作的？公式是什么？rrf_k=60 是怎么选的？
**考察点：** `score = Σ 1/(k + rank)` — k 控制排名衰减速度，60 是经验值

### Q5.4 为什么 RRF 用 rank 而不是 score 来融合？直接融合 score 不行吗？
**考察点：** 不同检索系统的 score 尺度不同（向量 COSINE 0~1 vs BM25 无上界），rank 更可比较

### Q5.5 你们 BM25 的分词用的是什么？为什么用 jieba？有没有考虑过其他中文分词方案？
**考察点：** jieba.lcut() + 停用词过滤 + 单字过滤

### Q5.6 BM25 索引是怎么持久化的？为什么用 pickle？有没有安全隐患？
**考察点：** `bm25_index.pkl` — pickle 的序列化/反序列化安全问题

### Q5.7 BM25 索引的 `_dirty` 标记是干什么的？这是一种什么设计模式？
**考察点：** 延迟重建（lazy rebuild）——只在搜索时才真正构建 BM25Okapi，避免频繁重建

### Q5.8 你们的 BM25 搜索做了按 path 去重（保留最高分的 chunk），这个逻辑和向量搜索的去重是一样的吗？
**考察点：** 两种检索都做了相同的去重策略，保证一致性

### Q5.9 hybrid_search 中，semantic_search 和 keyword_search 各取 `limit * 2` 条结果，为什么要多取？
**考察点：** 给 RRF 融合更多的候选集，增加召回率

### Q5.10 如果 BM25 索引和 Milvus 索引的数据不一致会怎样？你们怎么保证一致性？
**考察点：** sync_manager 的四路同步机制

### Q5.11 除了 RRF，还有哪些混合搜索的融合策略？它们各有什么优缺点？
**考察点：** 加权融合、学习排序（Learning to Rank）、cross-encoder rerank

---

## 6. LLM 集成与多模型支持

### Q6.1 你们项目支持哪些 LLM 提供商？它们分别用在什么场景？
**考察点：** DeepSeek（主 Agent + 评估）、OpenAI、Anthropic、ZhipuAI、Qwen（评估 + 共识）

### Q6.2 为什么主 Agent 用 DeepSeek 而不是 GPT-4 或 Claude？是基于什么考虑选的？
**考察点：** 成本、中文能力、延迟的 trade-off

### Q6.3 你们调用 LLM 用的是 LangChain 的 ChatOpenAI，DeepSeek 和 Qwen 的 API 兼容 OpenAI 格式吗？
**考察点：** OpenAI-compatible API 的行业标准

### Q6.4 你们在不同场景下用了不同的 temperature（0.1、0.3、0.7、0），为什么要这样设置？
**考察点：** auto-tagging 0.1（需要确定性）、knowledge-decision 0.3（稍灵活）、chat 0.7（需要创造性）、evaluation 0（需要一致性）

### Q6.5 LLM 返回的内容不符合预期格式怎么办？你们怎么做输出解析的？
**考察点：** PydanticOutputParser + KnowledgeDecision 结构化输出

### Q6.6 如果 LLM 返回的 JSON 格式不合法，PydanticOutputParser 会怎样？你们怎么处理这种异常？
**考察点：** 解析失败的容错处理

### Q6.7 你们有没有遇到 LLM 的 token 限制问题？怎么处理的？
**考察点：** 上下文窗口管理——chat history 截断、wiki_text 长度控制

### Q6.8 LLM 调用的延迟你们有监控吗？一次完整的 Agent 调用大概需要多长时间？
**考察点：** 端到端延迟的构成（embedding + 检索 + LLM 生成 + 决策）

### Q6.9 如果某个 LLM 提供商的 API 挂了，你们有 fallback 机制吗？
**考察点：** 多提供商容灾

### Q6.10 你们有没有做过 prompt engineering？prompt 是怎么迭代的？有版本管理吗？
**考察点：** prompt 设计的方法论

---

## 7. 评估系统设计

### Q7.1 你们的 Agent 评估系统评估了哪些维度？为什么是这 6 个维度？
**考察点：** Planning、Tactical、Tool Use、Memory、Replan、Retrieval 的设计思路

### Q7.2 每个评估维度的子指标是怎么定的？权重是怎么分配的？
**考察点：** 例如 Planning 的 coverage(0.30) + ordering(0.20) + granularity(0.20) + completeness(0.30)

### Q7.3 你们的评估用的是"LLM-as-Judge"模式，这个模式有什么优缺点？
**考察点：** LLM 评估的一致性、偏见、成本问题

### Q7.4 你们怎么保证 LLM 评估的结果是可靠的、可重复的？
**考察点：** temperature=0、多次评估取均值、consensus 机制

### Q7.5 ConsensusEvaluator 是怎么工作的？为什么需要多模型共识？
**考察点：** 多 LLM 提供商独立评估 → 取均值 + 标准差，减少单一模型的偏见

### Q7.6 你们的评估是串行执行还是并行执行的？性能差多少？
**考察点：** LangGraph StateGraph 顺序执行（~71s）vs asyncio.gather 并行（~15s），5 倍加速

### Q7.7 评估的 Trajectory（轨迹）数据包含哪些信息？14 种 action type 分别代表什么？
**考察点：** plan, tool_call, tool_result, memory_write, memory_read, think, replan 等

### Q7.8 如果一个 Agent 的 Planning 分数很高但 Tool Use 分数很低，说明什么问题？
**考察点：** 对评估结果的解读能力

### Q7.9 你们的评估系统有没有做"自评"？也就是评估评估系统本身是否准确？
**考察点：** tests/eval_evaluator_accuracy.py — 评估器的准确性验证

### Q7.10 "评估"和"测试"有什么区别？你们项目中既有评估又有测试，它们的定位分别是什么？
**考察点：** 测试 = 确定性的 pass/fail；评估 = LLM-based 的质量打分

### Q7.11 你们评估系统中的 RetrievalEvaluator 检测 hallucination 是怎么实现的？
**考察点：** hallucination_detected 字段的检测逻辑

### Q7.12 如果让你设计一个新的评估维度，你会加什么？为什么？
**考察点：** 创新能力——例如安全性、用户体验、成本效率

---

## 8. Human-in-the-Loop（HITL）

### Q8.1 为什么你们的 Agent 在执行知识 CRUD 操作之前需要人类确认？
**考察点：** 防止 Agent 自主修改知识库导致数据损坏

### Q8.2 Human-in-the-Loop 的实现机制是什么？LangGraph 的 `interrupt()` 和 `Command(resume=...)` 是怎么配合的？
**考察点：** 中断 → 挂起状态 → 等待用户 → resume 恢复

### Q8.3 HITL 中断后，Agent 的状态存在哪里？如果用户一直不确认，状态会一直保留吗？
**考察点：** AsyncSqliteSaver 持久化 checkpointer

### Q8.4 用户确认（confirm）和取消（cancel）分别会触发什么行为？
**考察点：** resume=True 执行 CRUD vs resume=False 跳过

### Q8.5 HITL 对用户体验有什么影响？有没有做到"无感"的 HITL？
**考察点：** SSE 流式推送确认请求 → 前端弹窗 → 用户点击 → 继续流式输出

### Q8.6 在什么场景下 HITL 是必要的？什么场景下可以省略？
**考察点：** 写操作需要确认，读操作可以自动执行

### Q8.7 如果把你的 HITL 去掉，让 Agent 完全自主操作知识库，会有什么风险？怎么缓解？
**考察点：** 沙箱、dry-run、自动回滚、审批阈值

---

## 9. 数据一致性与同步

### Q9.1 你们的"四路同步"（Markdown + Milvus + BM25 + Git）是怎么实现的？
**考察点：** WikiSyncManager 的 create/update/delete 流程

### Q9.2 四路同步中如果某一步失败了怎么办？比如 Milvus 写入成功但 BM25 更新失败了，会怎样？
**考察点：** 部分失败的一致性问题和恢复策略

### Q9.3 你们有没有考虑过事务（transaction）机制？把四路操作包在一个事务里？
**考察点：** 分布式事务的复杂性——Markdown 是文件系统，Milvus 是数据库，Git 是版本控制，无法用传统事务

### Q9.4 `reindex_all()` 是什么时候需要调用的？它做了什么？
**考察点：** 全量重建——扫描所有 MD 文件 → 重建 Milvus + BM25 索引

### Q9.5 Git 在你们系统中扮演什么角色？为什么要用 Git 来管理知识库？
**考察点：** 版本控制 + 回滚能力（git_service.py 的 rollback）

### Q9.6 如果用户在 Git 仓库外部直接修改了 Markdown 文件，你们能检测到吗？怎么处理？
**考察点：** 文件系统变更检测 + reindex 机制

### Q9.7 你们的知识库支持多人协作吗？如果两个人同时修改同一个页面会怎样？
**考察点：** Git 的冲突处理 + 文件锁

### Q9.8 sync_manager 用了单例模式（singleton），为什么？如果创建多个实例会有什么问题？
**考察点：** 全局状态共享——embedding_model 缓存、BM25 索引缓存

---

## 10. 流式输出与实时通信

### Q10.1 你们的 SSE（Server-Sent Events）流式输出是怎么实现的？
**考察点：** sse-starlette + asyncio.Queue

### Q10.2 SSE 和 WebSocket 有什么区别？为什么你们选了 SSE 而不是 WebSocket？
**考察点：** SSE 单向、轻量、HTTP 兼容；WebSocket 双向、更重

### Q10.3 流式输出时，如果网络中断了怎么办？客户端怎么恢复？
**考察点：** SSE 的 Last-Event-ID 重连机制

### Q10.4 流式 chat 的 LLM 输出是怎么和 SSE 对接的？LangChain 的 streaming 是怎么用的？
**考察点：** ChatOpenAI 的 stream() 方法 + 逐 token 推入 Queue

### Q10.5 在流式模式下，HITL 确认请求是怎么插入到流中的？
**考察点：** 中断时在 SSE 流中发送确认请求事件

---

## 11. SDK 设计与可观测性

### Q11.1 你们的 SDK 为什么要做到"零依赖（zero app dependencies）"？
**考察点：** SDK 作为独立包被外部项目集成，不引入 FastAPI/SQLAlchemy 等重依赖

### Q11.2 TrajectoryCollector 支持 14 种 action type，为什么要定义这么多类型？不能简化吗？
**考察点：** 细粒度追踪的价值——评估系统需要不同维度的数据

### Q11.3 SDK 的三种 Adapter（langgraph、llm_proxy、callback）分别用在什么场景？
**考察点：** langgraph adapter 自动包装 graph、llm_proxy 拦截 LLM 调用、callback 集成 LangChain 回调

### Q11.4 TrajectoryCollector 是线程安全的吗？怎么保证的？
**考察点：** 多线程环境下的数据竞争问题

### Q11.5 Collector 的"批量上传（batched uploads）"是怎么实现的？为什么要批量？
**考察点：** 减少 HTTP 请求次数，降低网络开销

### Q11.6 如果 Collector 连接的评估平台挂了，数据会丢失吗？有没有离线模式？
**考察点：** 离线缓存 + 重试机制

### Q11.7 你们用了 OpenTelemetry，追踪了哪些内容？和自定义的 EvaluationTrace 有什么区别？
**考察点：** OpenTelemetry 做基础设施级追踪（延迟、错误率）；EvaluationTrace 做业务级追踪（Agent 行为）

---

## 12. 工程实践与系统设计

### Q12.1 你们的数据库用了 SQLAlchemy + Alembic，为什么需要数据库迁移工具？
**考察点：** 版本化数据库 schema 变更

### Q12.2 评估任务为什么用后台任务（Background Task）执行而不是同步执行？
**考察点：** 评估耗时长（15s~71s），同步会阻塞 HTTP 连接

### Q12.3 你们的 chat session 用的是单独的 SQLite 数据库，为什么不和主库合并？
**考察点：** 关注点分离——chat 是 wiki_agent 子系统的私有数据

### Q12.4 项目的配置管理是怎么做的？环境变量、配置文件、默认值的优先级是怎样的？
**考察点：** pydantic-settings 的 Settings 类 + .env 文件 + 默认值三层优先级

### Q12.5 你们的项目有 Docker 化吗？docker-compose 里有哪些服务？
**考察点：** Dockerfile + docker-compose.yml 的编排

### Q12.6 你们的测试覆盖了哪些方面？有没有集成测试？
**考察点：** test_api（集成）、test_evaluation_service（单元）、test_vector_store（集成）、benchmark_evaluators（性能）

### Q12.7 你们的 CI/CD 是怎么做的？代码合并前有什么检查？
**考察点：** ruff linting、mypy type checking、pytest

### Q12.8 如果让你把这个项目从单机部署改成分布式部署，你会怎么设计？
**考察点：** 系统设计能力——服务拆分、消息队列、共享存储

### Q12.9 你们的知识库文件存在本地文件系统上，如果要支持水平扩展（多个后端实例），需要怎么改？
**考察点：** 共享文件系统（NFS/S3）、数据库存储文件

### Q12.10 项目中的单例模式用在了哪些地方？为什么用单例？有什么替代方案？
**考察点：** MilvusVectorStore、BM25Index、WikiSyncManager、embedding_model — 依赖注入作为替代

---

## 13. 安全与权限

### Q13.1 你们的 API 有认证机制吗？是怎么实现的？
**考察点：** auth_middleware.py 的 API Key 认证

### Q13.2 知识库页面的 path 参数有没有做路径遍历（path traversal）防护？
**考察点：** service.py 中验证 path 不能逃逸 KNOWLEDGE_DIR

### Q13.3 用户通过 CRUD API 能写入任意内容到知识库，有没有做内容审查或过滤？
**考察点：** 输入验证和安全

### Q13.4 LLM 的 prompt 有没有做 injection 防护？如果用户在消息中嵌入恶意指令怎么办？
**考察点：** Prompt Injection 防御

### Q13.5 Milvus 的 filter 表达式是直接拼接字符串的（`f'path == "{escaped}"'`），有没有注入风险？
**考察点：** 转义处理（replace `\` 和 `"`）的充分性

### Q13.6 pickle 持久化 BM25 索引有没有安全风险？有没有考虑过替代方案？
**考察点：** pickle 反序列化任意代码执行风险

---

## 14. 性能与优化

### Q14.1 一次完整的用户聊天请求（从输入到输出），端到端延迟大概多少？瓶颈在哪里？
**考察点：** 延迟拆解：embedding（~50ms）+ Milvus 搜索（~10ms）+ BM25 搜索（~5ms）+ LLM 生成（~2-5s）+ 决策（~1-2s）

### Q14.2 你们的评估系统并行执行（asyncio.gather）比串行快 5 倍，这个并行有没有什么限制或风险？
**考察点：** API rate limit、并发连接数、内存占用

### Q14.3 BM25 搜索的时间复杂度是多少？知识库增长到 10 万条 chunk 时，BM25 还能快吗？
**考察点：** BM25Okapi 的 `get_scores()` 是 O(n) 遍历所有文档

### Q14.4 Embedding 模型加载一次之后常驻内存，占多少内存？如果内存不够怎么办？
**考察点：** bge-small-zh-v1.5 约 100-200MB；可以考虑按需加载或使用 API

### Q14.5 Milvus Lite 的搜索性能和 Milvus Server 差多少？在什么量级下会有明显差异？
**考察点：** 数据量、并发量、索引类型的影响

### Q14.6 你们的 BM25 索引用了 pickle 持久化，加载速度怎么样？有没有更快的方案？
**考察点：** pickle 加载 vs SQLite vs Redis 缓存

### Q14.7 如果知识库有 1 万个页面，启动时的 `sync_indexes_if_needed()` 需要多长时间？怎么优化？
**考察点：** 全量 embedding + 写入 Milvus 的成本——可以增量同步

### Q14.8 你们的 Agent 用了 LLM 来做"decide"（判断是否需要 CRUD 操作），每次对话都要调一次额外的 LLM，成本和延迟怎么优化？
**考察点：** 可以合并 respond 和 decide 到一次 LLM 调用；或用小模型做 decide

---

## 15. 开放性与深度追问

### Q15.1 你觉得你们的 Wiki Agent 和市面上的 RAG 产品（如 Dify、FastGPT）相比，有什么优势和不足？
**考察点：** 行业视野、产品思维

### Q15.2 如果让你给这个 Agent 加一个"自我反思（self-reflection）"能力，你会怎么设计？
**考察点：** Agent 自主评估和改进的能力

### Q15.3 你们的 Agent 目前是单 Agent 架构，如果要改成 Multi-Agent，你会怎么设计？
**考察点：** 多 Agent 协作——检索 Agent、写作 Agent、审核 Agent 的分工

### Q15.4 你们的知识库是静态的 Markdown 文件，如果知识库的内容是实时变化的（比如爬取的网页），你们的系统需要怎么改？
**考察点：** 增量同步、变更检测、实时索引更新

### Q15.5 如果用户用英文提问但知识库是中文的，你们的检索能工作吗？为什么？怎么解决？
**考察点：** bge-small-zh 是中文优化模型，跨语言检索效果差——需要多语言模型（如 multilingual-e5）

### Q15.6 你们有没有考虑过 Agent 的"记忆（Memory）"？短期的对话记忆和长期的知识记忆分别怎么管理？
**考察点：** chat history = 短期记忆；knowledge base = 长期记忆；MemoryEvaluator 评估记忆质量

### Q15.7 你了解 MCP（Model Context Protocol）吗？你们的 Agent 工具可以用 MCP 来暴露吗？
**考察点：** 对最新 Agent 生态的了解

### Q15.8 Function Calling 和你们现在的工具调用方式有什么区别？你们的 Agent 用的是哪种？
**考察点：** LangGraph 的 tool calling vs OpenAI Function Calling vs 自定义路由

### Q15.9 你们的 Auto-Tagger 是怎么实现的？用 LLM 自动打标签的准确性怎么样？
**考察点：** auto_tagger.py — LLM 分析内容生成标签，temperature=0.1

### Q15.10 如果你们的 Agent 在生产环境中给出了错误的知识库修改建议并被用户确认了，怎么恢复？
**考察点：** Git rollback + reindex

### Q15.11 你们项目中最有技术挑战的一个问题是什么？你是怎么解决的？
**考察点：** 综合能力和解决问题的思路

### Q15.12 你在这个项目中犯过的最大的一个技术错误是什么？从中学到了什么？
**考察点：** 自我反思和成长能力

### Q15.13 如果知识库中存了一些敏感信息（如密码、API Key），你们的系统有什么机制来防止泄露？
**考察点：** 知识库内容审查、LLM 输出过滤

### Q15.14 你们评估系统中的 "Monotonicity Benchmark" 是什么意思？为什么需要测试单调性？
**考察点：** 评估分数是否随 Agent 能力单调递增——能力越强分数越高，不能出现"更差的 Agent 得分更高"

### Q15.15 如果要给你们的 Agent 加一个"成本预算"功能（限制每次对话的 API 调用费用），你会怎么设计？
**考察点：** token 计数 + 费用估算 + 预算控制

---

## 附：面试建议

### 回答技巧
1. **STAR 法则**：Situation（背景）→ Task（任务）→ Action（行动）→ Result（结果）
2. **先总后分**：先说结论，再展开细节
3. **数据支撑**：用数字说明效果（如"并行优化后评估速度提升 5 倍"）
4. **对比分析**：说明为什么选 A 不选 B（展示决策过程）
5. **承认不足**：说出项目的局限性和改进方向（展示成长性）

### 高频考点优先级
| 优先级 | 考点 | 原因 |
|--------|------|------|
| ⭐⭐⭐⭐⭐ | LangGraph Agent 设计 | Agent 开发工程师的核心技能 |
| ⭐⭐⭐⭐⭐ | RAG 全链路 | 最常见的 Agent 应用场景 |
| ⭐⭐⭐⭐⭐ | Embedding + 向量搜索 | RAG 的技术基础 |
| ⭐⭐⭐⭐ | 混合搜索（RRF） | 检索质量的关键 |
| ⭐⭐⭐⭐ | 评估体系 | 体现系统化思维 |
| ⭐⭐⭐⭐ | HITL 设计 | Agent 安全性的关键 |
| ⭐⭐⭐ | LLM 多模型集成 | 工程能力 |
| ⭐⭐⭐ | 数据一致性 | 系统设计能力 |
| ⭐⭐ | 性能优化 | 进阶能力 |
| ⭐⭐ | SDK 设计 | 架构能力 |





