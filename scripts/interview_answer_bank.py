"""Interview answer bank for docs/interview_questions_agent_dev.md (Q1-Q200)."""

from __future__ import annotations


def _a(
    reference: str,
    code_refs: list[str],
    points: list[str],
    followups: list[tuple[str, str]],
) -> dict:
    return {
        "reference": reference,
        "code_refs": code_refs,
        "points": points,
        "followups": followups,
    }


ANSWER_BANK: dict[int, dict] = {
    1: _a(
        "Agent Runtime Evaluation Platform 是一个面向 Agent 开发团队的运行时质量评估平台，它不替代被评 Agent 的运行，而是通过 SDK 或 Wiki Demo 采集 trajectory（轨迹），再经 LangGraph 编排的六维 LLM-as-Judge 评估（Planning/Tactical/Tool Use/Memory/Replan/Retrieval），输出可解释的分数与改进建议。目标用户是 Agent 工程师、平台架构师和需要量化 Agent 过程质量的团队。前端 Vue3 Dashboard 展示任务、评估报告与 Analytics；后端 FastAPI 提供 REST 与 SSE 流式评估。Wiki Agent 作为同仓库 Demo，演示 RAG + 显式 EvaluationTrace 埋点 + EVAL_AUTO_RUN 自动评估闭环。",
        ["app/main.py", "app/services/evaluation_service.py", "frontend/src/views/Dashboard.vue"],
        ["定位：过程质量评估平台，非 Agent 运行时本身", "六维评估 + overall 加权聚合（planning/tactical 各 20%）", "轨迹驱动：被评 Agent 通过 sdk/collector.py 上报", "Wiki Agent 是 Demo 也是 RAG 评估样例"],
        [
            ("和 LangSmith 的最大区别？", "本平台强调六维 rubric 与单调性 benchmark 校准，而非仅 trace 可视化。"),
            ("谁会用这个平台？", "Agent 团队在 CI 或上线前对 trajectory 做回归评估。"),
        ],
    ),
    2: _a(
        "人工标注成本高、不可扩展，且难以覆盖 Planning/Replan 等过程维度；端到端任务成功率只看结果，无法定位是规划差、工具选型错还是检索幻觉。本平台通过结构化 ActionType（14 种）和六维 Evaluator，把失败拆成可行动反馈。LLM-as-Judge 在 temperature=0 下可批量运行；monotonicity benchmark（6 条合成轨迹、容差 +0.05）用于校准分数是否随质量单调下降。SDK 零侵入接入降低集成门槛。",
        ["app/benchmarks/monotonicity.py", "app/evaluators/planning_evaluator.py", "sdk/collector.py"],
        ["过程维度人工难标、LLM Judge 可规模化", "成功率无法解释根因", "benchmark 提供回归门禁", "轨迹 schema 统一便于自动化"],
        [
            ("只用人工不行吗？", "六维 × 多子维度 × 大量 trajectory，人工无法跟上迭代速度。"),
            ("LLM Judge 可靠吗？", "用 monotonicity 与 consensus 交叉验证，并保留 feedback 供人工 spot check。"),
        ],
    ),
    3: _a(
        "平台同时评估过程与结果：Tactical/Tool Use 看每步决策与工具使用，Retrieval 看证据是否支撑回答，Planning 看计划覆盖与粒度；overall_score 在 evaluation_graph.py 加权汇总，也生成 summary 与 recommendations。Trajectory 中的 observation 与 failure 反映结果侧信号。非 RAG Agent 的 Retrieval 可能为 0，需在解读 overall 时看维度适用性。Wiki Demo 中 search 节点 record_retrieval 把检索过程显式写入轨迹供 RetrievalEvaluator 消费。",
        ["app/graphs/evaluation_graph.py", "app/evaluators/tactical_evaluator.py", "app/evaluators/retrieval_evaluator.py"],
        ["过程：plan/tool/replan/retrieval 动作链", "结果：failure、最终 observation、goal 达成隐含在 Judge prompt", "aggregate 生成 summary + recommendations", "解读 overall 需看 Agent 类型是否适用六维"],
        [
            ("能否只评结果？", "可以弱化过程维权重，但会失去定位根因的能力。"),
            ("如何平衡？", "RAG Agent 提高 retrieval 权重；工具型 Agent 提高 tool_use。"),
        ],
    ),
    4: _a(
        "六维对应 Agent 运行时关键能力：Planning（计划）、Tactical（逐步决策）、Tool Use（工具链）、Memory（上下文一致性）、Replan（失败恢复）、Retrieval（RAG 证据）。少一维会 blind spot，例如无 Replan 则无法评估连续 failure 后是否调整策略；无 Retrieval 则 RAG 质量不可见。多一维如 Safety 需新增 Evaluator 并改 aggregate WEIGHTS。ActionType 14 种与各维 Evaluator 的 _extract_* 方法一一对应，保证轨迹可解析。",
        ["app/models/action_types.py", "app/evaluators/__init__.py", "app/graphs/evaluation_graph.py"],
        ["六维覆盖 plan→act→remember→recover→ground", "权重 planning/tactical 20%，其余 15%", "缺维会导致评估盲区", "扩展需改 evaluators + schemas + aggregate"],
        [
            ("为什么不是三维？", "工具型与 RAG 型 Agent 失败模式不同，合并会损失诊断粒度。"),
            ("加 Safety 维改什么？", "新建 safety_evaluator.py、schemas、evaluation_graph 注册与权重重分配。"),
        ],
    ),
    5: _a(
        "LangSmith/Phoenix/Braintrust 侧重 trace 采集、可视化与通用 eval dataset；本平台聚焦 Agent 运行时六维 rubric、单调性 synthetic benchmark、与 Wiki Agent 端到端 RAG 评估闭环。提供 sdk/collector.py 三种 adapter（langgraph/callback/llm_proxy）和 EVAL_BATCH_SIZE 批量上报。差异在于：我们内置 REFERENCE_SCORES 校准、ReplanEvaluator 的 _detect_missed_replans 启发式、hybrid_search RRF k=60 等可落地代码而非仅 SaaS UI。",
        ["app/adapters/", "sdk/adapters/", "app/benchmarks/monotonicity_data.py"],
        ["观测平台重 trace UI；本平台重 rubric + benchmark", "内置 Wiki Demo 与 EvaluationTrace", "开源可自托管，配置 EVAL_PARALLEL 等", "六维 overall 有明确权重公式"],
        [
            ("能否对接 LangSmith？", "可 export trajectory 到本平台 schema，或写 adapter 转换 ActionType。"),
            ("优势在哪？", "领域 rubric 深度 + 单调性回归 + RAG 检索评估一体化。"),
        ],
    ),
    6: _a(
        "向产品经理可这样说：我们准备了六档「假 Agent 行为剧本」（优秀到空轨迹），跑同一套打分器，分数应该越差越低；若中等比良好还高，说明打分器有问题。容差 0.05 允许 LLM Judge 小幅波动。通过标准在 monotonicity.py 的 check_monotonicity：沿 QUALITY_ORDER  overall 非递增（允许 +0.05）。REFERENCE_SCORES 约 93.1→20.0 是历史标定参考。",
        ["app/benchmarks/monotonicity.py", "app/benchmarks/monotonicity_data.py", "app/graphs/evaluation_graph.py"],
        ["六条合成轨迹对应质量档位", "分数应单调下降，容差 +0.05", "用于 CI 门禁与 prompt 变更回归", "REFERENCE_SCORES 为标定参考非硬阈值"],
        [
            ("为什么要容差？", "LLM Judge 有随机性边界，严格单调易误报。"),
            ("失败了怎么办？", "看各维 dim_scores 哪一档逆序，定位具体 Evaluator。"),
        ],
    ),
    7: _a(
        "Wiki Agent 是同仓库的 RAG Demo 与评估样例：graph.py 中 search→respond→decide→execute，hybrid_search（Milvus+BGE+BM25+RRF）检索知识库，EvaluationTrace 显式 record_retrieval。EVAL_AUTO_RUN 在对话结束后自动 POST 评估。与评估平台放同一仓库是为零拷贝集成：trajectory schema、ActionType、RetrievalEvaluator 字段与 search 节点输出对齐，新工程师可跑通「提问→检索→回答→六维报告」全链路。它是 Demo 也是集成测试夹具。",
        ["app/wiki_agent/agent/graph.py", "app/wiki_agent/evaluation.py", "app/main.py"],
        ["Demo + 集成测试 + RAG 评估样例", "EvaluationTrace 与 sdk 格式对齐", "EVAL_AUTO_RUN 自动触发评估", "同仓避免 schema 漂移"],
        [
            ("能拆成两个 repo 吗？", "可以，但 ActionType 与 API 版本需严格同步。"),
            ("是核心产品吗？", "评估平台是核心，Wiki 是 reference implementation。"),
        ],
    ),
    8: _a(
        "LangGraph 提供 StateGraph、checkpoint、interrupt、条件边，适合 Wiki Agent 与评估 workflow 编排。evaluation_graph.py 用 StateGraph 串行六节点（注释说明并行用 evaluate_parallel + asyncio.gather）。相比 AgentExecutor 单链、AutoGen 对话式、CrewAI 角色分工，LangGraph 节点级可观测与 adapter 包装更自然：sdk/adapters/langgraph.py 的 instrument_langgraph 透明包装节点记录 NODE_EXECUTE。评估侧与 Agent 侧可共用 LangGraph 生态。",
        ["app/graphs/evaluation_graph.py", "sdk/adapters/langgraph.py", "app/wiki_agent/agent/graph.py"],
        ["StateGraph + checkpoint 适合长会话 Wiki", "instrument_langgraph 低侵入埋点", "评估图与 Agent 图分离但技术栈统一", "evaluate_parallel 生产路径用 gather 而非图并行"],
        [
            ("为什么评估图串行？", "LangGraph state merge 冲突；生产用 evaluate_parallel。"),
            ("AutoGen 呢？", "多 Agent 对话轨迹 schema 难统一，需额外 adapter。"),
        ],
    ),
    9: _a(
        "FastAPI 原生 async 与 SQLAlchemy 2.0 AsyncSession（Depends(get_db)）匹配：评估六维并行 asyncio.gather、SSE 流式 POST /evaluations/stream 需非阻塞 I/O。Pydantic schemas 在 app/models/schemas.py 与 endpoint 类型安全。Django 过重、Flask 异步生态弱。SQLite 默认 aiosqlite，可切 PostgreSQL asyncpg。lifespan 在 main.py 初始化 DB 与 Wiki bootstrap。",
        ["app/main.py", "app/db/session.py", "app/api/v1/endpoints/evaluation.py"],
        ["async 全链路：DB + LLM + SSE", "Pydantic v2 请求/响应校验", "Depends(get_db) 管理 session 生命周期", "比 Django 轻、比 Flask 现代 async 支持好"],
        [
            ("SQLite 生产够用吗？", "评估量小可；10 万/日需 PostgreSQL + 队列。"),
            ("为何 pydantic-settings？", "EVAL_PARALLEL 等环境变量 case-sensitive 统一配置。"),
        ],
    ),
    10: _a(
        "默认 DeepSeek deepseek-v4-flash 通过 ChatOpenAI + DEEPSEEK_BASE_URL，成本与速度平衡。BaseEvaluator._get_default_llm 按 DEFAULT_LLM_PROVIDER 切换 anthropic/deepseek/glm/qwen/openai，均 temperature=0。可比性：换模型应重跑 monotonicity benchmark 与 REFERENCE_SCORES 对齐；benchmark_multimodel.py 可对比不同 Judge 排序一致性；consensus.py 的 std_score 高则告警。",
        ["app/evaluators/base.py", "app/core/config.py", "app/evaluators/consensus.py"],
        ["temperature=0 保证 Judge 稳定", "多 provider 统一 BaseEvaluator 入口", "换模型需重标 benchmark", "consensus 多模型降低单模型偏见"],
        [
            ("自评偏见？", "Judge 与 Agent 同模型可能偏宽松，用不同模型或 consensus。"),
            ("如何保证可比？", "固定 prompt 版本 + monotonicity 回归 + 记录 model 版本。"),
        ],
    ),
    11: _a(
        "Wiki Agent 用 Milvus Lite 嵌入式向量库，schema 含 path/chunk/title/embedding（见 vector store 模块），配合 BAAI/bge-small-zh-v1.5（512 维）。选型理由：本地 Demo 零运维、与 hybrid_search 集成简单。Milvus 不可用时 semantic_search 降级 BM25（search_tools.py）。生产可换 Milvus 集群、pgvector 或 Qdrant，只需替换 embedding 与 store 层，RRF 融合逻辑可保留。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/wiki_agent/seed/knowledge/platform/vector-index.md", "app/graphs/evaluation_graph.py"],
        ["Milvus Lite 适合本地 Demo", "BGE 中文小模型 512 维", "不可用降级 BM25", "生产换分布式 Milvus 或 pgvector"],
        [
            ("为什么不用 Chroma？", "Milvus 生态与规模扩展更好；Lite 模式满足 Demo。"),
            ("512 维够吗？", "中文 wiki 场景够用；长文档可换 bge-large。"),
        ],
    ),
    12: _a(
        "前端 Vue3 + Vite + Element Plus + ECharts，views 含 Dashboard/Tasks/Evaluations/Analytics/Benchmark/WikiAgent/Settings。选型因团队熟悉度与 Element Plus 后台组件成熟；Agent 岗不必须深前端，但需理解 API 契约（202 异步评估、SSE progress）与 trajectory 展示。vite.config 代理 /api 到 8000。评估工程师应能读 Evaluation 详情页与 Benchmark 页源码。",
        ["frontend/src/views/Evaluations.vue", "frontend/vite.config.ts", "frontend/package.json"],
        ["Vue3 Composition API + Pinia", "ECharts 展示六维雷达与趋势", "Agent 岗重点 API/数据流非 CSS", "proxy 解决 dev CORS"],
        [
            ("必须会 Vue 吗？", "能读组件与调 API 即可，不要求写复杂 UI。"),
            ("为何不用 React？", "项目历史与 Element Plus 生态，非技术优劣绝对判断。"),
        ],
    ),
    13: _a(
        "轨迹驱动评估指：平台不 embed 运行被评 Agent，只消费外部上报的 trajectory + goal + context。优点：框架无关（sdk/collector.py、三种 adapter）、语言无关、可评生产流量副本；缺点：依赖埋点质量，缺 tool_result 等会导致 Tool Use 评估失真。EvaluationService 触发 evaluate_parallel 或 LangGraph 图；数据流：Agent→POST /api/v1/tasks→steps→POST /evaluations。",
        ["sdk/collector.py", "app/services/evaluation_service.py", "app/api/v1/endpoints/tasks.py"],
        ["解耦：评估平台 ≠ Agent runtime", "优点：通用、可 scale 采集", "缺点：garbage in garbage out", "ActionType schema 是契约核心"],
        [
            ("能否 inline 评估？", "可以 wrapper，但违背框架无关设计。"),
            ("轨迹从哪来？", "SDK adapter 或 Wiki EvaluationTrace。"),
        ],
    ),
    14: _a(
        "边界：Agent 侧负责执行与 collector.start/record/finish；平台侧负责存储 AgentTask/AgentTrajectory 与六维 Judge。数据流：start 创建 task_id→record_step 批量（EVAL_BATCH_SIZE）→finish 可选 auto_run 触发评估。context 如 key_facts 随 task 存储供 MemoryEvaluator。adapters 在 app/adapters 与 sdk/adapters 镜像，langgraph/callback/llm_proxy 三类。",
        ["app/db/models.py", "sdk/collector.py", "app/adapters/__init__.py"],
        ["Agent：执行 + 上报", "平台：持久化 + LLM Judge", "task_id 关联 trajectory 与 evaluation", "adapter 层转换框架事件→ActionType"],
        [
            ("谁拥有 schema？", "平台定义 ActionType，SDK 同步常量。"),
            ("finish 做什么？", "flush 缓冲并可 auto_run 评估。"),
        ],
    ),
    15: _a(
        "多进程/多机场景：每个 Worker 用 sdk/collector.py 独立 task_id 或共享 task_id + 线程安全锁；高并发用 _buffer_lock/_flush_lock；步骤带 step_number 与 timestamp。汇聚方式：统一 EVAL_API_BASE_URL 指向中央 FastAPI；或 sidecar collector 聚合后批量 POST。K8s 可为每个 Pod 注入 EVAL_API_BASE_URL 与 EVAL_BATCH_SIZE 环境变量。",
        ["sdk/collector.py", "app/api/v1/endpoints/tasks.py", "app/core/config.py"],
        ["SDK 线程安全单例", "中央 API 汇聚 trajectory", "step_number 排序合并", "可选消息队列异步写入"],
        [
            ("多机同一 task？", "需分布式 step_number 协调或单 writer 聚合。"),
            ("离线怎么办？", "SDK 内存缓冲，恢复网络后 flush。"),
        ],
    ),
    16: _a(
        "ActionType 14 种在 app/models/action_types.py：plan/plan_update/tool_call/tool_result/memory_write/memory_read/state_change/think/replan/failure/node_execute/tool_decision/retrieval/evidence。细分是为让各 Evaluator _extract_* 精确过滤：Planning 看 plan，Tool Use 配对 tool_call+tool_result，Retrieval 看 retrieval 的 retrieved_docs。合并会损失诊断粒度，例如 tool_call 与 tool_result 分离才能评 result_utilization。",
        ["app/models/action_types.py", "app/evaluators/base.py", "app/evaluators/tool_use_evaluator.py"],
        ["14 类型映射六维评估输入", "ALL_TYPES 集合用于校验", "SDK 与平台常量需同步", "过粗合并损害 Tool/Retrieval 评估"],
        [
            ("能只用 5 种吗？", "Memory/Replan 等维会无法评估。"),
            ("unknown 类型呢？", "validate 或 Evaluator 忽略，可能降分。"),
        ],
    ),
    17: _a(
        "tool_call 记录工具名与参数，tool_result 独立记录返回体与 latency；BaseEvaluator._extract_tool_calls 按 step 顺序配对。分离原因：异步工具、多步调用、失败时可能只有 call 无 result；Tool Use Evaluator 的 selection_quality/parameter_accuracy 看 call，result_utilization 看 Agent 是否使用 result。轨迹不完整时 utilization 低或 Judge 给保守分。",
        ["app/evaluators/base.py", "app/evaluators/tool_use_evaluator.py", "app/models/action_types.py"],
        ["call/result 分离支持异步与失败场景", "_extract_tool_calls 顺序配对", "result_utilization 依赖 result 步骤", "缺 result 是常见数据质量问题"],
        [
            ("合并成一个行吗？", "会丢失 utilization 与错误归因能力。"),
            ("Callback adapter 怎么映射？", "on_tool_end→tool_result。"),
        ],
    ),
    18: _a(
        "think 记录推理链（action_detail.thought）；node_execute 记录 LangGraph 节点进出（adapter 包装）；tool_decision 记录 LLM 选择工具的决策理由。Tactical Evaluator 评估除 plan 外动作；Replan 格式化时包含 think。Wiki graph 各节点经 instrument 或 EvaluationTrace.record_node 上报 node_execute。",
        ["app/models/action_types.py", "sdk/adapters/langgraph.py", "app/evaluators/tactical_evaluator.py"],
        ["think：显式 CoT", "node_execute：图节点边界", "tool_decision：选型理由", "Tactical 含这些非 plan 动作"],
        [
            ("think 和 plan 区别？", "plan 是结构化里程碑，think 是中间推理。"),
            ("必须录 think 吗？", "可选，但有助于 Tactical 解释性。"),
        ],
    ),
    19: _a(
        "retrieval 记录检索动作：query、retrieved_docs 列表（path/snippet/score 等）；evidence 记录最终送入 LLM 的证据池（可能裁剪/重排后）。RetrievalEvaluator 消费 retrieval；evidence 帮助评 evidence_accuracy 与幻觉。Wiki search 节点 hybrid_search 后 record_retrieval，respond 前可 record_evidence。",
        ["app/evaluators/retrieval_evaluator.py", "app/wiki_agent/evaluation.py", "app/models/action_types.py"],
        ["retrieval=召回阶段", "evidence=生成前证据池", "retrieved_docs 结构是评估输入", "两者分离定位召回 vs 引用问题"],
        [
            ("只录 evidence 够吗？", "不够，无法评 coverage/relevance 召回。"),
            ("字段必填？", "path、content/snippet、score 等见 RetrievalEvaluator prompt。"),
        ],
    ),
    20: _a(
        "第三方框架适配策略：1) 手动 sdk/collector record_*；2) 写新 adapter 映射到 ActionType；3) 离线转换 batch 导入 POST tasks/steps。Semantic Kernel 等可包装 step 回调→统一 JSON schema。关键是 tool_call/tool_result 配对与 retrieval 的 retrieved_docs 字段对齐 app/models/schemas.py TrajectoryStep。",
        ["sdk/collector.py", "app/adapters/callback.py", "app/models/schemas.py"],
        ["adapter 模式扩展框架", "手动 collector 最低成本 PoC", "schema 对齐比框架更重要", "可批量 ETL 历史 log"],
        [
            ("需要改平台吗？", "通常只加 adapter，不改 Evaluator。"),
            ("最小字段集？", "step_number、action_type、action_detail、observation。"),
        ],
    ),
    21: _a(
        "context 随 task 存储（如 key_facts 列表），MemoryEvaluator prompt 注入 context 与 trajectory 中 memory_read/write。retention 评是否记住早期事实；consistency 评是否自相矛盾。无显式 memory 动作时 Judge 从 trajectory 启发式推断。Wiki Agent 可在 context 传 session metadata。",
        ["app/evaluators/memory_evaluator.py", "app/models/schemas.py", "app/db/models.py"],
        ["key_facts 是 ground hint", "memory_read/write 显式更佳", "无动作时靠 LLM 推断，噪声更大", "context 在 evaluate API 传入"],
        [
            ("key_facts 谁维护？", "Agent 或 adapter 在 start/update 时写入。"),
            ("和 vector memory 关系？", "key_facts 是评估锚点，非替代向量库。"),
        ],
    ),
    22: _a(
        "长轨迹 token 超限策略：BaseEvaluator._format_trajectory 全文拼接；各 Evaluator 可截断 action_detail（如 [:150]）。sdk _short limit 4000；collector 批量上报也截断。改进方向：按维提取相关步骤（Tool Use 只送 tool 对）、summarize 中间 think、或 sliding window + 关键 step 保留。当前实现依赖 LLM 上下文窗口（DeepSeek 等）。",
        ["app/evaluators/base.py", "sdk/collector.py", "app/evaluators/tactical_evaluator.py"],
        ["当前全量 format，长轨迹有风险", "_short 4000 字符截断", "可按维过滤步骤降 token", "评估成本与轨迹长度线性相关"],
        [
            ("128K 够吗？", "六维并行 × 全轨迹仍贵，应预处理。"),
            ("如何采样？", "保留 plan/failure/replan/首尾 tool 对。"),
        ],
    ),
    23: _a(
        "区分多轮迭代 vs 子任务：用 task_id 粒度——一个 goal 一个 task；plan_update/replan 标记同一任务内迭代；不同 goal 应 start 新 task。step_number 单调递增；context 可含 subtask_id（自定义）。评估按单 task trajectory 独立出分，Analytics 可聚合多 task。以上结论均可在本仓库源码中验证：后端入口为 `python -m app.main`（FastAPI + LangGraph），评估编排见 `app/graphs/evaluation_graph.py`，六维 Evaluator 位于 `app/evaluators/`，轨迹 SDK 为 `sdk/collector.py`，Wiki Agent 与混合检索在 `app/wiki_agent/`，单调性基准在 `app/benchmarks/monotonicity.py`，配置项如 EVAL_PARALLEL、EVAL_BATCH_SIZE 定义于 `app/core/config.py`。",
        ["sdk/collector.py", "app/models/action_types.py", "app/api/v1/endpoints/tasks.py"],
        ["一 goal 一 task_id", "plan_update/replan 表迭代", "step_number 单 task 内有序", "避免多 goal 混一条 trajectory"],
        [
            ("多轮对话呢？", "同一 session 可同一 task，用 step 区分轮次。"),
            ("子 Agent？", "建议独立 task 或 node_execute 标注。"),
        ],
    ),
    24: _a(
        "Human-in-the-loop：轨迹应记录 interrupt、用户输入、decide 节点分支。Wiki Agent graph decide 节点判断是否需要人工确认（如知识提取）；LangGraph interrupt 暂停后恢复，checkpoint AsyncSqliteSaver 存状态。EvaluationTrace 可 record_state_change 记录 HITL 前后 diff。评估时 Tactical 可看是否因 HITL 改变路径。",
        ["app/wiki_agent/agent/graph.py", "app/models/action_types.py", "app/wiki_agent/evaluation.py"],
        ["记录 interrupt 与用户决策", "decide 节点 HITL 网关", "state_change 记录前后状态", "checkpoint 支持会话恢复"],
        [
            ("interrupt 和 failure？", "interrupt 是预期暂停，failure 是异常。"),
            ("评 HITL 质量？", "可看 replan/tactical 是否因反馈改进。"),
        ],
    ),
    25: _a(
        "围绕 两套 collector：服务端 collector 供平台内部；SDK 零依赖 httpx 供外部 Agent；逻辑应对齐 ActionType 与 batch flush 面试回答应先说业务场景，再落到 app/collectors/trajectory.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/collectors/trajectory.py", "sdk/collector.py", "app/graphs/evaluation_graph.py"],
        ["两套 collector：服务端 collector 供平台内部", "代码入口：app/collectors/trajectory.py", "app/collectors/trajectory.py 供平台内部", "sdk/collector.py 供外部零依赖", "两者 ActionType 与 batch 语义应一致"],
        [
            ("「两套 collector」最先看哪段代码？", "打开 app/collectors/trajectory.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 两套 collector？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    26: _a(
        "Q26 与 finish 与离线缓冲 相关。finish flush 剩余 steps；无 EVAL_API_BASE_URL 时纯内存；失败步骤进 _steps 缓冲 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["finish 与离线缓冲：finish flush 剩余 steps", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「finish 与离线缓冲」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 finish 与离线缓冲？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    27: _a(
        "问题「`EVAL_BATCH_SIZE` 批量上报的设计考虑是什么？太小或太大有什么影响？」考察 EVAL_BATCH_SIZE。默认 10；过小 HTTP 开销大，过大丢 batch 风险增 轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。 首要读 app/core/config.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/core/config.py", "sdk/collector.py", "app/graphs/evaluation_graph.py"],
        ["EVAL_BATCH_SIZE：默认 10", "代码入口：app/core/config.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「EVAL_BATCH_SIZE」最先看哪段代码？", "打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 EVAL_BATCH_SIZE？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    28: _a(
        "围绕 上报失败重试：当前 catch 后保留缓冲；可改进 exponential backoff 与 dead letter 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["上报失败重试：当前 catch 后保留缓冲", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「上报失败重试」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 上报失败重试？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    29: _a(
        "Q29 与 线程安全 相关。_buffer_lock/_flush_lock 单例；高并发锁竞争可 shard collector Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["线程安全：_buffer_lock/_flush_lock 单例", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「线程安全」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 线程安全？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    30: _a(
        "问题「什么是「低侵入埋点」？本项目提供了哪三种 adapter？各自适用什么场景？」考察 低侵入三种 adapter。langgraph 包装节点；callback 映射 LangChain；llm_proxy 幂等包装 LLM 轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。 首要读 app/adapters/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/adapters/", "sdk/adapters/", "app/graphs/evaluation_graph.py"],
        ["低侵入三种 adapter：langgraph 包装节点", "代码入口：app/adapters/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「低侵入三种 adapter」最先看哪段代码？", "打开 app/adapters/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 低侵入三种 adapter？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    31: _a(
        "围绕 LangGraph 包装：instrument_langgraph 装饰节点记录 NODE_EXECUTE；开销约一次 dict 序列化 面试回答应先说业务场景，再落到 sdk/adapters/langgraph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["sdk/adapters/langgraph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["LangGraph 包装：instrument_langgraph 装饰节点记录 NODE_EXECUTE", "代码入口：sdk/adapters/langgraph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「LangGraph 包装」最先看哪段代码？", "打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 LangGraph 包装？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    32: _a(
        "Q32 与 Callback 映射 相关。on_llm_start→think；on_tool_start/end→tool_call/result Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/adapters/callback.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Callback 映射：on_llm_start→think", "代码入口：app/adapters/callback.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Callback 映射」最先看哪段代码？", "打开 app/adapters/callback.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Callback 映射？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    33: _a(
        "问题「LLM Proxy adapter 的「幂等包装」是什么意思？为什么需要 idempotent？」考察 LLM Proxy 幂等。idempotent 防重复 record 同一 call_id；_seen_events 去重 轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。 首要读 app/adapters/llm_proxy.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/adapters/llm_proxy.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["LLM Proxy 幂等：idempotent 防重复 record 同一 call_id", "代码入口：app/adapters/llm_proxy.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「LLM Proxy 幂等」最先看哪段代码？", "打开 app/adapters/llm_proxy.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 LLM Proxy 幂等？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    34: _a(
        "围绕 手动 collector：get_collector().record_tool_call/record_retrieval 等 14 种 API 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["手动 collector：get_collector().record_tool_call/record_retrieval 等 14 种 API", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「手动 collector」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 手动 collector？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    35: _a(
        "Q35 与 显式 vs 自动埋点 相关。Wiki 用 EvaluationTrace 精确控制 retrieval 字段；SDK 适合通用 Agent Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/wiki_agent/evaluation.py", "sdk/collector.py", "app/graphs/evaluation_graph.py"],
        ["显式 vs 自动埋点：Wiki 用 EvaluationTrace 精确控制 retrieval 字段", "代码入口：app/wiki_agent/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「显式 vs 自动埋点」最先看哪段代码？", "打开 app/wiki_agent/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 显式 vs 自动埋点？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    36: _a(
        "问题「轨迹数据不完整（例如只有 tool_call 没有 tool_result）时，各 Evaluator 如何表现？」考察 轨迹不完整。缺 tool_result 时 utilization 低；Planning 缺 plan 得 0 轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。 首要读 app/evaluators/tool_use_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/tool_use_evaluator.py", "app/evaluators/base.py", "app/graphs/evaluation_graph.py"],
        ["轨迹不完整：缺 tool_result 时 utilization 低", "代码入口：app/evaluators/tool_use_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「轨迹不完整」最先看哪段代码？", "打开 app/evaluators/tool_use_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 轨迹不完整？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    37: _a(
        "围绕 伪造轨迹：检测 step 时间戳逆序、call/result 不匹配、异常高分与空动作 面试回答应先说业务场景，再落到 app/api/v1/endpoints/tasks.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/api/v1/endpoints/tasks.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["伪造轨迹：检测 step 时间戳逆序、call/result 不匹配、异常高分与空动作", "代码入口：app/api/v1/endpoints/tasks.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「伪造轨迹」最先看哪段代码？", "打开 app/api/v1/endpoints/tasks.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 伪造轨迹？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    38: _a(
        "Q38 与 observation 序列化 相关。非字符串 json.dumps；Judge 读 observation 文本 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["sdk/collector.py", "app/evaluators/base.py", "app/graphs/evaluation_graph.py"],
        ["observation 序列化：非字符串 json.dumps", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「observation 序列化」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 observation 序列化？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    39: _a(
        "问题「轨迹 step_number 的语义是什么？乱序上报如何处理？」考察 step_number。单调递增；乱序上报应服务端排序或拒绝 轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。 首要读 sdk/collector.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["step_number：单调递增", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「step_number」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 step_number？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    40: _a(
        "围绕 评估工作流：validate→六 eval 节点→aggregate→END；生产 evaluate_parallel 面试回答应先说业务场景，再落到 app/graphs/evaluation_graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["评估工作流：validate→六 eval 节点→aggregate→END", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「评估工作流」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 评估工作流？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    41: _a(
        "Q41 与 EvaluationState 相关。task_id/goal/trajectory/context + 六 score 字段 + overall_evaluation Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["EvaluationState：task_id/goal/trajectory/context + 六 score 字段 + overall_evaluation", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「EvaluationState」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 EvaluationState？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    42: _a(
        "问题「代码注释写「LangGraph 并行评估」，但实际图是串行的；生产环境却用 `asyncio.gather` 并行。请解释这个「双路径」设计的原因。」考察 双路径并行。图串行避 state merge；evaluate_parallel 用 asyncio.gather 71s→15s LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。 首要读 app/graphs/evaluation_graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["双路径并行：图串行避 state merge", "代码入口：app/graphs/evaluation_graph.py", "LangGraph 图串行因 state merge", "evaluate_parallel 用 asyncio.gather", "注释写明 71s→~15s"],
        [
            ("「双路径并行」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 双路径并行？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    43: _a(
        "围绕 EVAL_PARALLEL：True 走 evaluate_parallel；False 可走 StateGraph 面试回答应先说业务场景，再落到 app/core/config.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/core/config.py", "app/services/evaluation_service.py", "app/graphs/evaluation_graph.py"],
        ["EVAL_PARALLEL：True 走 evaluate_parallel", "代码入口：app/core/config.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「EVAL_PARALLEL」最先看哪段代码？", "打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 EVAL_PARALLEL？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    44: _a(
        "Q44 与 state merge 冲突 相关。并行节点写同一 state key 会覆盖；故串行边 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["state merge 冲突：并行节点写同一 state key 会覆盖", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「state merge 冲突」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 state merge 冲突？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    45: _a(
        "问题「如果未来要在 LangGraph 里实现真正的并行评估节点，你会怎么改 State 设计？」考察 真并行 State 改造。用 Annotated reducer 或子 state 分片再 aggregate LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。 首要读 app/graphs/evaluation_graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["真并行 State 改造：用 Annotated reducer 或子 state 分片再 aggregate", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「真并行 State 改造」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 真并行 State 改造？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    46: _a(
        "围绕 Wiki 节点：search 检索；respond 生成；decide HITL；execute 工具/提取 面试回答应先说业务场景，再落到 app/wiki_agent/agent/graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Wiki 节点：search 检索", "代码入口：app/wiki_agent/agent/graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Wiki 节点」最先看哪段代码？", "打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Wiki 节点？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    47: _a(
        "Q47 与 AsyncSqliteSaver 相关。checkpoint 持久化 thread_id；interrupt 后 ainvoke 恢复 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["AsyncSqliteSaver：checkpoint 持久化 thread_id", "代码入口：app/wiki_agent/agent/graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「AsyncSqliteSaver」最先看哪段代码？", "打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 AsyncSqliteSaver？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    48: _a(
        "问题「Wiki Agent 的 `decide` 节点如何判断是否需要 human-in-the-loop？」考察 decide HITL。判断 extraction 等需人工确认的分支 LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。 首要读 app/wiki_agent/agent/graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["decide HITL：判断 extraction 等需人工确认的分支", "代码入口：app/wiki_agent/agent/graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「decide HITL」最先看哪段代码？", "打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 decide HITL？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    49: _a(
        "围绕 知识提取：extraction 触发→用户 confirm→sync_manager reindex 面试回答应先说业务场景，再落到 app/wiki_agent/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["知识提取：extraction 触发→用户 confirm→sync_manager reindex", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「知识提取」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 知识提取？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    50: _a(
        "Q50 与 StateGraph vs Compiled 相关。StateGraph 构建；compile() 得可 invoke 图 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["StateGraph vs Compiled：StateGraph 构建", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「StateGraph vs Compiled」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 StateGraph vs Compiled？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    51: _a(
        "问题「条件边（conditional edge）在 Agent 里通常怎么用？本项目有没有用到？」考察 条件边。Wiki 用 conditional_edges 路由 decide 结果 LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。 首要读 app/wiki_agent/agent/graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["条件边：Wiki 用 conditional_edges 路由 decide 结果", "代码入口：app/wiki_agent/agent/graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「条件边」最先看哪段代码？", "打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 条件边？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    52: _a(
        "围绕 Subgraph：可拆 search 为 subgraph 共享 state keys 面试回答应先说业务场景，再落到 app/wiki_agent/agent/graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Subgraph：可拆 search 为 subgraph 共享 state keys", "代码入口：app/wiki_agent/agent/graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Subgraph」最先看哪段代码？", "打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Subgraph？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    53: _a(
        "Q53 与 interrupt 相关。LangGraph interrupt 协作式暂停；非 Celery 抢占 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["interrupt：LangGraph interrupt 协作式暂停", "代码入口：app/wiki_agent/agent/graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「interrupt」最先看哪段代码？", "打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 interrupt？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    54: _a(
        "问题「什么是 LLM-as-Judge？相比传统 rubric + 人工打分，优势和局限分别是什么？」考察 LLM-as-Judge。ChatPromptTemplate + temperature=0 + JSON 分数 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/base.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/base.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["LLM-as-Judge：ChatPromptTemplate + temperature=0 + JSON 分数", "代码入口：app/evaluators/base.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「LLM-as-Judge」最先看哪段代码？", "打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 LLM-as-Judge？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    55: _a(
        "围绕 temperature=0：降低 Judge 随机性；0.7 会导致同 trajectory 分波动大 面试回答应先说业务场景，再落到 app/evaluators/base.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/base.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["temperature=0：降低 Judge 随机性", "代码入口：app/evaluators/base.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「temperature=0」最先看哪段代码？", "打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 temperature=0？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    56: _a(
        "Q56 与 自评偏见 相关。Judge≠Agent 模型；或多模型 consensus Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/consensus.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["自评偏见：Judge≠Agent 模型", "代码入口：app/evaluators/consensus.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「自评偏见」最先看哪段代码？", "打开 app/evaluators/consensus.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 自评偏见？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    57: _a(
        "问题「JSON 解析失败时 fallback 到 50 分，这个策略合理吗？有没有更好的降级方案？」考察 JSON fallback 50。解析失败各子维 50；保守中性；可改 retry 或 structured output 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["JSON fallback 50：解析失败各子维 50", "代码入口：app/evaluators/planning_evaluator.py", "各 Evaluator _parse_scores fallback 50", "content.find('{') 抽取 JSON", "可改 structured output"],
        [
            ("「JSON fallback 50」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 JSON fallback 50？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    58: _a(
        "围绕 JSON 抽取漏洞：find/rfind 可能被嵌套 JSON 或 markdown 误导 面试回答应先说业务场景，再落到 app/evaluators/planning_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["JSON 抽取漏洞：find/rfind 可能被嵌套 JSON 或 markdown 误导", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「JSON 抽取漏洞」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 JSON 抽取漏洞？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    59: _a(
        "Q59 与 Structured Output 相关。可用 with_structured_output 替代手工 parse Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Structured Output：可用 with_structured_output 替代手工 parse", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Structured Output」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Structured Output？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    60: _a(
        "问题「多模型共识评估（`consensus.py`）中，`std_score` 如何解读？标准差大于多少应该告警？」考察 consensus std_score。多 Judge 标准差大说明不稳定应告警 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/consensus.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/consensus.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["consensus std_score：多 Judge 标准差大说明不稳定应告警", "代码入口：app/evaluators/consensus.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「consensus std_score」最先看哪段代码？", "打开 app/evaluators/consensus.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 consensus std_score？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    61: _a(
        "围绕 Planning prompt：输入 goal+trajectory；输出 coverage/ordering/granularity/completeness 面试回答应先说业务场景，再落到 app/evaluators/planning_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Planning prompt：输入 goal+trajectory", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Planning prompt」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Planning prompt？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    62: _a(
        "Q62 与 中英文 prompt 相关。当前英文 prompt；中文 trajectory 可能略降 Judge 质量 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["中英文 prompt：当前英文 prompt", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「中英文 prompt」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 中英文 prompt？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    63: _a(
        "问题「如何在 prompt 里注入 few-shot 示例？本项目有没有做？效果如何？」考察 few-shot。可在 prompt 加示例；本项目默认 zero-shot 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["few-shot：可在 prompt 加示例", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「few-shot」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 few-shot？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    64: _a(
        "围绕 分数 feedback 不一致：后处理校验或让 Judge 输出 reasoning chain 面试回答应先说业务场景，再落到 app/evaluators/planning_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["分数 feedback 不一致：后处理校验或让 Judge 输出 reasoning chain", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「分数 feedback 不一致」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 分数 feedback 不一致？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    65: _a(
        "Q65 与 Prompt Injection 相关。trajectory 中恶意指令；分隔符+系统 prompt  hardened Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/base.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Prompt Injection：trajectory 中恶意指令", "代码入口：app/evaluators/base.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Prompt Injection」最先看哪段代码？", "打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Prompt Injection？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    66: _a(
        "问题「评估 prompt 的版本管理策略是什么？改了 prompt 如何对比历史评估结果？」考察 prompt 版本管理。prompt 常量化+git tag；评估记录 prompt_version 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["prompt 版本管理：prompt 常量化+git tag", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「prompt 版本管理」最先看哪段代码？", "打开 app/evaluators/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 prompt 版本管理？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    67: _a(
        "围绕 token 成本：六维各一次 LLM；轨迹长度主导；并行不省 token 面试回答应先说业务场景，再落到 app/evaluators/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["token 成本：六维各一次 LLM", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「token 成本」最先看哪段代码？", "打开 app/evaluators/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 token 成本？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    68: _a(
        "Q68 与 成本追踪 相关。Dashboard 估算；需接 LLM usage callback 才精确 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["frontend/src/views/Analytics.vue", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["成本追踪：Dashboard 估算", "代码入口：frontend/src/views/Analytics.vue", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「成本追踪」最先看哪段代码？", "打开 frontend/src/views/Analytics.vue，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 成本追踪？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    69: _a(
        "问题「六维并行评估从 71s 降到 ~15s，瓶颈在哪里？还能继续优化吗？」考察 并行优化。瓶颈是 6 次 LLM RTT；gather 已并行；可缓存或 mini Judge 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/graphs/evaluation_graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["并行优化：瓶颈是 6 次 LLM RTT", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「并行优化」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 并行优化？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    70: _a(
        "围绕 评估缓存：key=hash(trajectory+prompt_version+model) 面试回答应先说业务场景，再落到 app/services/evaluation_service.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/services/evaluation_service.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["评估缓存：key=hash(trajectory+prompt_version+model)", "代码入口：app/services/evaluation_service.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「评估缓存」最先看哪段代码？", "打开 app/services/evaluation_service.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 评估缓存？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    71: _a(
        "Q71 与 部分维度复用 相关。只重跑变更维 Evaluator+aggregate Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["部分维度复用：只重跑变更维 Evaluator+aggregate", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「部分维度复用」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 部分维度复用？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    72: _a(
        "问题「Planning 的四个子维度（coverage、ordering、granularity、completeness）分别评估什么？」考察 Planning 四子维。coverage/ordering/granularity/completeness 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Planning 四子维：coverage/ordering/granularity/completeness", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Planning 四子维」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Planning 四子维？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    73: _a(
        "围绕 Planning 权重：0.3/0.2/0.2/0.3；可用 benchmark 网格搜索 面试回答应先说业务场景，再落到 app/evaluators/planning_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Planning 权重：0.3/0.2/0.2/0.3", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Planning 权重」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Planning 权重？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    74: _a(
        "Q74 与 无 plan 零分 相关。无 plan/plan_update 返回 0；严格但可改 N/A Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["无 plan 零分：无 plan/plan_update 返回 0", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「无 plan 零分」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 无 plan 零分？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    75: _a(
        "问题「「计划粒度（granularity）」如何在 prompt 里定义？过细和过粗的计划如何区分？」考察 granularity。prompt 定义里程碑粒度适中；过细过粗 Judge 描述 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["granularity：prompt 定义里程碑粒度适中", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「granularity」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 granularity？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    76: _a(
        "围绕 Tactical 排除 plan：plan 已在 Planning 维；Tactical 评执行步 relevance/efficiency/correctness 面试回答应先说业务场景，再落到 app/evaluators/tactical_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/tactical_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Tactical 排除 plan：plan 已在 Planning 维", "代码入口：app/evaluators/tactical_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Tactical 排除 plan」最先看哪段代码？", "打开 app/evaluators/tactical_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Tactical 排除 plan？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    77: _a(
        "Q77 与 Tactical 例子 相关。高分：每步靠近 goal；低分：冗余 search Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/tactical_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Tactical 例子：高分：每步靠近 goal", "代码入口：app/evaluators/tactical_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Tactical 例子」最先看哪段代码？", "打开 app/evaluators/tactical_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Tactical 例子？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    78: _a(
        "问题「如果 Agent 做了正确决策但工具返回错误导致失败，Tactical 应该怎么打分？」考察 工具错 Tactical。决策正确但工具失败：correctness 考虑决策非环境 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/tactical_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/tactical_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["工具错 Tactical：决策正确但工具失败：correctness 考虑决策非环境", "代码入口：app/evaluators/tactical_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「工具错 Tactical」最先看哪段代码？", "打开 app/evaluators/tactical_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 工具错 Tactical？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    79: _a(
        "围绕 Tool Use 三子维：selection_quality/parameter_accuracy/result_utilization 面试回答应先说业务场景，再落到 app/evaluators/tool_use_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/tool_use_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Tool Use 三子维：selection_quality/parameter_accuracy/result_utilization", "代码入口：app/evaluators/tool_use_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Tool Use 三子维」最先看哪段代码？", "打开 app/evaluators/tool_use_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Tool Use 三子维？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    80: _a(
        "Q80 与 参数 JSON 错误 相关。parameter_accuracy 低；selection 可能仍高 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/tool_use_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["参数 JSON 错误：parameter_accuracy 低", "代码入口：app/evaluators/tool_use_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「参数 JSON 错误」最先看哪段代码？", "打开 app/evaluators/tool_use_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 参数 JSON 错误？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    81: _a(
        "问题「工具返回结果被 Agent 忽略（result_utilization 低），在实际 Agent 里常见吗？如何检测？」考察 result_utilization。常见忽略 tool_result；检测 action 是否引用 result 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/tool_use_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/tool_use_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["result_utilization：常见忽略 tool_result", "代码入口：app/evaluators/tool_use_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「result_utilization」最先看哪段代码？", "打开 app/evaluators/tool_use_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 result_utilization？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    82: _a(
        "围绕 Memory 三子维：retention/relevance/consistency 面试回答应先说业务场景，再落到 app/evaluators/memory_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/memory_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Memory 三子维：retention/relevance/consistency", "代码入口：app/evaluators/memory_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Memory 三子维」最先看哪段代码？", "打开 app/evaluators/memory_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Memory 三子维？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    83: _a(
        "Q83 与 key_facts 可靠性 相关。显式 key_facts 优于纯推断 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/memory_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["key_facts 可靠性：显式 key_facts 优于纯推断", "代码入口：app/evaluators/memory_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「key_facts 可靠性」最先看哪段代码？", "打开 app/evaluators/memory_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 key_facts 可靠性？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    84: _a(
        "问题「Agent 没有显式 memory_read/write 动作时，Memory Evaluator 如何工作？」考察 无 memory 动作。LLM 从 trajectory 推断记忆行为 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/memory_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/memory_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["无 memory 动作：LLM 从 trajectory 推断记忆行为", "代码入口：app/evaluators/memory_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「无 memory 动作」最先看哪段代码？", "打开 app/evaluators/memory_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 无 memory 动作？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    85: _a(
        "围绕 长短期记忆：可拆 Evaluator；当前合并 面试回答应先说业务场景，再落到 app/evaluators/memory_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/memory_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["长短期记忆：可拆 Evaluator", "代码入口：app/evaluators/memory_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「长短期记忆」最先看哪段代码？", "打开 app/evaluators/memory_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 长短期记忆？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    86: _a(
        "Q86 与 无 replan 满分 相关。无 replan 且无 missed_opportunities 返回 100 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/replan_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["无 replan 满分：无 replan 且无 missed_opportunities 返回 100", "代码入口：app/evaluators/replan_evaluator.py", "无 replan 且无 missed→100 分", "_detect_missed_replans 连续 5 failure", "有 missed 才走 LLM Judge"],
        [
            ("「无 replan 满分」最先看哪段代码？", "打开 app/evaluators/replan_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 无 replan 满分？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    87: _a(
        "问题「trigger_appropriateness 如何判断「该重规划却没重规划」？」考察 trigger_appropriateness。_detect_missed_replans 检连续 failure 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/replan_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/replan_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["trigger_appropriateness：_detect_missed_replans 检连续 failure", "代码入口：app/evaluators/replan_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「trigger_appropriateness」最先看哪段代码？", "打开 app/evaluators/replan_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 trigger_appropriateness？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    88: _a(
        "围绕 failure 与 replan：连续 5 failure 无 replan 记 missed 面试回答应先说业务场景，再落到 app/evaluators/replan_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/replan_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["failure 与 replan：连续 5 failure 无 replan 记 missed", "代码入口：app/evaluators/replan_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「failure 与 replan」最先看哪段代码？", "打开 app/evaluators/replan_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 failure 与 replan？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    89: _a(
        "Q89 与 Replan 缺口 相关。缺 plan diff 量化；可对标 industry replanning rubric Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/replan_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Replan 缺口：缺 plan diff 量化", "代码入口：app/evaluators/replan_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Replan 缺口」最先看哪段代码？", "打开 app/evaluators/replan_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Replan 缺口？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    90: _a(
        "问题「Retrieval 的三个子维度（relevance、evidence_accuracy、coverage）如何对应 RAG 质量？」考察 Retrieval 三子维。relevance/evidence_accuracy/coverage 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/retrieval_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/retrieval_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Retrieval 三子维：relevance/evidence_accuracy/coverage", "代码入口：app/evaluators/retrieval_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Retrieval 三子维」最先看哪段代码？", "打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Retrieval 三子维？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    91: _a(
        "围绕 retrieved_docs：需 path、content/snippet、score 等 面试回答应先说业务场景，再落到 app/evaluators/retrieval_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/retrieval_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["retrieved_docs：需 path、content/snippet、score 等", "代码入口：app/evaluators/retrieval_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「retrieved_docs」最先看哪段代码？", "打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 retrieved_docs？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    92: _a(
        "Q92 与 无 retrieval 零分 相关。非 RAG Agent 该维 0；overall 仍加权需解读 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/retrieval_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["无 retrieval 零分：非 RAG Agent 该维 0", "代码入口：app/evaluators/retrieval_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「无 retrieval 零分」最先看哪段代码？", "打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 无 retrieval 零分？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    93: _a(
        "问题「如何评估「幻觉」：Agent 用了检索结果但歪曲了原文？」考察 幻觉评估。evidence_accuracy 对比 retrieved_docs 与 Agent 陈述 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/retrieval_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/retrieval_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["幻觉评估：evidence_accuracy 对比 retrieved_docs 与 Agent 陈述", "代码入口：app/evaluators/retrieval_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「幻觉评估」最先看哪段代码？", "打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 幻觉评估？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    94: _a(
        "围绕 coverage 低：召回窄；建议扩大 query 或 hybrid top_k 面试回答应先说业务场景，再落到 app/evaluators/retrieval_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/retrieval_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["coverage 低：召回窄", "代码入口：app/evaluators/retrieval_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「coverage 低」最先看哪段代码？", "打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 coverage 低？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    95: _a(
        "Q95 与 overall 权重 相关。planning/tactical 0.2；其余 0.15 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["overall 权重：planning/tactical 0.2", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「overall 权重」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 overall 权重？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    96: _a(
        "问题「为什么要先算各维子维度加权，再算六维 overall 加权？能否端到端一个分数？」考察 两级加权。子维加权→维 overall→六维 overall；可解释性强 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/graphs/evaluation_graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["两级加权：子维加权→维 overall→六维 overall", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「两级加权」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 两级加权？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    97: _a(
        "围绕 单维异常 0：一维 0 最多拉低 15-20%；应标记 failed dim 面试回答应先说业务场景，再落到 app/graphs/evaluation_graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["单维异常 0：一维 0 最多拉低 15-20%", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「单维异常 0」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 单维异常 0？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    98: _a(
        "Q98 与 分块 500/50 相关。chunk size 500 overlap 50 平衡语义与粒度 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["分块 500/50：chunk size 500 overlap 50 平衡语义与粒度", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「分块 500/50」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 分块 500/50？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    99: _a(
        "问题「分块时如何处理标题层级？标题是否拼进 chunk 文本？」考察 标题层级。标题拼入 chunk 保留结构 Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。 首要读 app/wiki_agent/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["标题层级：标题拼入 chunk 保留结构", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「标题层级」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 标题层级？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    100: _a(
        "围绕 代码块分块：避免从 markdown 中间切断 fenced code 面试回答应先说业务场景，再落到 app/wiki_agent/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["代码块分块：避免从 markdown 中间切断 fenced code", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「代码块分块」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 代码块分块？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    101: _a(
        "Q101 与 增量索引 相关。CRUD 触发增量；全量 rebuild 兜底 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/wiki_agent/sync_manager.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["增量索引：CRUD 触发增量", "代码入口：app/wiki_agent/sync_manager.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「增量索引」最先看哪段代码？", "打开 app/wiki_agent/sync_manager.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 增量索引？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    102: _a(
        "问题「为什么选 `BAAI/bge-small-zh-v1.5`？512 维够用吗？」考察 BGE 选型。bge-small-zh-v1.5 512维中文 wiki 轻量 Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。 首要读 app/wiki_agent/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["BGE 选型：bge-small-zh-v1.5 512维中文 wiki 轻量", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「BGE 选型」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 BGE 选型？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    103: _a(
        "围绕 零向量降级：embedding 失败返回零向量；semantic 失效靠 BM25 面试回答应先说业务场景，再落到 app/wiki_agent/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["零向量降级：embedding 失败返回零向量", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「零向量降级」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 零向量降级？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    104: _a(
        "Q104 与 Milvus schema 相关。path/chunk/title/embedding 字段 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Milvus schema：path/chunk/title/embedding 字段", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Milvus schema」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Milvus schema？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    105: _a(
        "问题「Milvus 不可用时 semantic search 降级为 BM25——用户体验上如何感知？」考察 Milvus 降级 BM25。available false 时仅 keyword_search Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。 首要读 app/wiki_agent/agent/tools/search_tools.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Milvus 降级 BM25：available false 时仅 keyword_search", "代码入口：app/wiki_agent/agent/tools/search_tools.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Milvus 降级 BM25」最先看哪段代码？", "打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Milvus 降级 BM25？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    106: _a(
        "围绕 RRF k=60：score+=1/(k+rank+1)；k=60 平滑秩次 面试回答应先说业务场景，再落到 app/wiki_agent/agent/tools/search_tools.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["RRF k=60：score+=1/(k+rank+1)", "代码入口：app/wiki_agent/agent/tools/search_tools.py", "RRF: 1/(k+rank+1)", "k=60 在 search_tools.py", "semantic 与 BM25 各取 limit*2"],
        [
            ("「RRF k=60」最先看哪段代码？", "打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 RRF k=60？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    107: _a(
        "Q107 与 RRF vs 加权 相关。RRF 无分数标定问题；不同量纲融合 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["RRF vs 加权：RRF 无分数标定问题", "代码入口：app/wiki_agent/agent/tools/search_tools.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「RRF vs 加权」最先看哪段代码？", "打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 RRF vs 加权？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    108: _a(
        "问题「jieba 分词 + 停用词对 BM25 的影响？英文内容检索效果如何？」考察 jieba BM25。中文分词；英文靠 BM25 仍可用但弱于 semantic Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。 首要读 app/wiki_agent/agent/tools/search_tools.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["jieba BM25：中文分词", "代码入口：app/wiki_agent/agent/tools/search_tools.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「jieba BM25」最先看哪段代码？", "打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 jieba BM25？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    109: _a(
        "围绕 path 去重：同 path 保留最高分 chunk 防刷屏 面试回答应先说业务场景，再落到 app/wiki_agent/agent/tools/search_tools.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["path 去重：同 path 保留最高分 chunk 防刷屏", "代码入口：app/wiki_agent/agent/tools/search_tools.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「path 去重」最先看哪段代码？", "打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 path 去重？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    110: _a(
        "Q110 与 top_k 相关。limit*2 召回再 RRF 截断 limit Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["top_k：limit*2 召回再 RRF 截断 limit", "代码入口：app/wiki_agent/agent/tools/search_tools.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「top_k」最先看哪段代码？", "打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 top_k？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    111: _a(
        "问题「Wiki Agent search 节点如何 `record_retrieval`？数据如何流到 RetrievalEvaluator？」考察 record_retrieval。search 后写入 retrieval 步骤 Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。 首要读 app/wiki_agent/evaluation.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/wiki_agent/evaluation.py", "app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py"],
        ["record_retrieval：search 后写入 retrieval 步骤", "代码入口：app/wiki_agent/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「record_retrieval」最先看哪段代码？", "打开 app/wiki_agent/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 record_retrieval？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    112: _a(
        "围绕 检索好生成差：测例：高 relevance 低 evidence_accuracy 面试回答应先说业务场景，再落到 app/evaluators/retrieval_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/retrieval_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["检索好生成差：测例：高 relevance 低 evidence_accuracy", "代码入口：app/evaluators/retrieval_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「检索好生成差」最先看哪段代码？", "打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 检索好生成差？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    113: _a(
        "Q113 与 RAG ground truth 相关。合成轨迹+人工 spot；无大规模标注集 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/benchmarks/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["RAG ground truth：合成轨迹+人工 spot", "代码入口：app/benchmarks/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「RAG ground truth」最先看哪段代码？", "打开 app/benchmarks/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 RAG ground truth？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    114: _a(
        "问题「Wiki Agent 的完整请求链路：用户提问 → 检索 → 生成 → 可选知识提取，请逐步说明。」考察 Wiki 链路。提问→hybrid_search→LLM respond→可选 extract Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。 首要读 app/wiki_agent/agent/graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Wiki 链路：提问→hybrid_search→LLM respond→可选 extract", "代码入口：app/wiki_agent/agent/graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Wiki 链路」最先看哪段代码？", "打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Wiki 链路？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    115: _a(
        "围绕 Chat SSE：SSE 流式 token；事件 type 含 message/done/error 面试回答应先说业务场景，再落到 app/wiki_agent/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Chat SSE：SSE 流式 token", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Chat SSE」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Chat SSE？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    116: _a(
        "Q116 与 SYSTEM_PROMPT 相关。约束引用来源、拒答无证据 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/wiki_agent/agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["SYSTEM_PROMPT：约束引用来源、拒答无证据", "代码入口：app/wiki_agent/agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「SYSTEM_PROMPT」最先看哪段代码？", "打开 app/wiki_agent/agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 SYSTEM_PROMPT？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    117: _a(
        "问题「知识自动提取（auto extraction）的触发条件和确认流程是什么？」考察 自动提取。条件触发+用户 confirm Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。 首要读 app/wiki_agent/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["自动提取：条件触发+用户 confirm", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「自动提取」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 自动提取？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    118: _a(
        "围绕 reject 提取：状态标记 rejected 防重复 prompt 面试回答应先说业务场景，再落到 app/wiki_agent/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["reject 提取：状态标记 rejected 防重复 prompt", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「reject 提取」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 reject 提取？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    119: _a(
        "Q119 与 CRUD 索引 相关。删页清理 Milvus+BM25 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/wiki_agent/sync_manager.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["CRUD 索引：删页清理 Milvus+BM25", "代码入口：app/wiki_agent/sync_manager.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「CRUD 索引」最先看哪段代码？", "打开 app/wiki_agent/sync_manager.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 CRUD 索引？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    120: _a(
        "问题「Git 风格的 history / rollback 是如何实现的？回滚后索引如何恢复？」考察 history rollback。版本链+回滚触发 reindex Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。 首要读 app/wiki_agent/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["history rollback：版本链+回滚触发 reindex", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「history rollback」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 history rollback？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    121: _a(
        "围绕 EvaluationTrace 事件：plan/tool/retrieval 等与 SDK 同 schema 面试回答应先说业务场景，再落到 app/wiki_agent/evaluation.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/evaluation.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["EvaluationTrace 事件：plan/tool/retrieval 等与 SDK 同 schema", "代码入口：app/wiki_agent/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「EvaluationTrace 事件」最先看哪段代码？", "打开 app/wiki_agent/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 EvaluationTrace 事件？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    122: _a(
        "Q122 与 EVAL_AUTO_RUN 相关。finish 后异步 POST /evaluations Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/evaluation.py", "app/core/config.py", "app/graphs/evaluation_graph.py"],
        ["EVAL_AUTO_RUN：finish 后异步 POST /evaluations", "代码入口：app/wiki_agent/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「EVAL_AUTO_RUN」最先看哪段代码？", "打开 app/wiki_agent/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 EVAL_AUTO_RUN？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    123: _a(
        "问题「「零侵入 SDK 接入」的具体含义是什么？开发者最少需要改几行代码？」考察 零侵入 SDK。import adapter 包装即可；最少数行 sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。 首要读 sdk/collector.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["sdk/collector.py", "sdk/adapters/langgraph.py", "app/graphs/evaluation_graph.py"],
        ["零侵入 SDK：import adapter 包装即可", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「零侵入 SDK」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 零侵入 SDK？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    124: _a(
        "围绕 adapter 路径：镜像关系；SDK 可独立 pip 面试回答应先说业务场景，再落到 app/adapters/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/adapters/", "sdk/adapters/", "app/graphs/evaluation_graph.py"],
        ["adapter 路径：镜像关系", "代码入口：app/adapters/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「adapter 路径」最先看哪段代码？", "打开 app/adapters/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 adapter 路径？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    125: _a(
        "Q125 与 LangGraph 兼容 相关。compile/ainvoke API 不变 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["sdk/adapters/langgraph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["LangGraph 兼容：compile/ainvoke API 不变", "代码入口：sdk/adapters/langgraph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「LangGraph 兼容」最先看哪段代码？", "打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 LangGraph 兼容？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    126: _a(
        "问题「同步节点函数和异步节点函数，adapter 如何处理？」考察 同步异步节点。分别包装 sync/async 函数 sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。 首要读 sdk/adapters/langgraph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["sdk/adapters/langgraph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["同步异步节点：分别包装 sync/async 函数", "代码入口：sdk/adapters/langgraph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「同步异步节点」最先看哪段代码？", "打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 同步异步节点？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    127: _a(
        "围绕 state diff 截断：_short 限制 state 快照大小 面试回答应先说业务场景，再落到 sdk/adapters/langgraph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["sdk/adapters/langgraph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["state diff 截断：_short 限制 state 快照大小", "代码入口：sdk/adapters/langgraph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「state diff 截断」最先看哪段代码？", "打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 state diff 截断？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    128: _a(
        "Q128 与 SDK 独立安装 相关。httpx 依赖；不依赖 app 包 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["sdk/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["SDK 独立安装：httpx 依赖", "代码入口：sdk/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「SDK 独立安装」最先看哪段代码？", "打开 sdk/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 SDK 独立安装？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    129: _a(
        "问题「如果 Agent 使用非 LangChain 技术栈（纯 OpenAI API、Anthropic SDK），如何接入？」考察 非 LangChain 接入。手动 record 或 HTTP API sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。 首要读 sdk/collector.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["非 LangChain 接入：手动 record 或 HTTP API", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「非 LangChain 接入」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 非 LangChain 接入？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    130: _a(
        "围绕 ActionType 同步：两处常量需 CI diff 检查 面试回答应先说业务场景，再落到 app/models/action_types.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/models/action_types.py", "sdk/collector.py", "app/graphs/evaluation_graph.py"],
        ["ActionType 同步：两处常量需 CI diff 检查", "代码入口：app/models/action_types.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「ActionType 同步」最先看哪段代码？", "打开 app/models/action_types.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 ActionType 同步？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    131: _a(
        "Q131 与 单调性基准 相关。6 trajectory QUALITY_ORDER 非递增+0.05 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/benchmarks/monotonicity.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["单调性基准：6 trajectory QUALITY_ORDER 非递增+0.05", "代码入口：app/benchmarks/monotonicity.py", "六条 QUALITY_ORDER 轨迹", "check_monotonicity +0.05", "REFERENCE_SCORES 标定参考"],
        [
            ("「单调性基准」最先看哪段代码？", "打开 app/benchmarks/monotonicity.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 单调性基准？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    132: _a(
        "问题「六条合成轨迹（优秀/良好/中等/差/对抗/空）是如何构造的？参考分 93.1→20.0 怎么来的？」考察 合成轨迹。REFERENCE_SCORES 93.1→20.0 标定 monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。 首要读 app/benchmarks/monotonicity_data.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/benchmarks/monotonicity_data.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["合成轨迹：REFERENCE_SCORES 93.1→20.0 标定", "代码入口：app/benchmarks/monotonicity_data.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「合成轨迹」最先看哪段代码？", "打开 app/benchmarks/monotonicity_data.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 合成轨迹？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    133: _a(
        "围绕 容差 0.05：check_monotonicity 允许小幅上跳 面试回答应先说业务场景，再落到 app/benchmarks/monotonicity.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/benchmarks/monotonicity.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["容差 0.05：check_monotonicity 允许小幅上跳", "代码入口：app/benchmarks/monotonicity.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「容差 0.05」最先看哪段代码？", "打开 app/benchmarks/monotonicity.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 容差 0.05？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    134: _a(
        "Q134 与 逆序定位 相关。对比 dim_scores 找逆序维 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/benchmarks/monotonicity.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["逆序定位：对比 dim_scores 找逆序维", "代码入口：app/benchmarks/monotonicity.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「逆序定位」最先看哪段代码？", "打开 app/benchmarks/monotonicity.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 逆序定位？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    135: _a(
        "问题「`eval_evaluator_accuracy.py` 的好/坏场景对比测试是如何设计的？」考察 eval_evaluator_accuracy。好/坏场景对比断言 monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。 首要读 tests/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["tests/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["eval_evaluator_accuracy：好/坏场景对比断言", "代码入口：tests/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「eval_evaluator_accuracy」最先看哪段代码？", "打开 tests/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 eval_evaluator_accuracy？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    136: _a(
        "围绕 真实轨迹补充：脱敏业务 trace 加入 ALL_TRAJECTORIES 面试回答应先说业务场景，再落到 app/benchmarks/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/benchmarks/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["真实轨迹补充：脱敏业务 trace 加入 ALL_TRAJECTORIES", "代码入口：app/benchmarks/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「真实轨迹补充」最先看哪段代码？", "打开 app/benchmarks/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 真实轨迹补充？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    137: _a(
        "Q137 与 评估准确率 相关。人工 vs Judge agreement Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/consensus.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["评估准确率：人工 vs Judge agreement", "代码入口：app/evaluators/consensus.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「评估准确率」最先看哪段代码？", "打开 app/evaluators/consensus.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 评估准确率？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    138: _a(
        "问题「多模型 benchmark（`benchmark_multimodel.py`）结论是什么？不同 Judge 模型排序是否一致？」考察 benchmark_multimodel。多 Judge 模型排序一致性 monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。 首要读 app/benchmarks/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/benchmarks/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["benchmark_multimodel：多 Judge 模型排序一致性", "代码入口：app/benchmarks/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「benchmark_multimodel」最先看哪段代码？", "打开 app/benchmarks/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 benchmark_multimodel？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    139: _a(
        "围绕 POST evaluations 202：异步；客户端轮询或 SSE 面试回答应先说业务场景，再落到 app/api/v1/endpoints/evaluation.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/api/v1/endpoints/evaluation.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["POST evaluations 202：异步", "代码入口：app/api/v1/endpoints/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「POST evaluations 202」最先看哪段代码？", "打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 POST evaluations 202？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    140: _a(
        "Q140 与 SSE 格式 相关。progress/result/done 事件 JSON Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/api/v1/endpoints/evaluation.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["SSE 格式：progress/result/done 事件 JSON", "代码入口：app/api/v1/endpoints/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「SSE 格式」最先看哪段代码？", "打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 SSE 格式？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    141: _a(
        "问题「已完成评估的 SSE replay 为什么不重跑 LLM？如何实现？」考察 SSE replay。已完成评估重放缓存结果不重跑 LLM FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。 首要读 app/api/v1/endpoints/evaluation.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/api/v1/endpoints/evaluation.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["SSE replay：已完成评估重放缓存结果不重跑 LLM", "代码入口：app/api/v1/endpoints/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「SSE replay」最先看哪段代码？", "打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 SSE replay？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    142: _a(
        "围绕 任务状态机：PENDING→RUNNING→COMPLETED 面试回答应先说业务场景，再落到 app/db/models.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/db/models.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["任务状态机：PENDING→RUNNING→COMPLETED", "代码入口：app/db/models.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「任务状态机」最先看哪段代码？", "打开 app/db/models.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 任务状态机？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    143: _a(
        "Q143 与 PENDING vs RUNNING 相关。推轨迹仍 PENDING；评估开始 RUNNING Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/services/evaluation_service.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["PENDING vs RUNNING：推轨迹仍 PENDING", "代码入口：app/services/evaluation_service.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「PENDING vs RUNNING」最先看哪段代码？", "打开 app/services/evaluation_service.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 PENDING vs RUNNING？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    144: _a(
        "问题「SQLAlchemy 2.0 async session 的生命周期如何管理？`Depends(get_db)` 模式？」考察 async session。Depends get_db yield session FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。 首要读 app/db/session.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/db/session.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["async session：Depends get_db yield session", "代码入口：app/db/session.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「async session」最先看哪段代码？", "打开 app/db/session.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 async session？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    145: _a(
        "围绕 SQLite PostgreSQL：DATABASE_URL 切换；Alembic 可选 面试回答应先说业务场景，再落到 app/core/config.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/core/config.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["SQLite PostgreSQL：DATABASE_URL 切换", "代码入口：app/core/config.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「SQLite PostgreSQL」最先看哪段代码？", "打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 SQLite PostgreSQL？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    146: _a(
        "Q146 与 AUTH_ENABLED 相关。API Key header；health 跳过 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/core/config.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["AUTH_ENABLED：API Key header", "代码入口：app/core/config.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「AUTH_ENABLED」最先看哪段代码？", "打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 AUTH_ENABLED？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    147: _a(
        "问题「`/health` 和 `/api/v1/system/health` 为什么有两个？前端开发环境 proxy 如何配置？」考察 双 health。/health 与 /api/v1/system/health；proxy FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。 首要读 app/main.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/main.py", "frontend/vite.config.ts", "app/graphs/evaluation_graph.py"],
        ["双 health：/health 与 /api/v1/system/health", "代码入口：app/main.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「双 health」最先看哪段代码？", "打开 app/main.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 双 health？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    148: _a(
        "围绕 10万评估/日：队列+worker+PG+缓存 Judge 面试回答应先说业务场景，再落到 app/services/evaluation_service.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/services/evaluation_service.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["10万评估/日：队列+worker+PG+缓存 Judge", "代码入口：app/services/evaluation_service.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「10万评估/日」最先看哪段代码？", "打开 app/services/evaluation_service.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 10万评估/日？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    149: _a(
        "Q149 与 Celery vs BackgroundTasks 相关。BackgroundTasks 进程内；大规模需 Redis 队列 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/services/evaluation_service.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Celery vs BackgroundTasks：BackgroundTasks 进程内", "代码入口：app/services/evaluation_service.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Celery vs BackgroundTasks」最先看哪段代码？", "打开 app/services/evaluation_service.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Celery vs BackgroundTasks？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    150: _a(
        "问题「多租户（workspace）隔离如何实现？`workspace_endpoints.py` 的设计意图？」考察 多租户 workspace。workspace 隔离 task/eval 当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。 首要读 app/api/v1/endpoints/workspace_endpoints.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/api/v1/endpoints/workspace_endpoints.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["多租户 workspace：workspace 隔离 task/eval", "代码入口：app/api/v1/endpoints/workspace_endpoints.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「多租户 workspace」最先看哪段代码？", "打开 app/api/v1/endpoints/workspace_endpoints.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 多租户 workspace？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    151: _a(
        "围绕 评估版本化：存 prompt_version model_version 面试回答应先说业务场景，再落到 app/db/models.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/db/models.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["评估版本化：存 prompt_version model_version", "代码入口：app/db/models.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「评估版本化」最先看哪段代码？", "打开 app/db/models.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 评估版本化？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    152: _a(
        "Q152 与 A/B prompt 相关。双 prompt 并行 evaluate 对比 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["A/B prompt：双 prompt 并行 evaluate 对比", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「A/B prompt」最先看哪段代码？", "打开 app/evaluators/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 A/B prompt？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    153: _a(
        "问题「评估中途 Judge LLM 超时或 429 限流，如何重试？会不会部分维度成功、部分失败？」考察 Judge 429。gather 部分失败得 0；应 retry 与 circuit breaker 当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。 首要读 app/evaluators/base.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/base.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Judge 429：gather 部分失败得 0", "代码入口：app/evaluators/base.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Judge 429」最先看哪段代码？", "打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Judge 429？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    154: _a(
        "围绕 DB 一致性：评估失败 mark FAILED；transaction 面试回答应先说业务场景，再落到 app/services/evaluation_service.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/services/evaluation_service.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["DB 一致性：评估失败 mark FAILED", "代码入口：app/services/evaluation_service.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「DB 一致性」最先看哪段代码？", "打开 app/services/evaluation_service.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 DB 一致性？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    155: _a(
        "Q155 与 双索引不一致 相关。定期 reconcile Milvus vs BM25 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/wiki_agent/sync_manager.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["双索引不一致：定期 reconcile Milvus vs BM25", "代码入口：app/wiki_agent/sync_manager.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「双索引不一致」最先看哪段代码？", "打开 app/wiki_agent/sync_manager.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 双索引不一致？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    156: _a(
        "问题「如何实现评估任务的幂等性（同一 task_id 重复触发评估）？」考察 评估幂等。同 task_id 重复触发 upsert 或 reject 当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。 首要读 app/services/evaluation_service.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/services/evaluation_service.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["评估幂等：同 task_id 重复触发 upsert 或 reject", "代码入口：app/services/evaluation_service.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「评估幂等」最先看哪段代码？", "打开 app/services/evaluation_service.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 评估幂等？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    157: _a(
        "围绕 PII 脱敏：_short+regex Redact；存储加密 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["PII 脱敏：_short+regex Redact", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「PII 脱敏」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 PII 脱敏？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    158: _a(
        "Q158 与 Wiki XSS 相关。Markdown sanitize；path 校验 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/wiki_agent/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Wiki XSS：Markdown sanitize", "代码入口：app/wiki_agent/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Wiki XSS」最先看哪段代码？", "打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Wiki XSS？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    159: _a(
        "问题「`EVAL_WEBHOOK_URL` 通知机制的安全考虑？」考察 WEBHOOK 安全。EVAL_WEBHOOK_URL HMAC 签名 当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。 首要读 app/core/config.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/core/config.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["WEBHOOK 安全：EVAL_WEBHOOK_URL HMAC 签名", "代码入口：app/core/config.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「WEBHOOK 安全」最先看哪段代码？", "打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 WEBHOOK 安全？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    160: _a(
        "围绕 平台观测：ENABLE_TRACING OTEL 面试回答应先说业务场景，再落到 app/core/config.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/core/config.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["平台观测：ENABLE_TRACING OTEL", "代码入口：app/core/config.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「平台观测」最先看哪段代码？", "打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 平台观测？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    161: _a(
        "Q161 与 Judge 监控 相关。记录 latency/token metrics Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/base.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Judge 监控：记录 latency/token metrics", "代码入口：app/evaluators/base.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Judge 监控」最先看哪段代码？", "打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Judge 监控？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    162: _a(
        "问题「用户反馈「Planning 分数总是很低」，你的排查步骤是什么？」考察 Planning 低分排查。查是否有 plan 动作；prompt feedback 排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Planning 低分排查：查是否有 plan 动作", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Planning 低分排查」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Planning 低分排查？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    163: _a(
        "围绕 overall 高分争议：展示六维雷达；业务 KPI 对齐 面试回答应先说业务场景，再落到 app/graphs/evaluation_graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["overall 高分争议：展示六维雷达", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「overall 高分争议」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 overall 高分争议？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    164: _a(
        "Q164 与 Retrieval 0 分 相关。最可能未 record_retrieval Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/retrieval_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Retrieval 0 分：最可能未 record_retrieval", "代码入口：app/evaluators/retrieval_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Retrieval 0 分」最先看哪段代码？", "打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Retrieval 0 分？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    165: _a(
        "问题「单调性 benchmark 失败，如何定位是数据问题还是 Evaluator bug？」考察 benchmark 失败。数据 vs Evaluator：看 dim 逆序 排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。 首要读 app/benchmarks/monotonicity.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/benchmarks/monotonicity.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["benchmark 失败：数据 vs Evaluator：看 dim 逆序", "代码入口：app/benchmarks/monotonicity.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「benchmark 失败」最先看哪段代码？", "打开 app/benchmarks/monotonicity.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 benchmark 失败？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    166: _a(
        "围绕 Wiki 不引用 KB：查 hybrid 结果与 SYSTEM_PROMPT 面试回答应先说业务场景，再落到 app/wiki_agent/agent/graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/agent/graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Wiki 不引用 KB：查 hybrid 结果与 SYSTEM_PROMPT", "代码入口：app/wiki_agent/agent/graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Wiki 不引用 KB」最先看哪段代码？", "打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Wiki 不引用 KB？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    167: _a(
        "Q167 与 Milvus unavailable 相关。状态页 BM25-only；恢复 Milvus Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Milvus unavailable：状态页 BM25-only", "代码入口：app/wiki_agent/agent/tools/search_tools.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Milvus unavailable」最先看哪段代码？", "打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Milvus unavailable？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    168: _a(
        "问题「前端 Dashboard 图表为空，可能有哪些原因（数据、API、前端渲染）？」考察 Dashboard 空。无数据/API 失败/渲染错误 排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。 首要读 frontend/src/views/Dashboard.vue，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["frontend/src/views/Dashboard.vue", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Dashboard 空：无数据/API 失败/渲染错误", "代码入口：frontend/src/views/Dashboard.vue", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「Dashboard 空」最先看哪段代码？", "打开 frontend/src/views/Dashboard.vue，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 Dashboard 空？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    169: _a(
        "围绕 SSE 断开：客户端重连+Last-Event-ID 或轮询 面试回答应先说业务场景，再落到 app/api/v1/endpoints/evaluation.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/api/v1/endpoints/evaluation.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["SSE 断开：客户端重连+Last-Event-ID 或轮询", "代码入口：app/api/v1/endpoints/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「SSE 断开」最先看哪段代码？", "打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 SSE 断开？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    170: _a(
        "Q170 与 JSON parse HTML 相关。proxy 错配返回 HTML；fix vite proxy Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["frontend/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["JSON parse HTML：proxy 错配返回 HTML", "代码入口：frontend/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「JSON parse HTML」最先看哪段代码？", "打开 frontend/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 JSON parse HTML？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    171: _a(
        "问题「请阅读 `BaseEvaluator._extract_tool_calls`，说明它如何从 trajectory 提取工具调用对。」考察 _extract_tool_calls。顺序扫描 tool_call 配 tool_result 改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。 首要读 app/evaluators/base.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/base.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["_extract_tool_calls：顺序扫描 tool_call 配 tool_result", "代码入口：app/evaluators/base.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「_extract_tool_calls」最先看哪段代码？", "打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 _extract_tool_calls？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    172: _a(
        "围绕 evaluate_parallel：asyncio.gather 六 Evaluator 异常返 0 面试回答应先说业务场景，再落到 app/graphs/evaluation_graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["evaluate_parallel：asyncio.gather 六 Evaluator 异常返 0", "代码入口：app/graphs/evaluation_graph.py", "asyncio.gather 六任务", "单维异常返回 overall 0", "EvaluationService 生产默认路径"],
        [
            ("「evaluate_parallel」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 evaluate_parallel？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    173: _a(
        "Q173 与 instrument_langgraph 相关。wrap 节点函数 record 前后 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["sdk/adapters/langgraph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["instrument_langgraph：wrap 节点函数 record 前后", "代码入口：sdk/adapters/langgraph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「instrument_langgraph」最先看哪段代码？", "打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 instrument_langgraph？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    174: _a(
        "问题「阅读 `hybrid_search` 的 RRF 实现，手工算两个排名的融合结果。」考察 RRF 手算。两列表 rank 代入 1/(60+r+1) 相加 改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。 首要读 app/wiki_agent/agent/tools/search_tools.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/wiki_agent/agent/tools/search_tools.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["RRF 手算：两列表 rank 代入 1/(60+r+1) 相加", "代码入口：app/wiki_agent/agent/tools/search_tools.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「RRF 手算」最先看哪段代码？", "打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 RRF 手算？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    175: _a(
        "围绕 新增 Safety 维：新 evaluator+schema+权重 面试回答应先说业务场景，再落到 app/evaluators/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/", "app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py"],
        ["新增 Safety 维：新 evaluator+schema+权重", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「新增 Safety 维」最先看哪段代码？", "打开 app/evaluators/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 新增 Safety 维？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    176: _a(
        "Q176 与 效率 Evaluator 相关。统计 step 数与 goal 达成 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/base.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["效率 Evaluator：统计 step 数与 goal 达成", "代码入口：app/evaluators/base.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「效率 Evaluator」最先看哪段代码？", "打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 效率 Evaluator？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    177: _a(
        "问题「给 SDK 增加「采样率」配置：只有 10% 的 tool_call 上报，如何实现？」考察 采样率。random.sample 在 record 前 改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。 首要读 sdk/collector.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["采样率：random.sample 在 record 前", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「采样率」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 采样率？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    178: _a(
        "围绕 gzip 上报：Content-Encoding gzip 解压 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["sdk/collector.py", "app/api/", "app/graphs/evaluation_graph.py"],
        ["gzip 上报：Content-Encoding gzip 解压", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「gzip 上报」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 gzip 上报？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    179: _a(
        "Q179 与 可执行性子维 相关。prompt 加 executability 字段 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/planning_evaluator.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["可执行性子维：prompt 加 executability 字段", "代码入口：app/evaluators/planning_evaluator.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「可执行性子维」最先看哪段代码？", "打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 可执行性子维？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    180: _a(
        "问题「实现一个简单的「评估结果 diff」API：对比同一 task 两次评估的六维分数变化。」考察 评估 diff API。对比两次 Evaluation ORM 记录 改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。 首要读 app/api/v1/endpoints/evaluation.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/api/v1/endpoints/evaluation.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["评估 diff API：对比两次 Evaluation ORM 记录", "代码入口：app/api/v1/endpoints/evaluation.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「评估 diff API」最先看哪段代码？", "打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 评估 diff API？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    181: _a(
        "围绕 评估 2.0：插件 registry+动态权重+consensus 面试回答应先说业务场景，再落到 app/evaluators/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/evaluators/", "app/graphs/", "app/graphs/evaluation_graph.py"],
        ["评估 2.0：插件 registry+动态权重+consensus", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「评估 2.0」最先看哪段代码？", "打开 app/evaluators/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 评估 2.0？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    182: _a(
        "Q182 与 联邦评估 相关。多部署上报中央 EVAL_API Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["联邦评估：多部署上报中央 EVAL_API", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「联邦评估」最先看哪段代码？", "打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 联邦评估？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    183: _a(
        "问题「设计一个「在线评估」模式：Agent 运行每一步都实时打分并反馈给 Agent 自我修正。」考察 在线评估。每步 mini Judge SSE 反馈 改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。 首要读 app/graphs/evaluation_graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["在线评估：每步 mini Judge SSE 反馈", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「在线评估」最先看哪段代码？", "打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 在线评估？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    184: _a(
        "围绕 MCP Server：暴露 evaluate/tools MCP 面试回答应先说业务场景，再落到 app/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["MCP Server：暴露 evaluate/tools MCP", "代码入口：app/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「MCP Server」最先看哪段代码？", "打开 app/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 MCP Server？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    185: _a(
        "Q185 与 黄金数据集 相关。采集→标注→版本→CI 回归 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/benchmarks/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["黄金数据集：采集→标注→版本→CI 回归", "代码入口：app/benchmarks/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("「黄金数据集」最先看哪段代码？", "打开 app/benchmarks/，再对照 app/graphs/evaluation_graph.py 的数据流。"),
            ("Demo 里如何验证 黄金数据集？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
            ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
        ],
    ),
    186: _a(
        "问题「2024–2026 年 Agent 领域最重要的技术趋势是什么？对本项目有什么启示？」考察 Agent 趋势。Multi-agent、long context、eval-driven dev 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Agent 趋势：Multi-agent、long context、eval-driven dev", "代码入口：app/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    187: _a(
        "围绕 Multi-Agent 评估：扩展 trajectory 含 agent_id 面试回答应先说业务场景，再落到 app/evaluators/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Multi-Agent 评估：扩展 trajectory 含 agent_id", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/evaluators/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    188: _a(
        "Q188 与 可解释与可评估 相关。可评估需结构化 trace；可解释靠 feedback Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        ["app/evaluators/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["可解释与可评估：可评估需结构化 trace", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/evaluators/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    189: _a(
        "问题「RLHF / DPO 训练的 Agent 和 prompt-based Agent，评估方法应该有什么不同？」考察 RLHF vs prompt。RLHF Agent 评 policy 一致性 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/evaluators/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/evaluators/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["RLHF vs prompt：RLHF Agent 评 policy 一致性", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/evaluators/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    190: _a(
        "围绕 长上下文：截断与摘要策略 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["sdk/collector.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["长上下文：截断与摘要策略", "代码入口：sdk/collector.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 sdk/collector.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    191: _a(
        "Q191 与 个人负责 相关。结合候选人实际；参考 evaluators/graph/sdk Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        ["app/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["个人负责：结合候选人实际", "代码入口：app/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    192: _a(
        "问题「有没有遇到过 Judge LLM 和人工评分严重不一致的情况？怎么处理的？」考察 Judge 人工不一致。校准 prompt 或换 Judge 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/evaluators/consensus.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/evaluators/consensus.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["Judge 人工不一致：校准 prompt 或换 Judge", "代码入口：app/evaluators/consensus.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/evaluators/consensus.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    193: _a(
        "围绕 架构重做：可能早做 plugin evaluators 面试回答应先说业务场景，再落到 app/graphs/evaluation_graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["架构重做：可能早做 plugin evaluators", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/graphs/evaluation_graph.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    194: _a(
        "Q194 与 技术债 相关。图串行注释 vs 并行 gather 双路径 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["技术债：图串行注释 vs 并行 gather 双路径", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/graphs/evaluation_graph.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    195: _a(
        "问题「从 0 到 1 搭建 Agent 系统，你会优先做评估平台还是优先做 Agent 本身？」考察 评估 vs Agent 优先。MVP 可 Demo Agent；规模化需 eval 先行 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["评估 vs Agent 优先：MVP 可 Demo Agent", "代码入口：app/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    196: _a(
        "围绕 推广轨迹规范：文档+adapter 降低摩擦 面试回答应先说业务场景，再落到 docs/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["docs/", "sdk/", "app/graphs/evaluation_graph.py"],
        ["推广轨迹规范：文档+adapter 降低摩擦", "代码入口：docs/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 docs/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    197: _a(
        "Q197 与 评估与 KPI 相关。联合 dashboard 业务指标 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["评估与 KPI：联合 dashboard 业务指标", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/graphs/evaluation_graph.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    198: _a(
        "问题「如何在 CI/CD 里集成单调性 benchmark 作为 merge gate？」考察 CI benchmark。pytest merge gate 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/benchmarks/monotonicity.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/benchmarks/monotonicity.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["CI benchmark：pytest merge gate", "代码入口：app/benchmarks/monotonicity.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/benchmarks/monotonicity.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    199: _a(
        "围绕 领域专家：共建 rubric few-shot 面试回答应先说业务场景，再落到 app/evaluators/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/evaluators/", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["领域专家：共建 rubric few-shot", "代码入口：app/evaluators/", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/evaluators/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
    200: _a(
        "Q200 与 单一数字 相关。overall+六维雷达+recommendations 而非单分 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        ["app/graphs/evaluation_graph.py", "app/graphs/evaluation_graph.py", "app/evaluators/base.py"],
        ["单一数字：overall+六维雷达+recommendations 而非单分", "代码入口：app/graphs/evaluation_graph.py", "与六维 LLM-as-Judge 评估链路相关", "轨迹 schema 见 app/models/action_types.py"],
        [
            ("如何结合本项目回答开放题？", "引用 app/graphs/evaluation_graph.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ],
    ),
}
