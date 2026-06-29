# Agent 开发工程师面试题 — 参考答案索引

> 本目录由 `scripts/generate_interview_answers.py` 自动生成。
> 问题来源：[interview_questions_agent_dev.md](../interview_questions_agent_dev.md)

共 **200** 道题，按分类索引如下。


## 项目理解与动机

- [★★ Q001](answers/Q001-项目介绍.md) — 请用 3 分钟介绍这个项目：它解决什么问题？目标用户是谁？
- [★★ Q002](answers/Q002-运行时评估必要性.md) — 为什么需要「Agent 运行时评估平台」，而不是直接用人工标注或端到端任务成功率？
- [★ Q003](answers/Q003-过程与结果质量.md) — 平台评估的是 Agent 的「过程质量」还是「结果质量」？两者如何平衡？
- [★ Q004](answers/Q004-六维选型.md) — 六维评估（Planning / Tactical / Tool Use / Memory / Replan / Retrieval）是如何选出来的？少一维或多一维会怎样？
- [★ Q005](answers/Q005-与观测工具对比.md) — 这个项目与 LangSmith、Arize Phoenix、Braintrust 等 Agent 观测/评估工具有什么异同？
- [★ Q006](answers/Q006-单调性基准解释.md) — 如果让你向非技术人员（产品经理）解释「单调性基准测试」，你会怎么说？
- [★ Q007](answers/Q007-Wiki-Agent角色.md) — Wiki Agent 在本项目中的角色是什么？是核心产品还是 Demo？为什么要把 RAG Agent 和评估平台放在同一个仓库？
- [★★ Q008](answers/Q008-为何选LangGraph.md) — 为什么选择 LangGraph 而不是纯 LangChain AgentExecutor、AutoGen、CrewAI？
- [★ Q009](answers/Q009-为何选FastAPI.md) — 为什么后端选 FastAPI + 异步 SQLAlchemy，而不是 Django / Flask？
- [★ Q010](answers/Q010-LLM选型与可比性.md) — 默认 LLM 为什么选 DeepSeek？切换 OpenAI / Anthropic / 智谱 / 通义时，评估结果的可比性如何保证？
- [★ Q011](answers/Q011-Milvus选型.md) — 向量库为什么用 Milvus Lite 而不是 Chroma、FAISS、pgvector？生产环境你会怎么换？
- [★ Q012](answers/Q012-Vue前端选型.md) — 前端为什么用 Vue 3 而不是 React？对 Agent 开发工程师这个岗位，前端能力是否必须？

## Agent 架构与设计理念

- [★★ Q013](answers/Q013-轨迹驱动评估.md) — 请解释「轨迹驱动评估（Trajectory-driven Evaluation）」：平台本身不运行被评 Agent，这种设计有什么优缺点？
- [★ Q014](answers/Q014-评估边界与数据流.md) — 被评估 Agent 和评估平台之间的边界在哪里？数据流是怎样的？
- [★ Q015](answers/Q015-分布式轨迹汇聚.md) — 如果 Agent 运行在多进程 / 多机 / K8s 集群上，轨迹如何汇聚到评估平台？
- [★ Q016](answers/Q016-ActionType粒度.md) — `ActionType` 定义了 14 种动作类型（plan、tool_call、retrieval、evidence 等），为什么要这么细？能否合并成更少的类型？
- [★★★ Q017](answers/Q017-tool-call-result分离.md) — `tool_call` 和 `tool_result` 为什么要分开记录？对 Tool Use 评估有什么影响？
- [★ Q018](answers/Q018-think-node-decision.md) — `think`、`node_execute`、`tool_decision` 分别记录什么？在什么场景下会用到？
- [★ Q019](answers/Q019-evidence与retrieval.md) — `evidence` 动作类型的设计意图是什么？它和 `retrieval` 有什么区别？
- [★ Q020](answers/Q020-第三方框架适配.md) — 如果第三方 Agent 框架（如 Semantic Kernel）无法按你的 schema 上报轨迹，你会怎么适配？
- [★ Q021](answers/Q021-context与Memory.md) — Agent 的 `context`（如 `key_facts`）在评估中起什么作用？Memory Evaluator 如何利用它？
- [★ Q022](answers/Q022-轨迹token超限.md) — 长对话场景下，轨迹可能非常长，评估时如何处理 token 超限？
- [★ Q023](answers/Q023-多轮与子任务.md) — 多轮对话中，如何区分「同一任务的多轮迭代」和「多个独立子任务」？
- [★ Q024](answers/Q024-HITL轨迹记录.md) — Human-in-the-loop 场景下，轨迹里应该记录什么？Wiki Agent 的 interrupt 机制如何体现？

