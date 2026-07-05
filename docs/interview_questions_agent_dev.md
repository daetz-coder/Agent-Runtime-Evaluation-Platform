# Agent 开发工程师 — 基于本项目的面试问题清单

> **参考答案**：每道题的详细参考答案已生成，见 [面试参考答案索引](interview/README.md)（`docs/interview/answers/Q001-*.md` 共 200 篇）。重新生成：`python scripts/generate_interview_answers.py`
>
> 本文档以 **Agent Runtime Evaluation Platform** 为考察背景，模拟招聘方（技术面试官 / 架构师 / Team Lead）在 Agent 开发工程师岗位面试中可能提出的问题。  
> 问题按模块分类，由浅入深；标注 **★** 的为高频/核心题，**★★★** 为深度追问。

---

## 目录

1. [项目理解与动机](#1-项目理解与动机)
2. [Agent 架构与设计理念](#2-agent-架构与设计理念)
3. [轨迹（Trajectory）与埋点](#3-轨迹trajectory与埋点)
4. [LangGraph 与工作流编排](#4-langgraph-与工作流编排)
5. [LLM-as-Judge 评估体系](#5-llm-as-judge-评估体系)
6. [六维评估器深入](#6-六维评估器深入)
7. [RAG 与检索质量](#7-rag-与检索质量)
8. [Wiki Agent 端到端实现](#8-wiki-agent-端到端实现)
9. [SDK 与零侵入接入](#9-sdk-与零侵入接入)
10. [Benchmark 与评估校准](#10-benchmark-与评估校准)
11. [后端工程与 API 设计](#11-后端工程与-api-设计)
12. [系统设计与生产化](#12-系统设计与生产化)
13. [调试、排错与案例分析](#13-调试排错与案例分析)
14. [编码与现场设计题](#14-编码与现场设计题)
15. [开放讨论与行为面](#15-开放讨论与行为面)

---

## 1. 项目理解与动机

### 基础认知

1. **★** 请用 3 分钟介绍这个项目：它解决什么问题？目标用户是谁？
2. **★** 为什么需要「Agent 运行时评估平台」，而不是直接用人工标注或端到端任务成功率？
3. 平台评估的是 Agent 的「过程质量」还是「结果质量」？两者如何平衡？
4. 六维评估（Planning / Tactical / Tool Use / Memory / Replan / Retrieval）是如何选出来的？少一维或多一维会怎样？
5. 这个项目与 LangSmith、Arize Phoenix、Braintrust 等 Agent 观测/评估工具有什么异同？
6. 如果让你向非技术人员（产品经理）解释「单调性基准测试」，你会怎么说？
7. Wiki Agent 在本项目中的角色是什么？是核心产品还是 Demo？为什么要把 RAG Agent 和评估平台放在同一个仓库？

### 技术选型

8. **★** 为什么选择 LangGraph 而不是纯 LangChain AgentExecutor、AutoGen、CrewAI？
9. 为什么后端选 FastAPI + 异步 SQLAlchemy，而不是 Django / Flask？
10. 默认 LLM 为什么选 DeepSeek？切换 OpenAI / Anthropic / 智谱 / 通义时，评估结果的可比性如何保证？
11. 向量库为什么用 Milvus Lite 而不是 Chroma、FAISS、pgvector？生产环境你会怎么换？
12. 前端为什么用 Vue 3 而不是 React？对 Agent 开发工程师这个岗位，前端能力是否必须？

---

## 2. Agent 架构与设计理念

### 核心范式

13. **★** 请解释「轨迹驱动评估（Trajectory-driven Evaluation）」：平台本身不运行被评 Agent，这种设计有什么优缺点？
14. 被评估 Agent 和评估平台之间的边界在哪里？数据流是怎样的？
15. 如果 Agent 运行在多进程 / 多机 / K8s 集群上，轨迹如何汇聚到评估平台？
16. `ActionType` 定义了 14 种动作类型（plan、tool_call、retrieval、evidence 等），为什么要这么细？能否合并成更少的类型？
17. **★★★** `tool_call` 和 `tool_result` 为什么要分开记录？对 Tool Use 评估有什么影响？
18. `think`、`node_execute`、`tool_decision` 分别记录什么？在什么场景下会用到？
19. `evidence` 动作类型的设计意图是什么？它和 `retrieval` 有什么区别？
20. 如果第三方 Agent 框架（如 Semantic Kernel）无法按你的 schema 上报轨迹，你会怎么适配？

### Agent 状态与上下文

21. Agent 的 `context`（如 `key_facts`）在评估中起什么作用？Memory Evaluator 如何利用它？
22. 长对话场景下，轨迹可能非常长，评估时如何处理 token 超限？
23. 多轮对话中，如何区分「同一任务的多轮迭代」和「多个独立子任务」？
24. Human-in-the-loop 场景下，轨迹里应该记录什么？Wiki Agent 的 interrupt 机制如何体现？

---

## 3. 轨迹（Trajectory）与埋点

### 收集机制

25. **★** 请说明 `sdk/collector.py` 的 TrajectoryCollector 如何统一所有 Agent 的轨迹采集？HTTP 模式如何避免自死锁？
26. SDK 的 `finish(auto_run=True)` 做了什么？离线缓冲是如何实现的？
27. `EVAL_BATCH_SIZE` 批量上报的设计考虑是什么？太小或太大有什么影响？
28. 轨迹上报失败时（网络抖动、后端 500），SDK 会丢数据还是重试？你会如何改进？
29. 线程安全：`TrajectoryCollector` 用了什么锁策略？高并发 Agent 会有什么问题？

### 埋点策略

30. **★** 什么是「低侵入埋点」？本项目提供了哪三种 adapter？各自适用什么场景？
31. LangGraph adapter 如何「透明包装」节点函数？包装后性能开销如何估算？
32. Callback adapter 能捕获哪些事件？LangChain 的 `on_llm_start` / `on_tool_end` 如何映射到 ActionType？
33. LLM Proxy adapter 的「幂等包装」是什么意思？为什么需要 idempotent？
34. 如果 Agent 内部有自定义工具（非 LangChain Tool），如何手动调用 collector 上报？
35. Wiki Agent 使用 `EvaluationTrace` 显式埋点，与 SDK 自动埋点相比，哪种更好？为什么 Demo 选了显式埋点？

### 数据质量

36. **★★★** 轨迹数据不完整（例如只有 tool_call 没有 tool_result）时，各 Evaluator 如何表现？
37. 如何检测「伪造轨迹」或「过度清洗的轨迹」导致评估失真？
38. `observation` 字段非字符串时会 `json.dumps`，为什么？下游 Evaluator 如何消费？
39. 轨迹 step_number 的语义是什么？乱序上报如何处理？

---

## 4. LangGraph 与工作流编排

### 评估工作流

40. **★** 请画出评估工作流：`validate → 六维评估 → aggregate` 的完整流程。
41. LangGraph 评估图（`evaluation_graph.py`）的节点是如何定义的？State 里有哪些字段？
42. **★★★** 代码注释写「LangGraph 并行评估」，但实际图是串行的；生产环境却用 `asyncio.gather` 并行。请解释这个「双路径」设计的原因。
43. `EVAL_PARALLEL=True/False` 切换时，行为差异是什么？什么场景下应该用串行？
44. LangGraph 状态合并（state merge）冲突是什么？为什么并行 evaluator 节点会导致冲突？
45. 如果未来要在 LangGraph 里实现真正的并行评估节点，你会怎么改 State 设计？

### Wiki Agent 工作流

46. Wiki Agent 的 LangGraph 图有哪些节点？`search → respond → decide → execute` 各自职责是什么？
47. `AsyncSqliteSaver` checkpoint 的作用是什么？会话恢复如何实现？
48. Wiki Agent 的 `decide` 节点如何判断是否需要 human-in-the-loop？
49. 知识提取（extraction）流程是如何触发的？提取结果如何写入知识库并触发 reindex？

### 通用 LangGraph 能力

50. **★** LangGraph 的 `StateGraph` 和 `CompiledStateGraph` 区别是什么？
51. 条件边（conditional edge）在 Agent 里通常怎么用？本项目有没有用到？
52. Subgraph 和 parent graph 如何共享状态？有没有考虑过把 Wiki Agent 拆成 subgraph？
53. LangGraph 的 `interrupt` 机制原理是什么？和 Celery 任务暂停有什么区别？

---

## 5. LLM-as-Judge 评估体系

### 方法论

54. **★** 什么是 LLM-as-Judge？相比传统 rubric + 人工打分，优势和局限分别是什么？
55. 为什么所有 Evaluator 都设 `temperature=0`？如果改成 0.7 会怎样？
56. Judge LLM 和被评估 Agent 用同一个模型，会有「自评偏见」吗？如何缓解？
57. **★★★** JSON 解析失败时 fallback 到 50 分，这个策略合理吗？有没有更好的降级方案？
58. 如何从 LLM 响应中抽取 JSON？`content.find("{")` 这种方法有什么漏洞？
59. 是否考虑过 Structured Output / Function Calling 来约束 Judge 输出格式？
60. 多模型共识评估（`consensus.py`）中，`std_score` 如何解读？标准差大于多少应该告警？

### Prompt 工程

61. **★** 请描述 Planning Evaluator 的 prompt 结构：输入是什么？要求 Judge 输出哪些字段？
62. 各 Evaluator 的 prompt 是中文还是英文？对 Judge 质量有什么影响？
63. 如何在 prompt 里注入 few-shot 示例？本项目有没有做？效果如何？
64. 如果 Judge 给出的 feedback 和 score 不一致（高分但 feedback 全是批评），如何处理？
65. 如何防止 Judge prompt 被 trajectory 里的恶意内容注入（Prompt Injection）？
66. 评估 prompt 的版本管理策略是什么？改了 prompt 如何对比历史评估结果？

### 成本与性能

67. 一次完整六维评估大约消耗多少 token？成本如何估算？
68. Dashboard 上的「成本追踪」是如何计算的？准确吗？
69. 六维并行评估从 71s 降到 ~15s，瓶颈在哪里？还能继续优化吗？
70. 是否考虑过缓存相同 trajectory 的评估结果？缓存 key 如何设计？
71. 评估结果能否复用（例如只改了 Tactical prompt，其他五维能否跳过）？

---

## 6. 六维评估器深入

### Planning Evaluator

72. **★** Planning 的四个子维度（coverage、ordering、granularity、completeness）分别评估什么？
73. 权重 0.3/0.2/0.2/0.3 是如何确定的？能否用数据驱动调权？
74. 没有 `plan` 或 `plan_update` 动作时，Planning 得 0 分——这个规则是否过于严格？
75. 「计划粒度（granularity）」如何在 prompt 里定义？过细和过粗的计划如何区分？

### Tactical Evaluator

76. Tactical 评估「除 plan 外所有 action」——为什么排除 plan？
77. relevance / efficiency / correctness 三个子维度，请各举一个高分和低分的 trajectory 例子。
78. 如果 Agent 做了正确决策但工具返回错误导致失败，Tactical 应该怎么打分？

### Tool Use Evaluator

79. **★** selection_quality、parameter_accuracy、result_utilization 分别看什么？
80. Agent 调用了正确工具但参数 JSON 格式错误，各子维度如何扣分？
81. 工具返回结果被 Agent 忽略（result_utilization 低），在实际 Agent 里常见吗？如何检测？

### Memory Evaluator

82. Memory 的 retention / relevance / consistency 如何定义？
83. `context.key_facts` 和从 trajectory 启发式推断的记忆，哪个更可靠？
84. Agent 没有显式 memory_read/write 动作时，Memory Evaluator 如何工作？
85. 长期记忆 vs 工作记忆，评估上应该分开吗？

### Replan Evaluator

86. **★★★** 没有 replan 事件时默认满分 100——请解释这个设计逻辑，是否合理？
87. trigger_appropriateness 如何判断「该重规划却没重规划」？
88. `failure` 动作和 `replan` 的关系是什么？连续 5 次失败触发 replan 的启发式在哪里？
89. 对比 OpenAI 的 replanning 论文或 industry best practice，本项目的 Replan 评估缺什么？

### Retrieval Evaluator

90. **★** Retrieval 的三个子维度（relevance、evidence_accuracy、coverage）如何对应 RAG 质量？
91. `retrieved_docs` 的数据结构是什么？需要哪些字段才能评估？
92. 没有 retrieval 动作时得 0 分——对非 RAG Agent 是否公平？
93. 如何评估「幻觉」：Agent 用了检索结果但歪曲了原文？
94. coverage 低但 relevance 高，说明什么问题？如何给 Agent 开发者 actionable 的建议？

### 聚合与 Overall Score

95. 六维 overall 权重（planning 20%、tactical 20%、其余各 15%）是如何定的？
96. 为什么要先算各维子维度加权，再算六维 overall 加权？能否端到端一个分数？
97. 如果某一维 Evaluator 异常返回 0，对 overall 影响多大？是否应该降权或标记不可信？

---

## 7. RAG 与检索质量

### 索引与分块

98. **★** Markdown 分块策略：chunk size 500、overlap 50 是如何选的？
99. 分块时如何处理标题层级？标题是否拼进 chunk 文本？
100. 代码块、表格、列表在分块时有什么特殊处理？
101. 知识库更新后，增量索引 vs 全量 rebuild 如何选择？`sync_manager.py` 如何实现？

### Embedding 与向量库

102. 为什么选 `BAAI/bge-small-zh-v1.5`？512 维够用吗？
103. Embedding 加载失败时返回零向量——这个降级策略对检索质量影响多大？
104. Milvus collection schema 如何设计？有哪些字段（path、chunk、title、embedding）？
105. Milvus 不可用时 semantic search 降级为 BM25——用户体验上如何感知？

### 混合检索

106. **★★★** 请解释 RRF（Reciprocal Rank Fusion）公式，k=60 的含义是什么？
107. 为什么用 RRF 而不是加权分数融合（如 0.7×semantic + 0.3×BM25）？
108. jieba 分词 + 停用词对 BM25 的影响？英文内容检索效果如何？
109. 语义检索按 path 去重保留最高分 chunk——为什么去重？会丢失信息吗？
110. hybrid_search 的 top_k 如何选？召回率和精度的 trade-off 如何调？

### RAG 评估闭环

111. Wiki Agent search 节点如何 `record_retrieval`？数据如何流到 RetrievalEvaluator？
112. 如何构造「检索好但生成差」和「检索差但生成碰巧对」的测试用例？
113. RAG 评估中，ground truth 从哪里来？本项目有没有标注数据集？

---

## 8. Wiki Agent 端到端实现

114. **★** Wiki Agent 的完整请求链路：用户提问 → 检索 → 生成 → 可选知识提取，请逐步说明。
115. Chat 接口是 SSE 流式还是一次性返回？流式事件类型有哪些？
116. `SYSTEM_PROMPT` 的核心约束是什么？如何减少幻觉？
117. 知识自动提取（auto extraction）的触发条件和确认流程是什么？
118. 用户 reject 提取结果后，状态如何更新？会不会重复提示？
119. Wiki 页面的 CRUD 如何触发向量索引同步？删除页面后 Milvus 和 BM25 如何清理？
120. Git 风格的 history / rollback 是如何实现的？回滚后索引如何恢复？
121. Wiki Agent 的 `EvaluationTrace` 记录了哪些事件？与 SDK collector 上报格式是否一致？
122. `EVAL_AUTO_RUN` 如何在 Wiki 对话结束后自动触发评估？异步链路是什么？

---

## 9. SDK 与零侵入接入

123. **★** 「零侵入 SDK 接入」的具体含义是什么？开发者最少需要改几行代码？
124. 三种 adapter 的安装/导入路径是什么？为什么统一放在 `sdk/adapters/`？
125. LangGraph adapter 包装后，原有的 `graph.compile()`、`graph.ainvoke()` 接口是否完全兼容？
126. 同步节点函数和异步节点函数，adapter 如何处理？
127. 状态 diff 截断策略是什么？大 state 会不会导致轨迹爆炸？
128. SDK 能否独立 pip 安装并在非本项目 Agent 中使用？依赖有哪些？
129. 如果 Agent 使用非 LangChain 技术栈（纯 OpenAI API、Anthropic SDK），如何接入？
130. SDK 的 `ActionType` 和平台 `app/models/action_types.py` 如何保持一致？

---

## 10. Benchmark 与评估校准

131. **★** 什么是「单调性基准测试（Monotonicity Benchmark）」？通过标准是什么？
132. 六条合成轨迹（优秀/良好/中等/差/对抗/空）是如何构造的？参考分 93.1→20.0 怎么来的？
133. 容差 +0.05 的含义是什么？为什么需要容差而不是严格单调？
134. 如果某条轨迹分数逆序（中等比良好高），如何定位是哪个 Evaluator 的问题？
135. `eval_evaluator_accuracy.py` 的好/坏场景对比测试是如何设计的？
136. 如何用真实业务 trajectory 补充合成 benchmark？需要多少条才够？
137. 评估器的「准确率」如何定义？有没有 inter-rater agreement（人工 vs LLM Judge）实验？
138. 多模型 benchmark（`benchmark_multimodel.py`）结论是什么？不同 Judge 模型排序是否一致？

---

## 11. 后端工程与 API 设计

139. **★** 评估 API `POST /evaluations` 返回 202 异步，客户端如何获取结果？轮询还是 SSE？
140. `POST /evaluations/stream` SSE 事件格式是什么？progress / result / done 各携带什么？
141. 已完成评估的 SSE replay 为什么不重跑 LLM？如何实现？
142. 任务状态机：PENDING → RUNNING → COMPLETED，什么事件触发状态变更？
143. 为什么轨迹推送时任务保持 PENDING，评估开始才 RUNNING？
144. SQLAlchemy 2.0 async session 的生命周期如何管理？`Depends(get_db)` 模式？
145. SQLite 默认 + PostgreSQL 可选，迁移策略是什么？Alembic 用到什么程度？
146. 可选 API Key 认证（`AUTH_ENABLED`）的实现方式？哪些路径跳过认证？
147. `/health` 和 `/api/v1/system/health` 为什么有两个？前端开发环境 proxy 如何配置？

---

## 12. 系统设计与生产化

### 扩展性

148. **★★★** 如果日评估量从 100 次增长到 10 万次，架构上需要改什么？
149. 评估任务是否应该引入 Celery / Redis Queue？BackgroundTasks 的局限是什么？
150. 多租户（workspace）隔离如何实现？`workspace_endpoints.py` 的设计意图？
151. 评估结果如何做版本化（prompt 版本、模型版本、evaluator 版本）？
152. 如何实现 A/B 测试：同一 trajectory 用两套 Evaluator prompt 对比？

### 可靠性

153. 评估中途 Judge LLM 超时或 429 限流，如何重试？会不会部分维度成功、部分失败？
154. 数据库写入和 LLM 调用的一致性如何保证？评估失败时 DB 状态如何回滚？
155. Wiki Agent Milvus 和 BM25 双索引不一致时，如何检测和修复？
156. 如何实现评估任务的幂等性（同一 task_id 重复触发评估）？

### 安全

157. trajectory 里可能包含用户 PII 或 API Key，平台如何脱敏？
158. Wiki 知识库上传 Markdown 有没有 XSS / 路径遍历风险？
159. `EVAL_WEBHOOK_URL` 通知机制的安全考虑？

### 观测

160. 平台自身的 logging / tracing 策略是什么？评估链路有没有 OpenTelemetry？
161. 如何监控 Judge LLM 的 latency P99、error rate、token usage？

---

## 13. 调试、排错与案例分析

162. **★** 用户反馈「Planning 分数总是很低」，你的排查步骤是什么？
163. 评估 overall 80 分但用户认为 Agent 表现很差——如何解释和处理？
164. Retrieval 0 分但 Agent 明明做了 RAG——最可能的原因是什么？
165. 单调性 benchmark 失败，如何定位是数据问题还是 Evaluator bug？
166. Wiki Agent 回答不引用知识库内容，从检索到生成，逐步怎么 debug？
167. Milvus `available: false`，系统状态页显示什么？如何恢复？
168. 前端 Dashboard 图表为空，可能有哪些原因（数据、API、前端渲染）？
169. SSE 评估流中途断开，客户端如何恢复？
170. JSON.parse 错误（如系统设置页 `/health` 返回 HTML）——根因和修复思路？

---

## 14. 编码与现场设计题

### 代码阅读

171. **★** 请阅读 `BaseEvaluator._extract_tool_calls`，说明它如何从 trajectory 提取工具调用对。
172. 阅读 `evaluate_parallel()`，解释并发控制和异常处理逻辑。
173. 阅读 `instrument_langgraph` 的核心包装逻辑，说明如何拦截节点执行。
174. 阅读 `hybrid_search` 的 RRF 实现，手工算两个排名的融合结果。

### 现场实现

175. **★** 新增第七维 Evaluator「Safety」，评估 Agent 是否输出有害内容，需要改哪些文件？
176. 实现一个 Evaluator：检测 Agent 是否在 10 步内完成任务（效率指标），如何设计？
177. 给 SDK 增加「采样率」配置：只有 10% 的 tool_call 上报，如何实现？
178. 实现 trajectory 的 gzip 压缩上报，前后端各改什么？
179. 给 Planning Evaluator 增加「计划是否可执行」子维度，写出 prompt 草案和解析逻辑。
180. 实现一个简单的「评估结果 diff」API：对比同一 task 两次评估的六维分数变化。

### 系统设计

181. **★★★** 设计一个「评估流水线 2.0」：支持自定义 Evaluator 插件、动态权重、多 Judge 投票。
182. 设计跨项目的 Agent 评估联邦：多个团队各自部署 Agent，中央平台统一评估。
183. 设计一个「在线评估」模式：Agent 运行每一步都实时打分并反馈给 Agent 自我修正。
184. 如何把本平台的评估能力封装成 MCP Server，供 Cursor / Claude Desktop 调用？
185. 设计 Agent 评估的「黄金数据集」构建流程：采集、标注、版本、回归。

---

## 15. 开放讨论与行为面

### 技术视野

186. **★** 2024–2026 年 Agent 领域最重要的技术趋势是什么？对本项目有什么启示？
187. 你怎么看 Multi-Agent 评估？本项目能否扩展到评估 Agent 团队协作？
188. Agent 的「可解释性」和「可评估性」是什么关系？
189. RLHF / DPO 训练的 Agent 和 prompt-based Agent，评估方法应该有什么不同？
190. 长上下文（128K+）对轨迹收集和评估有什么新挑战？

### 项目经验（结合候选人自述）

191. 你在项目中负责哪一块？最大的技术挑战是什么？
192. 有没有遇到过 Judge LLM 和人工评分严重不一致的情况？怎么处理的？
193. 如果重新做这个项目，你会改变哪个架构决策？为什么？
194. 项目里有没有「看起来能跑但设计上不满意」的技术债？你怎么看待？
195. 从 0 到 1 搭建 Agent 系统，你会优先做评估平台还是优先做 Agent 本身？

### 协作与交付

196. 如何向 Agent 应用团队推广轨迹上报规范？他们不愿意改代码怎么办？
197. 评估标准和业务 KPI 冲突时（例如评估高分但用户满意度低），如何对齐？
198. 如何在 CI/CD 里集成单调性 benchmark 作为 merge gate？
199. 写 Evaluator prompt 时，如何与领域专家（法务、医疗等）协作？
200. 如果产品经理要求「一个数字概括 Agent 好坏」，你怎么回应？

---

## 附录 A：面试官追问路径示例

以 **「请介绍 Planning Evaluator」** 为例，典型追问链：

```
Q1: Planning 评估哪四个子维度？
  ↓
Q2: 权重为什么这样分配？
  ↓
Q3: 没有 plan 动作为什么得 0 分而不是 N/A？
  ↓
Q4: 如果 plan 在 think 里而不是 plan action 里，怎么办？
  ↓
Q5: Judge prompt 如何定义 granularity？
  ↓
Q6: JSON 解析失败怎么处理？有没有更好的方案？
  ↓
Q7: 如何用 benchmark 验证 Planning Evaluator 有效？
  ↓
Q8: 如果让你重写 Planning Evaluator，你会怎么改？
```

---

## 附录 B：建议掌握的关键文件

| 模块 | 路径 | 面试前建议 |
|------|------|------------|
| 评估器基类 | `app/evaluators/base.py` | 通读，能讲 extraction 方法 |
| 六维 Evaluator | `app/evaluators/*.py` | 至少精读 Planning + Retrieval |
| 评估图 | `app/graphs/evaluation_graph.py` | 理解串行 vs 并行 |
| 评估服务 | `app/services/evaluation_service.py` | 理解异步评估流程 |
| 轨迹 SDK | `sdk/collector.py` | 理解上报 API |
| LangGraph 适配 | `sdk/adapters/langgraph.py` | 理解包装原理 |
| Wiki Agent 图 | `app/wiki_agent/agent/graph.py` | 理解 RAG + 埋点 |
| 混合检索 | `app/wiki_agent/agent/tools/search_tools.py` | 理解 RRF |
| 单调性基准 | `app/benchmarks/monotonicity.py` | 能解释通过标准 |
| Action 类型 | `app/models/action_types.py` | 记住 14 种类型的语义 |

---

## 附录 C：不同级别的考察侧重

| 级别 | 重点考察模块 | 期望深度 |
|------|-------------|----------|
| 初级 Agent 工程师 | 项目理解、轨迹埋点、ActionType、基础 Evaluator | 能跑通 Demo，理解数据流 |
| 中级 Agent 工程师 | LangGraph 编排、LLM-as-Judge、RAG 检索、SDK 接入 | 能独立新增 Evaluator 或 adapter |
| 高级 Agent 工程师 | 评估校准、系统设计、生产化、benchmark 方法论 | 能设计评估体系并推动落地 |
| 架构师方向 | 多租户、联邦评估、在线评估、与训练闭环 | 能权衡 trade-off 并定标准 |

---

*文档版本：基于项目 main 分支（2026-06）整理。共 **200+** 道问题，覆盖从入门到架构的全链路考察。*