## 轨迹（Trajectory）与埋点

- [★★ Q025](answers/Q025-两套collector对比.md) — 请说明 `sdk/collector.py` 与 `app/collectors/inprocess_transport.py` 的关系：为什么 Wiki 内嵌时需要 in-process transport？
- [★ Q026](answers/Q026-finish与离线缓冲.md) — SDK 的 `finish(auto_run=True)` 做了什么？离线缓冲是如何实现的？
- [★ Q027](answers/Q027-EVAL_BATCH_SIZE.md) — `EVAL_BATCH_SIZE` 批量上报的设计考虑是什么？太小或太大有什么影响？
- [★ Q028](answers/Q028-上报失败重试.md) — 轨迹上报失败时（网络抖动、后端 500），SDK 会丢数据还是重试？你会如何改进？
- [★ Q029](answers/Q029-线程安全.md) — 线程安全：`TrajectoryCollector` 用了什么锁策略？高并发 Agent 会有什么问题？
- [★★ Q030](answers/Q030-低侵入埋点.md) — 什么是「低侵入埋点」？本项目提供了哪三种 adapter？各自适用什么场景？
- [★ Q031](answers/Q031-LangGraph包装.md) — LangGraph adapter 如何「透明包装」节点函数？包装后性能开销如何估算？
- [★ Q032](answers/Q032-Callback映射.md) — Callback adapter 能捕获哪些事件？LangChain 的 `on_llm_start` / `on_tool_end` 如何映射到 ActionType？
- [★ Q033](answers/Q033-LLM-Proxy幂等.md) — LLM Proxy adapter 的「幂等包装」是什么意思？为什么需要 idempotent？
- [★ Q034](answers/Q034-手动collector上报.md) — 如果 Agent 内部有自定义工具（非 LangChain Tool），如何手动调用 collector 上报？
- [★ Q035](answers/Q035-显式vs自动埋点.md) — Wiki Agent 使用 `EvaluationTrace` 显式埋点，与 SDK 自动埋点相比，哪种更好？为什么 Demo 选了显式埋点？
- [★★★ Q036](answers/Q036-轨迹不完整.md) — 轨迹数据不完整（例如只有 tool_call 没有 tool_result）时，各 Evaluator 如何表现？
- [★ Q037](answers/Q037-伪造轨迹检测.md) — 如何检测「伪造轨迹」或「过度清洗的轨迹」导致评估失真？
- [★ Q038](answers/Q038-observation序列化.md) — `observation` 字段非字符串时会 `json.dumps`，为什么？下游 Evaluator 如何消费？
- [★ Q039](answers/Q039-step-number语义.md) — 轨迹 step_number 的语义是什么？乱序上报如何处理？

## LangGraph 与工作流编排

- [★★ Q040](answers/Q040-评估工作流.md) — 请画出评估工作流：`validate → 六维评估 → aggregate` 的完整流程。
- [★ Q041](answers/Q041-评估图State.md) — LangGraph 评估图（`evaluation_graph.py`）的节点是如何定义的？State 里有哪些字段？
- [★★★ Q042](answers/Q042-串行图与并行gather.md) — 代码注释写「LangGraph 并行评估」，但实际图是串行的；生产环境却用 `asyncio.gather` 并行。请解释这个「双路径」设计的原因。
- [★ Q043](answers/Q043-EVAL_PARALLEL切换.md) — `EVAL_PARALLEL=True/False` 切换时，行为差异是什么？什么场景下应该用串行？
- [★ Q044](answers/Q044-State合并冲突.md) — LangGraph 状态合并（state merge）冲突是什么？为什么并行 evaluator 节点会导致冲突？
- [★ Q045](answers/Q045-真并行State改造.md) — 如果未来要在 LangGraph 里实现真正的并行评估节点，你会怎么改 State 设计？
- [★ Q046](answers/Q046-Wiki-Agent节点.md) — Wiki Agent 的 LangGraph 图有哪些节点？`search → respond → decide → execute` 各自职责是什么？
- [★ Q047](answers/Q047-AsyncSqliteSaver.md) — `AsyncSqliteSaver` checkpoint 的作用是什么？会话恢复如何实现？
- [★ Q048](answers/Q048-decide-HITL.md) — Wiki Agent 的 `decide` 节点如何判断是否需要 human-in-the-loop？
- [★ Q049](answers/Q049-知识提取流程.md) — 知识提取（extraction）流程是如何触发的？提取结果如何写入知识库并触发 reindex？
- [★★ Q050](answers/Q050-StateGraph区别.md) — LangGraph 的 `StateGraph` 和 `CompiledStateGraph` 区别是什么？
- [★ Q051](answers/Q051-条件边.md) — 条件边（conditional edge）在 Agent 里通常怎么用？本项目有没有用到？
- [★ Q052](answers/Q052-Subgraph.md) — Subgraph 和 parent graph 如何共享状态？有没有考虑过把 Wiki Agent 拆成 subgraph？
- [★ Q053](answers/Q053-interrupt机制.md) — LangGraph 的 `interrupt` 机制原理是什么？和 Celery 任务暂停有什么区别？

## LLM-as-Judge 评估体系

- [★★ Q054](answers/Q054-LLM-as-Judge.md) — 什么是 LLM-as-Judge？相比传统 rubric + 人工打分，优势和局限分别是什么？
- [★ Q055](answers/Q055-temperature为零.md) — 为什么所有 Evaluator 都设 `temperature=0`？如果改成 0.7 会怎样？
- [★ Q056](answers/Q056-自评偏见.md) — Judge LLM 和被评估 Agent 用同一个模型，会有「自评偏见」吗？如何缓解？
- [★★★ Q057](answers/Q057-JSON-fallback-50分.md) — JSON 解析失败时 fallback 到 50 分，这个策略合理吗？有没有更好的降级方案？
- [★ Q058](answers/Q058-JSON抽取漏洞.md) — 如何从 LLM 响应中抽取 JSON？`content.find("{")` 这种方法有什么漏洞？
- [★ Q059](answers/Q059-Structured-Output.md) — 是否考虑过 Structured Output / Function Calling 来约束 Judge 输出格式？
- [★ Q060](answers/Q060-consensus-std-score.md) — 多模型共识评估（`consensus.py`）中，`std_score` 如何解读？标准差大于多少应该告警？
- [★★ Q061](answers/Q061-Planning-prompt.md) — 请描述 Planning Evaluator 的 prompt 结构：输入是什么？要求 Judge 输出哪些字段？
- [★ Q062](answers/Q062-中英文prompt.md) — 各 Evaluator 的 prompt 是中文还是英文？对 Judge 质量有什么影响？
- [★ Q063](answers/Q063-few-shot.md) — 如何在 prompt 里注入 few-shot 示例？本项目有没有做？效果如何？
- [★ Q064](answers/Q064-分数与feedback不一致.md) — 如果 Judge 给出的 feedback 和 score 不一致（高分但 feedback 全是批评），如何处理？
- [★ Q065](answers/Q065-Prompt-Injection.md) — 如何防止 Judge prompt 被 trajectory 里的恶意内容注入（Prompt Injection）？
- [★ Q066](answers/Q066-prompt版本管理.md) — 评估 prompt 的版本管理策略是什么？改了 prompt 如何对比历史评估结果？
- [★ Q067](answers/Q067-token成本.md) — 一次完整六维评估大约消耗多少 token？成本如何估算？
- [★ Q068](answers/Q068-成本追踪.md) — Dashboard 上的「成本追踪」是如何计算的？准确吗？
- [★ Q069](answers/Q069-并行优化瓶颈.md) — 六维并行评估从 71s 降到 ~15s，瓶颈在哪里？还能继续优化吗？
- [★ Q070](answers/Q070-评估缓存.md) — 是否考虑过缓存相同 trajectory 的评估结果？缓存 key 如何设计？
- [★ Q071](answers/Q071-部分维度复用.md) — 评估结果能否复用（例如只改了 Tactical prompt，其他五维能否跳过）？

## 六维评估器深入

- [★★ Q072](answers/Q072-Planning四子维.md) — Planning 的四个子维度（coverage、ordering、granularity、completeness）分别评估什么？
- [★ Q073](answers/Q073-Planning权重.md) — 权重 0.3/0.2/0.2/0.3 是如何确定的？能否用数据驱动调权？
- [★ Q074](answers/Q074-无plan零分.md) — 没有 `plan` 或 `plan_update` 动作时，Planning 得 0 分——这个规则是否过于严格？
- [★ Q075](answers/Q075-granularity定义.md) — 「计划粒度（granularity）」如何在 prompt 里定义？过细和过粗的计划如何区分？
- [★ Q076](answers/Q076-Tactical排除plan.md) — Tactical 评估「除 plan 外所有 action」——为什么排除 plan？
- [★ Q077](answers/Q077-Tactical例子.md) — relevance / efficiency / correctness 三个子维度，请各举一个高分和低分的 trajectory 例子。
- [★ Q078](answers/Q078-工具错Tactical打分.md) — 如果 Agent 做了正确决策但工具返回错误导致失败，Tactical 应该怎么打分？
- [★★ Q079](answers/Q079-ToolUse三子维.md) — selection_quality、parameter_accuracy、result_utilization 分别看什么？
- [★ Q080](answers/Q080-参数JSON错误.md) — Agent 调用了正确工具但参数 JSON 格式错误，各子维度如何扣分？
- [★ Q081](answers/Q081-result-utilization.md) — 工具返回结果被 Agent 忽略（result_utilization 低），在实际 Agent 里常见吗？如何检测？
- [★ Q082](answers/Q082-Memory三子维.md) — Memory 的 retention / relevance / consistency 如何定义？
- [★ Q083](answers/Q083-key-facts可靠性.md) — `context.key_facts` 和从 trajectory 启发式推断的记忆，哪个更可靠？
- [★ Q084](answers/Q084-无memory动作.md) — Agent 没有显式 memory_read/write 动作时，Memory Evaluator 如何工作？
- [★ Q085](answers/Q085-长短期记忆.md) — 长期记忆 vs 工作记忆，评估上应该分开吗？
- [★★★ Q086](answers/Q086-无replan满分.md) — 没有 replan 事件时默认满分 100——请解释这个设计逻辑，是否合理？
- [★ Q087](answers/Q087-trigger-appropriateness.md) — trigger_appropriateness 如何判断「该重规划却没重规划」？
- [★ Q088](answers/Q088-failure与replan.md) — `failure` 动作和 `replan` 的关系是什么？连续 5 次失败触发 replan 的启发式在哪里？
- [★ Q089](answers/Q089-Replan评估缺口.md) — 对比 OpenAI 的 replanning 论文或 industry best practice，本项目的 Replan 评估缺什么？
- [★★ Q090](answers/Q090-Retrieval三子维.md) — Retrieval 的三个子维度（relevance、evidence_accuracy、coverage）如何对应 RAG 质量？
- [★ Q091](answers/Q091-retrieved-docs结构.md) — `retrieved_docs` 的数据结构是什么？需要哪些字段才能评估？
- [★ Q092](answers/Q092-无retrieval零分.md) — 没有 retrieval 动作时得 0 分——对非 RAG Agent 是否公平？
- [★ Q093](answers/Q093-幻觉评估.md) — 如何评估「幻觉」：Agent 用了检索结果但歪曲了原文？
- [★ Q094](answers/Q094-coverage低建议.md) — coverage 低但 relevance 高，说明什么问题？如何给 Agent 开发者 actionable 的建议？
- [★ Q095](answers/Q095-六维overall权重.md) — 六维 overall 权重（planning 20%、tactical 20%、其余各 15%）是如何定的？
- [★ Q096](answers/Q096-两级加权.md) — 为什么要先算各维子维度加权，再算六维 overall 加权？能否端到端一个分数？
- [★ Q097](answers/Q097-单维异常零分.md) — 如果某一维 Evaluator 异常返回 0，对 overall 影响多大？是否应该降权或标记不可信？

## RAG 与检索质量

- [★★ Q098](answers/Q098-分块策略.md) — Markdown 分块策略：chunk size 500、overlap 50 是如何选的？
- [★ Q099](answers/Q099-标题层级.md) — 分块时如何处理标题层级？标题是否拼进 chunk 文本？
- [★ Q100](answers/Q100-代码块分块.md) — 代码块、表格、列表在分块时有什么特殊处理？
- [★ Q101](answers/Q101-增量索引.md) — 知识库更新后，增量索引 vs 全量 rebuild 如何选择？`sync_manager.py` 如何实现？
- [★ Q102](answers/Q102-BGE选型.md) — 为什么选 `BAAI/bge-small-zh-v1.5`？512 维够用吗？
- [★ Q103](answers/Q103-零向量降级.md) — Embedding 加载失败时返回零向量——这个降级策略对检索质量影响多大？
- [★ Q104](answers/Q104-Milvus-schema.md) — Milvus collection schema 如何设计？有哪些字段（path、chunk、title、embedding）？
- [★ Q105](answers/Q105-Milvus降级BM25.md) — Milvus 不可用时 semantic search 降级为 BM25——用户体验上如何感知？
- [★★★ Q106](answers/Q106-RRF公式.md) — 请解释 RRF（Reciprocal Rank Fusion）公式，k=60 的含义是什么？
- [★ Q107](answers/Q107-RRF-vs加权.md) — 为什么用 RRF 而不是加权分数融合（如 0.7×semantic + 0.3×BM25）？
- [★ Q108](answers/Q108-jieba-BM25.md) — jieba 分词 + 停用词对 BM25 的影响？英文内容检索效果如何？
- [★ Q109](answers/Q109-path去重.md) — 语义检索按 path 去重保留最高分 chunk——为什么去重？会丢失信息吗？
- [★ Q110](answers/Q110-top-k调参.md) — hybrid_search 的 top_k 如何选？召回率和精度的 trade-off 如何调？
- [★ Q111](answers/Q111-record-retrieval.md) — Wiki Agent search 节点如何 `record_retrieval`？数据如何流到 RetrievalEvaluator？
- [★ Q112](answers/Q112-检索好生成差.md) — 如何构造「检索好但生成差」和「检索差但生成碰巧对」的测试用例？
- [★ Q113](answers/Q113-RAG-ground-truth.md) — RAG 评估中，ground truth 从哪里来？本项目有没有标注数据集？

## Wiki Agent 端到端实现

- [★★ Q114](answers/Q114-Wiki完整链路.md) — Wiki Agent 的完整请求链路：用户提问 → 检索 → 生成 → 可选知识提取，请逐步说明。
- [★ Q115](answers/Q115-Chat-SSE.md) — Chat 接口是 SSE 流式还是一次性返回？流式事件类型有哪些？
- [★ Q116](answers/Q116-SYSTEM-PROMPT.md) — `SYSTEM_PROMPT` 的核心约束是什么？如何减少幻觉？
- [★ Q117](answers/Q117-自动提取.md) — 知识自动提取（auto extraction）的触发条件和确认流程是什么？
- [★ Q118](answers/Q118-reject提取.md) — 用户 reject 提取结果后，状态如何更新？会不会重复提示？
- [★ Q119](answers/Q119-CRUD索引同步.md) — Wiki 页面的 CRUD 如何触发向量索引同步？删除页面后 Milvus 和 BM25 如何清理？
- [★ Q120](answers/Q120-history-rollback.md) — Git 风格的 history / rollback 是如何实现的？回滚后索引如何恢复？
- [★ Q121](answers/Q121-EvaluationTrace.md) — Wiki Agent 的 `EvaluationTrace` 记录了哪些事件？与 SDK collector 上报格式是否一致？
- [★ Q122](answers/Q122-EVAL_AUTO_RUN.md) — `EVAL_AUTO_RUN` 如何在 Wiki 对话结束后自动触发评估？异步链路是什么？

## SDK 与零侵入接入

- [★★ Q123](answers/Q123-零侵入SDK.md) — 「零侵入 SDK 接入」的具体含义是什么？开发者最少需要改几行代码？
- [★ Q124](answers/Q124-adapter路径.md) — 三种 adapter 的安装/导入路径是什么？为什么统一放在 `sdk/adapters/`？
- [★ Q125](answers/Q125-LangGraph兼容性.md) — LangGraph adapter 包装后，原有的 `graph.compile()`、`graph.ainvoke()` 接口是否完全兼容？
- [★ Q126](answers/Q126-同步异步节点.md) — 同步节点函数和异步节点函数，adapter 如何处理？
- [★ Q127](answers/Q127-state-diff截断.md) — 状态 diff 截断策略是什么？大 state 会不会导致轨迹爆炸？
- [★ Q128](answers/Q128-SDK独立安装.md) — SDK 能否独立 pip 安装并在非本项目 Agent 中使用？依赖有哪些？
- [★ Q129](answers/Q129-非LangChain接入.md) — 如果 Agent 使用非 LangChain 技术栈（纯 OpenAI API、Anthropic SDK），如何接入？
- [★ Q130](answers/Q130-ActionType同步.md) — SDK 的 `ActionType` 和平台 `app/models/action_types.py` 如何保持一致？

## Benchmark 与评估校准

- [★★ Q131](answers/Q131-单调性基准.md) — 什么是「单调性基准测试（Monotonicity Benchmark）」？通过标准是什么？
- [★ Q132](answers/Q132-合成轨迹.md) — 六条合成轨迹（优秀/良好/中等/差/对抗/空）是如何构造的？参考分 93.1→20.0 怎么来的？
- [★ Q133](answers/Q133-容差0.05.md) — 容差 +0.05 的含义是什么？为什么需要容差而不是严格单调？
- [★ Q134](answers/Q134-逆序定位.md) — 如果某条轨迹分数逆序（中等比良好高），如何定位是哪个 Evaluator 的问题？
- [★ Q135](answers/Q135-eval-evaluator-accuracy.md) — `eval_evaluator_accuracy.py` 的好/坏场景对比测试是如何设计的？
- [★ Q136](answers/Q136-真实轨迹补充.md) — 如何用真实业务 trajectory 补充合成 benchmark？需要多少条才够？
- [★ Q137](answers/Q137-评估准确率.md) — 评估器的「准确率」如何定义？有没有 inter-rater agreement（人工 vs LLM Judge）实验？
- [★ Q138](answers/Q138-多模型benchmark.md) — 多模型 benchmark（`benchmark_multimodel.py`）结论是什么？不同 Judge 模型排序是否一致？

## 后端工程与 API 设计

- [★★ Q139](answers/Q139-POST-evaluations-202.md) — 评估 API `POST /evaluations` 返回 202 异步，客户端如何获取结果？轮询还是 SSE？
- [★ Q140](answers/Q140-SSE事件格式.md) — `POST /evaluations/stream` SSE 事件格式是什么？progress / result / done 各携带什么？
- [★ Q141](answers/Q141-SSE-replay.md) — 已完成评估的 SSE replay 为什么不重跑 LLM？如何实现？
- [★ Q142](answers/Q142-任务状态机.md) — 任务状态机：PENDING → RUNNING → COMPLETED，什么事件触发状态变更？
- [★ Q143](answers/Q143-PENDING与RUNNING.md) — 为什么轨迹推送时任务保持 PENDING，评估开始才 RUNNING？
- [★ Q144](answers/Q144-async-session.md) — SQLAlchemy 2.0 async session 的生命周期如何管理？`Depends(get_db)` 模式？
- [★ Q145](answers/Q145-SQLite-PostgreSQL.md) — SQLite 默认 + PostgreSQL 可选，迁移策略是什么？Alembic 用到什么程度？
- [★ Q146](answers/Q146-AUTH_ENABLED.md) — 可选 API Key 认证（`AUTH_ENABLED`）的实现方式？哪些路径跳过认证？
- [★ Q147](answers/Q147-双health端点.md) — `/health` 和 `/api/v1/system/health` 为什么有两个？前端开发环境 proxy 如何配置？

## 系统设计与生产化

- [★★★ Q148](answers/Q148-10万次日评估.md) — 如果日评估量从 100 次增长到 10 万次，架构上需要改什么？
- [★ Q149](answers/Q149-Celery队列.md) — 评估任务是否应该引入 Celery / Redis Queue？BackgroundTasks 的局限是什么？
- [★ Q150](answers/Q150-多租户workspace.md) — 多租户（workspace）隔离如何实现？`workspace_endpoints.py` 的设计意图？
- [★ Q151](answers/Q151-评估版本化.md) — 评估结果如何做版本化（prompt 版本、模型版本、evaluator 版本）？
- [★ Q152](answers/Q152-AB测试.md) — 如何实现 A/B 测试：同一 trajectory 用两套 Evaluator prompt 对比？
- [★ Q153](answers/Q153-Judge重试429.md) — 评估中途 Judge LLM 超时或 429 限流，如何重试？会不会部分维度成功、部分失败？
- [★ Q154](answers/Q154-DB一致性.md) — 数据库写入和 LLM 调用的一致性如何保证？评估失败时 DB 状态如何回滚？
- [★ Q155](answers/Q155-双索引不一致.md) — Wiki Agent Milvus 和 BM25 双索引不一致时，如何检测和修复？
- [★ Q156](answers/Q156-评估幂等.md) — 如何实现评估任务的幂等性（同一 task_id 重复触发评估）？
- [★ Q157](answers/Q157-PII脱敏.md) — trajectory 里可能包含用户 PII 或 API Key，平台如何脱敏？
- [★ Q158](answers/Q158-Wiki-XSS.md) — Wiki 知识库上传 Markdown 有没有 XSS / 路径遍历风险？
- [★ Q159](answers/Q159-WEBHOOK安全.md) — `EVAL_WEBHOOK_URL` 通知机制的安全考虑？
- [★ Q160](answers/Q160-平台观测.md) — 平台自身的 logging / tracing 策略是什么？评估链路有没有 OpenTelemetry？
- [★ Q161](answers/Q161-Judge监控.md) — 如何监控 Judge LLM 的 latency P99、error rate、token usage？

## 调试、排错与案例分析

- [★★ Q162](answers/Q162-Planning低分排查.md) — 用户反馈「Planning 分数总是很低」，你的排查步骤是什么？
- [★ Q163](answers/Q163-overall高分争议.md) — 评估 overall 80 分但用户认为 Agent 表现很差——如何解释和处理？
- [★ Q164](answers/Q164-Retrieval零分.md) — Retrieval 0 分但 Agent 明明做了 RAG——最可能的原因是什么？
- [★ Q165](answers/Q165-benchmark失败定位.md) — 单调性 benchmark 失败，如何定位是数据问题还是 Evaluator bug？
- [★ Q166](answers/Q166-Wiki不引用知识库.md) — Wiki Agent 回答不引用知识库内容，从检索到生成，逐步怎么 debug？
- [★ Q167](answers/Q167-Milvus不可用.md) — Milvus `available: false`，系统状态页显示什么？如何恢复？
- [★ Q168](answers/Q168-Dashboard为空.md) — 前端 Dashboard 图表为空，可能有哪些原因（数据、API、前端渲染）？
- [★ Q169](answers/Q169-SSE断开恢复.md) — SSE 评估流中途断开，客户端如何恢复？
- [★ Q170](answers/Q170-JSON-parse错误.md) — JSON.parse 错误（如系统设置页 `/health` 返回 HTML）——根因和修复思路？

## 编码与现场设计题

- [★★ Q171](answers/Q171-extract-tool-calls.md) — 请阅读 `BaseEvaluator._extract_tool_calls`，说明它如何从 trajectory 提取工具调用对。
- [★ Q172](answers/Q172-evaluate-parallel.md) — 阅读 `evaluate_parallel()`，解释并发控制和异常处理逻辑。
- [★ Q173](answers/Q173-instrument-langgraph.md) — 阅读 `instrument_langgraph` 的核心包装逻辑，说明如何拦截节点执行。
- [★ Q174](answers/Q174-RRF手算.md) — 阅读 `hybrid_search` 的 RRF 实现，手工算两个排名的融合结果。
- [★★ Q175](answers/Q175-新增Safety维.md) — 新增第七维 Evaluator「Safety」，评估 Agent 是否输出有害内容，需要改哪些文件？
- [★ Q176](answers/Q176-效率Evaluator.md) — 实现一个 Evaluator：检测 Agent 是否在 10 步内完成任务（效率指标），如何设计？
- [★ Q177](answers/Q177-采样率上报.md) — 给 SDK 增加「采样率」配置：只有 10% 的 tool_call 上报，如何实现？
- [★ Q178](answers/Q178-gzip上报.md) — 实现 trajectory 的 gzip 压缩上报，前后端各改什么？
- [★ Q179](answers/Q179-可执行性子维.md) — 给 Planning Evaluator 增加「计划是否可执行」子维度，写出 prompt 草案和解析逻辑。
- [★ Q180](answers/Q180-评估diff-API.md) — 实现一个简单的「评估结果 diff」API：对比同一 task 两次评估的六维分数变化。
- [★★★ Q181](answers/Q181-评估流水线2.0.md) — 设计一个「评估流水线 2.0」：支持自定义 Evaluator 插件、动态权重、多 Judge 投票。
- [★ Q182](answers/Q182-联邦评估.md) — 设计跨项目的 Agent 评估联邦：多个团队各自部署 Agent，中央平台统一评估。
- [★ Q183](answers/Q183-在线评估.md) — 设计一个「在线评估」模式：Agent 运行每一步都实时打分并反馈给 Agent 自我修正。
- [★ Q184](answers/Q184-MCP封装.md) — 如何把本平台的评估能力封装成 MCP Server，供 Cursor / Claude Desktop 调用？
- [★ Q185](answers/Q185-黄金数据集.md) — 设计 Agent 评估的「黄金数据集」构建流程：采集、标注、版本、回归。

## 开放讨论与行为面

- [★★ Q186](answers/Q186-Agent趋势.md) — 2024–2026 年 Agent 领域最重要的技术趋势是什么？对本项目有什么启示？
- [★ Q187](answers/Q187-Multi-Agent评估.md) — 你怎么看 Multi-Agent 评估？本项目能否扩展到评估 Agent 团队协作？
- [★ Q188](answers/Q188-可解释与可评估.md) — Agent 的「可解释性」和「可评估性」是什么关系？
- [★ Q189](answers/Q189-RLHF-vs-prompt.md) — RLHF / DPO 训练的 Agent 和 prompt-based Agent，评估方法应该有什么不同？
- [★ Q190](answers/Q190-长上下文挑战.md) — 长上下文（128K+）对轨迹收集和评估有什么新挑战？
- [★ Q191](answers/Q191-个人负责模块.md) — 你在项目中负责哪一块？最大的技术挑战是什么？
- [★ Q192](answers/Q192-Judge人工不一致.md) — 有没有遇到过 Judge LLM 和人工评分严重不一致的情况？怎么处理的？
- [★ Q193](answers/Q193-架构重做.md) — 如果重新做这个项目，你会改变哪个架构决策？为什么？
- [★ Q194](answers/Q194-技术债.md) — 项目里有没有「看起来能跑但设计上不满意」的技术债？你怎么看待？
- [★ Q195](answers/Q195-评估vs Agent优先.md) — 从 0 到 1 搭建 Agent 系统，你会优先做评估平台还是优先做 Agent 本身？
- [★ Q196](answers/Q196-推广轨迹规范.md) — 如何向 Agent 应用团队推广轨迹上报规范？他们不愿意改代码怎么办？
- [★ Q197](answers/Q197-评估与KPI冲突.md) — 评估标准和业务 KPI 冲突时（例如评估高分但用户满意度低），如何对齐？
- [★ Q198](answers/Q198-CI-benchmark.md) — 如何在 CI/CD 里集成单调性 benchmark 作为 merge gate？
- [★ Q199](answers/Q199-领域专家协作.md) — 写 Evaluator prompt 时，如何与领域专家（法务、医疗等）协作？
- [★ Q200](answers/Q200-单一数字概括.md) — 如果产品经理要求「一个数字概括 Agent 好坏」，你怎么回应？
