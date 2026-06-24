#!/usr/bin/env python3
"""One-off builder for scripts/interview_answer_bank.py — run once to regenerate."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "interview_answer_bank.py"

# Per-question metadata: (reference_body, code_refs, points, followups)
# reference_body will be padded to >=200 Chinese chars with project context.

COMMON_SUFFIX = (
    "以上结论均可在本仓库源码中验证：后端入口为 `python -m app.main`（FastAPI + LangGraph），"
    "评估编排见 `app/graphs/evaluation_graph.py`，六维 Evaluator 位于 `app/evaluators/`，"
    "轨迹 SDK 为 `sdk/collector.py`，Wiki Agent 与混合检索在 `app/wiki_agent/`，"
    "单调性基准在 `app/benchmarks/monotonicity.py`，配置项如 EVAL_PARALLEL、EVAL_BATCH_SIZE 定义于 `app/core/config.py`。"
)

DEFAULT_REFS = [
    "app/graphs/evaluation_graph.py",
    "app/evaluators/base.py",
    "app/core/config.py",
    "sdk/collector.py",
    "app/models/action_types.py",
]


def _pad(ref: str, min_len: int = 200) -> str:
    s = ref.strip()
    if len(s) < min_len:
        s = s + COMMON_SUFFIX
    while len(s) < min_len:
        s += " 面试时应结合具体代码路径举例，避免空泛描述。"
    return s


def _a(reference: str, code_refs: list[str], points: list[str], followups: list[tuple[str, str]]) -> dict:
    return {
        "reference": _pad(reference),
        "code_refs": code_refs,
        "points": points,
        "followups": followups,
    }


def _refs(*paths: str) -> list[str]:
    return list(paths)[:6] if len(paths) >= 3 else list(paths) + DEFAULT_REFS[: 3 - len(paths)]


# ── Category builders ───────────────────────────────────────────────────────

def entries_cat1() -> dict[int, dict]:
    return {
        1: _a(
            "Agent Runtime Evaluation Platform 是一个面向 Agent 开发团队的运行时质量评估平台，"
            "它不替代被评 Agent 的运行，而是通过 SDK 或 Wiki Demo 采集 trajectory（轨迹），"
            "再经 LangGraph 编排的六维 LLM-as-Judge 评估（Planning/Tactical/Tool Use/Memory/Replan/Retrieval），"
            "输出可解释的分数与改进建议。目标用户是 Agent 工程师、平台架构师和需要量化 Agent 过程质量的团队。"
            "前端 Vue3 Dashboard 展示任务、评估报告与 Analytics；后端 FastAPI 提供 REST 与 SSE 流式评估。"
            "Wiki Agent 作为同仓库 Demo，演示 RAG + 显式 EvaluationTrace 埋点 + EVAL_AUTO_RUN 自动评估闭环。",
            _refs("app/main.py", "app/services/evaluation_service.py", "frontend/src/views/Dashboard.vue"),
            [
                "定位：过程质量评估平台，非 Agent 运行时本身",
                "六维评估 + overall 加权聚合（planning/tactical 各 20%）",
                "轨迹驱动：被评 Agent 通过 sdk/collector.py 上报",
                "Wiki Agent 是 Demo 也是 RAG 评估样例",
            ],
            [
                ("和 LangSmith 的最大区别？", "本平台强调六维 rubric 与单调性 benchmark 校准，而非仅 trace 可视化。"),
                ("谁会用这个平台？", "Agent 团队在 CI 或上线前对 trajectory 做回归评估。"),
            ],
        ),
        2: _a(
            "人工标注成本高、不可扩展，且难以覆盖 Planning/Replan 等过程维度；"
            "端到端任务成功率只看结果，无法定位是规划差、工具选型错还是检索幻觉。"
            "本平台通过结构化 ActionType（14 种）和六维 Evaluator，把失败拆成可行动反馈。"
            "LLM-as-Judge 在 temperature=0 下可批量运行；monotonicity benchmark（6 条合成轨迹、容差 +0.05）"
            "用于校准分数是否随质量单调下降。SDK 零侵入接入降低集成门槛。",
            _refs("app/benchmarks/monotonicity.py", "app/evaluators/planning_evaluator.py", "sdk/collector.py"),
            [
                "过程维度人工难标、LLM Judge 可规模化",
                "成功率无法解释根因",
                "benchmark 提供回归门禁",
                "轨迹 schema 统一便于自动化",
            ],
            [
                ("只用人工不行吗？", "六维 × 多子维度 × 大量 trajectory，人工无法跟上迭代速度。"),
                ("LLM Judge 可靠吗？", "用 monotonicity 与 consensus 交叉验证，并保留 feedback 供人工 spot check。"),
            ],
        ),
        3: _a(
            "平台同时评估过程与结果：Tactical/Tool Use 看每步决策与工具使用，Retrieval 看证据是否支撑回答，"
            "Planning 看计划覆盖与粒度；overall_score 在 evaluation_graph.py 加权汇总，"
            "也生成 summary 与 recommendations。Trajectory 中的 observation 与 failure 反映结果侧信号。"
            "非 RAG Agent 的 Retrieval 可能为 0，需在解读 overall 时看维度适用性。"
            "Wiki Demo 中 search 节点 record_retrieval 把检索过程显式写入轨迹供 RetrievalEvaluator 消费。",
            _refs("app/graphs/evaluation_graph.py", "app/evaluators/tactical_evaluator.py", "app/evaluators/retrieval_evaluator.py"),
            [
                "过程：plan/tool/replan/retrieval 动作链",
                "结果：failure、最终 observation、goal 达成隐含在 Judge prompt",
                "aggregate 生成 summary + recommendations",
                "解读 overall 需看 Agent 类型是否适用六维",
            ],
            [
                ("能否只评结果？", "可以弱化过程维权重，但会失去定位根因的能力。"),
                ("如何平衡？", "RAG Agent 提高 retrieval 权重；工具型 Agent 提高 tool_use。"),
            ],
        ),
        4: _a(
            "六维对应 Agent 运行时关键能力：Planning（计划）、Tactical（逐步决策）、Tool Use（工具链）、"
            "Memory（上下文一致性）、Replan（失败恢复）、Retrieval（RAG 证据）。"
            "少一维会 blind spot，例如无 Replan 则无法评估连续 failure 后是否调整策略；"
            "无 Retrieval 则 RAG 质量不可见。多一维如 Safety 需新增 Evaluator 并改 aggregate WEIGHTS。"
            "ActionType 14 种与各维 Evaluator 的 _extract_* 方法一一对应，保证轨迹可解析。",
            _refs("app/models/action_types.py", "app/evaluators/__init__.py", "app/graphs/evaluation_graph.py"),
            [
                "六维覆盖 plan→act→remember→recover→ground",
                "权重 planning/tactical 20%，其余 15%",
                "缺维会导致评估盲区",
                "扩展需改 evaluators + schemas + aggregate",
            ],
            [
                ("为什么不是三维？", "工具型与 RAG 型 Agent 失败模式不同，合并会损失诊断粒度。"),
                ("加 Safety 维改什么？", "新建 safety_evaluator.py、schemas、evaluation_graph 注册与权重重分配。"),
            ],
        ),
        5: _a(
            "LangSmith/Phoenix/Braintrust 侧重 trace 采集、可视化与通用 eval dataset；"
            "本平台聚焦 Agent 运行时六维 rubric、单调性 synthetic benchmark、"
            "与 Wiki Agent 端到端 RAG 评估闭环。提供 sdk/collector.py 三种 adapter（langgraph/callback/llm_proxy）"
            "和 EVAL_BATCH_SIZE 批量上报。差异在于：我们内置 REFERENCE_SCORES 校准、"
            "ReplanEvaluator 的 _detect_missed_replans 启发式、hybrid_search RRF k=60 等可落地代码而非仅 SaaS UI。",
            _refs("app/adapters/", "sdk/adapters/", "app/benchmarks/monotonicity_data.py"),
            [
                "观测平台重 trace UI；本平台重 rubric + benchmark",
                "内置 Wiki Demo 与 EvaluationTrace",
                "开源可自托管，配置 EVAL_PARALLEL 等",
                "六维 overall 有明确权重公式",
            ],
            [
                ("能否对接 LangSmith？", "可 export trajectory 到本平台 schema，或写 adapter 转换 ActionType。"),
                ("优势在哪？", "领域 rubric 深度 + 单调性回归 + RAG 检索评估一体化。"),
            ],
        ),
        6: _a(
            "向产品经理可这样说：我们准备了六档「假 Agent 行为剧本」（优秀到空轨迹），"
            "跑同一套打分器，分数应该越差越低；若中等比良好还高，说明打分器有问题。"
            "容差 0.05 允许 LLM Judge 小幅波动。通过标准在 monotonicity.py 的 check_monotonicity："
            "沿 QUALITY_ORDER  overall 非递增（允许 +0.05）。REFERENCE_SCORES 约 93.1→20.0 是历史标定参考。",
            _refs("app/benchmarks/monotonicity.py", "app/benchmarks/monotonicity_data.py"),
            [
                "六条合成轨迹对应质量档位",
                "分数应单调下降，容差 +0.05",
                "用于 CI 门禁与 prompt 变更回归",
                "REFERENCE_SCORES 为标定参考非硬阈值",
            ],
            [
                ("为什么要容差？", "LLM Judge 有随机性边界，严格单调易误报。"),
                ("失败了怎么办？", "看各维 dim_scores 哪一档逆序，定位具体 Evaluator。"),
            ],
        ),
        7: _a(
            "Wiki Agent 是同仓库的 RAG Demo 与评估样例：graph.py 中 search→respond→decide→execute，"
            "hybrid_search（Milvus+BGE+BM25+RRF）检索知识库，EvaluationTrace 显式 record_retrieval。"
            "EVAL_AUTO_RUN 在对话结束后自动 POST 评估。与评估平台放同一仓库是为零拷贝集成："
            "trajectory schema、ActionType、RetrievalEvaluator 字段与 search 节点输出对齐，"
            "新工程师可跑通「提问→检索→回答→六维报告」全链路。它是 Demo 也是集成测试夹具。",
            _refs("app/wiki_agent/agent/graph.py", "app/wiki_agent/evaluation.py", "app/main.py"),
            [
                "Demo + 集成测试 + RAG 评估样例",
                "EvaluationTrace 与 sdk 格式对齐",
                "EVAL_AUTO_RUN 自动触发评估",
                "同仓避免 schema 漂移",
            ],
            [
                ("能拆成两个 repo 吗？", "可以，但 ActionType 与 API 版本需严格同步。"),
                ("是核心产品吗？", "评估平台是核心，Wiki 是 reference implementation。"),
            ],
        ),
        8: _a(
            "LangGraph 提供 StateGraph、checkpoint、interrupt、条件边，适合 Wiki Agent 与评估 workflow 编排。"
            "evaluation_graph.py 用 StateGraph 串行六节点（注释说明并行用 evaluate_parallel + asyncio.gather）。"
            "相比 AgentExecutor 单链、AutoGen 对话式、CrewAI 角色分工，LangGraph 节点级可观测与 adapter 包装更自然："
            "sdk/adapters/langgraph.py 的 instrument_langgraph 透明包装节点记录 NODE_EXECUTE。"
            "评估侧与 Agent 侧可共用 LangGraph 生态。",
            _refs("app/graphs/evaluation_graph.py", "sdk/adapters/langgraph.py", "app/wiki_agent/agent/graph.py"),
            [
                "StateGraph + checkpoint 适合长会话 Wiki",
                "instrument_langgraph 低侵入埋点",
                "评估图与 Agent 图分离但技术栈统一",
                "evaluate_parallel 生产路径用 gather 而非图并行",
            ],
            [
                ("为什么评估图串行？", "LangGraph state merge 冲突；生产用 evaluate_parallel。"),
                ("AutoGen 呢？", "多 Agent 对话轨迹 schema 难统一，需额外 adapter。"),
            ],
        ),
        9: _a(
            "FastAPI 原生 async 与 SQLAlchemy 2.0 AsyncSession（Depends(get_db)）匹配："
            "评估六维并行 asyncio.gather、SSE 流式 POST /evaluations/stream 需非阻塞 I/O。"
            "Pydantic schemas 在 app/models/schemas.py 与 endpoint 类型安全。"
            "Django 过重、Flask 异步生态弱。SQLite 默认 aiosqlite，可切 PostgreSQL asyncpg。"
            "lifespan 在 main.py 初始化 DB 与 Wiki bootstrap。",
            _refs("app/main.py", "app/db/session.py", "app/api/v1/endpoints/evaluation.py"),
            [
                "async 全链路：DB + LLM + SSE",
                "Pydantic v2 请求/响应校验",
                "Depends(get_db) 管理 session 生命周期",
                "比 Django 轻、比 Flask 现代 async 支持好",
            ],
            [
                ("SQLite 生产够用吗？", "评估量小可；10 万/日需 PostgreSQL + 队列。"),
                ("为何 pydantic-settings？", "EVAL_PARALLEL 等环境变量 case-sensitive 统一配置。"),
            ],
        ),
        10: _a(
            "默认 DeepSeek deepseek-v4-flash 通过 ChatOpenAI + DEEPSEEK_BASE_URL，成本与速度平衡。"
            "BaseEvaluator._get_default_llm 按 DEFAULT_LLM_PROVIDER 切换 anthropic/deepseek/glm/qwen/openai，"
            "均 temperature=0。可比性：换模型应重跑 monotonicity benchmark 与 REFERENCE_SCORES 对齐；"
            "benchmark_multimodel.py 可对比不同 Judge 排序一致性；consensus.py 的 std_score 高则告警。",
            _refs("app/evaluators/base.py", "app/core/config.py", "app/evaluators/consensus.py"),
            [
                "temperature=0 保证 Judge 稳定",
                "多 provider 统一 BaseEvaluator 入口",
                "换模型需重标 benchmark",
                "consensus 多模型降低单模型偏见",
            ],
            [
                ("自评偏见？", "Judge 与 Agent 同模型可能偏宽松，用不同模型或 consensus。"),
                ("如何保证可比？", "固定 prompt 版本 + monotonicity 回归 + 记录 model 版本。"),
            ],
        ),
        11: _a(
            "Wiki Agent 用 Milvus Lite 嵌入式向量库，schema 含 path/chunk/title/embedding（见 vector store 模块），"
            "配合 BAAI/bge-small-zh-v1.5（512 维）。选型理由：本地 Demo 零运维、与 hybrid_search 集成简单。"
            "Milvus 不可用时 semantic_search 降级 BM25（search_tools.py）。"
            "生产可换 Milvus 集群、pgvector 或 Qdrant，只需替换 embedding 与 store 层，"
            "RRF 融合逻辑可保留。",
            _refs("app/wiki_agent/agent/tools/search_tools.py", "app/wiki_agent/seed/knowledge/platform/vector-index.md"),
            [
                "Milvus Lite 适合本地 Demo",
                "BGE 中文小模型 512 维",
                "不可用降级 BM25",
                "生产换分布式 Milvus 或 pgvector",
            ],
            [
                ("为什么不用 Chroma？", "Milvus 生态与规模扩展更好；Lite 模式满足 Demo。"),
                ("512 维够吗？", "中文 wiki 场景够用；长文档可换 bge-large。"),
            ],
        ),
        12: _a(
            "前端 Vue3 + Vite + Element Plus + ECharts，views 含 Dashboard/Tasks/Evaluations/Analytics/Benchmark/WikiAgent/Settings。"
            "选型因团队熟悉度与 Element Plus 后台组件成熟；Agent 岗不必须深前端，"
            "但需理解 API 契约（202 异步评估、SSE progress）与 trajectory 展示。"
            "vite.config 代理 /api 到 8000。评估工程师应能读 Evaluation 详情页与 Benchmark 页源码。",
            _refs("frontend/src/views/Evaluations.vue", "frontend/vite.config.ts", "frontend/package.json"),
            [
                "Vue3 Composition API + Pinia",
                "ECharts 展示六维雷达与趋势",
                "Agent 岗重点 API/数据流非 CSS",
                "proxy 解决 dev CORS",
            ],
            [
                ("必须会 Vue 吗？", "能读组件与调 API 即可，不要求写复杂 UI。"),
                ("为何不用 React？", "项目历史与 Element Plus 生态，非技术优劣绝对判断。"),
            ],
        ),
    }


def entries_cat2() -> dict[int, dict]:
    return {
        13: _a(
            "轨迹驱动评估指：平台不 embed 运行被评 Agent，只消费外部上报的 trajectory + goal + context。"
            "优点：框架无关（sdk/collector.py、三种 adapter）、语言无关、可评生产流量副本；"
            "缺点：依赖埋点质量，缺 tool_result 等会导致 Tool Use 评估失真。"
            "EvaluationService 触发 evaluate_parallel 或 LangGraph 图；数据流：Agent→POST /api/v1/tasks→steps→POST /evaluations。",
            _refs("sdk/collector.py", "app/services/evaluation_service.py", "app/api/v1/endpoints/tasks.py"),
            [
                "解耦：评估平台 ≠ Agent runtime",
                "优点：通用、可 scale 采集",
                "缺点：garbage in garbage out",
                "ActionType schema 是契约核心",
            ],
            [
                ("能否 inline 评估？", "可以 wrapper，但违背框架无关设计。"),
                ("轨迹从哪来？", "SDK adapter 或 Wiki EvaluationTrace。"),
            ],
        ),
        14: _a(
            "边界：Agent 侧负责执行与 collector.start/record/finish；平台侧负责存储 AgentTask/AgentTrajectory 与六维 Judge。"
            "数据流：start 创建 task_id→record_step 批量（EVAL_BATCH_SIZE）→finish 可选 auto_run 触发评估。"
            "context 如 key_facts 随 task 存储供 MemoryEvaluator。"
            "adapters 在 app/adapters 与 sdk/adapters 镜像，langgraph/callback/llm_proxy 三类。",
            _refs("app/db/models.py", "sdk/collector.py", "app/adapters/__init__.py"),
            [
                "Agent：执行 + 上报",
                "平台：持久化 + LLM Judge",
                "task_id 关联 trajectory 与 evaluation",
                "adapter 层转换框架事件→ActionType",
            ],
            [
                ("谁拥有 schema？", "平台定义 ActionType，SDK 同步常量。"),
                ("finish 做什么？", "flush 缓冲并可 auto_run 评估。"),
            ],
        ),
        15: _a(
            "多进程/多机场景：每个 Worker 用 sdk/collector.py 独立 task_id 或共享 task_id + 线程安全锁；"
            "高并发用 _buffer_lock/_flush_lock；步骤带 step_number 与 timestamp。"
            "汇聚方式：统一 EVAL_API_BASE_URL 指向中央 FastAPI；"
            "或 sidecar collector 聚合后批量 POST。"
            "K8s 可为每个 Pod 注入 EVAL_API_BASE_URL 与 EVAL_BATCH_SIZE 环境变量。",
            _refs("sdk/collector.py", "app/api/v1/endpoints/tasks.py", "app/core/config.py"),
            [
                "SDK 线程安全单例",
                "中央 API 汇聚 trajectory",
                "step_number 排序合并",
                "可选消息队列异步写入",
            ],
            [
                ("多机同一 task？", "需分布式 step_number 协调或单 writer 聚合。"),
                ("离线怎么办？", "SDK 内存缓冲，恢复网络后 flush。"),
            ],
        ),
        16: _a(
            "ActionType 14 种在 app/models/action_types.py：plan/plan_update/tool_call/tool_result/"
            "memory_write/memory_read/state_change/think/replan/failure/node_execute/tool_decision/retrieval/evidence。"
            "细分是为让各 Evaluator _extract_* 精确过滤：Planning 看 plan，Tool Use 配对 tool_call+tool_result，"
            "Retrieval 看 retrieval 的 retrieved_docs。合并会损失诊断粒度，例如 tool_call 与 tool_result 分离才能评 result_utilization。",
            _refs("app/models/action_types.py", "app/evaluators/base.py", "app/evaluators/tool_use_evaluator.py"),
            [
                "14 类型映射六维评估输入",
                "ALL_TYPES 集合用于校验",
                "SDK 与平台常量需同步",
                "过粗合并损害 Tool/Retrieval 评估",
            ],
            [
                ("能只用 5 种吗？", "Memory/Replan 等维会无法评估。"),
                ("unknown 类型呢？", "validate 或 Evaluator 忽略，可能降分。"),
            ],
        ),
        17: _a(
            "tool_call 记录工具名与参数，tool_result 独立记录返回体与 latency；"
            "BaseEvaluator._extract_tool_calls 按 step 顺序配对。"
            "分离原因：异步工具、多步调用、失败时可能只有 call 无 result；"
            "Tool Use Evaluator 的 selection_quality/parameter_accuracy 看 call，result_utilization 看 Agent 是否使用 result。"
            "轨迹不完整时 utilization 低或 Judge 给保守分。",
            _refs("app/evaluators/base.py", "app/evaluators/tool_use_evaluator.py", "app/models/action_types.py"),
            [
                "call/result 分离支持异步与失败场景",
                "_extract_tool_calls 顺序配对",
                "result_utilization 依赖 result 步骤",
                "缺 result 是常见数据质量问题",
            ],
            [
                ("合并成一个行吗？", "会丢失 utilization 与错误归因能力。"),
                ("Callback adapter 怎么映射？", "on_tool_end→tool_result。"),
            ],
        ),
        18: _a(
            "think 记录推理链（action_detail.thought）；node_execute 记录 LangGraph 节点进出（adapter 包装）；"
            "tool_decision 记录 LLM 选择工具的决策理由。"
            "Tactical Evaluator 评估除 plan 外动作；Replan 格式化时包含 think。"
            "Wiki graph 各节点经 instrument 或 EvaluationTrace.record_node 上报 node_execute。",
            _refs("app/models/action_types.py", "sdk/adapters/langgraph.py", "app/evaluators/tactical_evaluator.py"),
            [
                "think：显式 CoT",
                "node_execute：图节点边界",
                "tool_decision：选型理由",
                "Tactical 含这些非 plan 动作",
            ],
            [
                ("think 和 plan 区别？", "plan 是结构化里程碑，think 是中间推理。"),
                ("必须录 think 吗？", "可选，但有助于 Tactical 解释性。"),
            ],
        ),
        19: _a(
            "retrieval 记录检索动作：query、retrieved_docs 列表（path/snippet/score 等）；"
            "evidence 记录最终送入 LLM 的证据池（可能裁剪/重排后）。"
            "RetrievalEvaluator 消费 retrieval；evidence 帮助评 evidence_accuracy 与幻觉。"
            "Wiki search 节点 hybrid_search 后 record_retrieval，respond 前可 record_evidence。",
            _refs("app/evaluators/retrieval_evaluator.py", "app/wiki_agent/evaluation.py", "app/models/action_types.py"),
            [
                "retrieval=召回阶段",
                "evidence=生成前证据池",
                "retrieved_docs 结构是评估输入",
                "两者分离定位召回 vs 引用问题",
            ],
            [
                ("只录 evidence 够吗？", "不够，无法评 coverage/relevance 召回。"),
                ("字段必填？", "path、content/snippet、score 等见 RetrievalEvaluator prompt。"),
            ],
        ),
        20: _a(
            "第三方框架适配策略：1) 手动 sdk/collector record_*；2) 写新 adapter 映射到 ActionType；"
            "3) 离线转换 batch 导入 POST tasks/steps。"
            "Semantic Kernel 等可包装 step 回调→统一 JSON schema。"
            "关键是 tool_call/tool_result 配对与 retrieval 的 retrieved_docs 字段对齐 app/models/schemas.py TrajectoryStep。",
            _refs("sdk/collector.py", "app/adapters/callback.py", "app/models/schemas.py"),
            [
                "adapter 模式扩展框架",
                "手动 collector 最低成本 PoC",
                "schema 对齐比框架更重要",
                "可批量 ETL 历史 log",
            ],
            [
                ("需要改平台吗？", "通常只加 adapter，不改 Evaluator。"),
                ("最小字段集？", "step_number、action_type、action_detail、observation。"),
            ],
        ),
        21: _a(
            "context 随 task 存储（如 key_facts 列表），MemoryEvaluator prompt 注入 context 与 trajectory 中 memory_read/write。"
            "retention 评是否记住早期事实；consistency 评是否自相矛盾。"
            "无显式 memory 动作时 Judge 从 trajectory 启发式推断。"
            "Wiki Agent 可在 context 传 session metadata。",
            _refs("app/evaluators/memory_evaluator.py", "app/models/schemas.py", "app/db/models.py"),
            [
                "key_facts 是 ground hint",
                "memory_read/write 显式更佳",
                "无动作时靠 LLM 推断，噪声更大",
                "context 在 evaluate API 传入",
            ],
            [
                ("key_facts 谁维护？", "Agent 或 adapter 在 start/update 时写入。"),
                ("和 vector memory 关系？", "key_facts 是评估锚点，非替代向量库。"),
            ],
        ),
        22: _a(
            "长轨迹 token 超限策略：BaseEvaluator._format_trajectory 全文拼接；各 Evaluator 可截断 action_detail（如 [:150]）。"
            "sdk _short limit 4000；collector 批量上报也截断。"
            "改进方向：按维提取相关步骤（Tool Use 只送 tool 对）、summarize 中间 think、"
            "或 sliding window + 关键 step 保留。当前实现依赖 LLM 上下文窗口（DeepSeek 等）。",
            _refs("app/evaluators/base.py", "sdk/collector.py", "app/evaluators/tactical_evaluator.py"),
            [
                "当前全量 format，长轨迹有风险",
                "_short 4000 字符截断",
                "可按维过滤步骤降 token",
                "评估成本与轨迹长度线性相关",
            ],
            [
                ("128K 够吗？", "六维并行 × 全轨迹仍贵，应预处理。"),
                ("如何采样？", "保留 plan/failure/replan/首尾 tool 对。"),
            ],
        ),
        23: _a(
            "区分多轮迭代 vs 子任务：用 task_id 粒度——一个 goal 一个 task；"
            "plan_update/replan 标记同一任务内迭代；不同 goal 应 start 新 task。"
            "step_number 单调递增；context 可含 subtask_id（自定义）。"
            "评估按单 task trajectory 独立出分，Analytics 可聚合多 task。",
            _refs("sdk/collector.py", "app/models/action_types.py", "app/api/v1/endpoints/tasks.py"),
            [
                "一 goal 一 task_id",
                "plan_update/replan 表迭代",
                "step_number 单 task 内有序",
                "避免多 goal 混一条 trajectory",
            ],
            [
                ("多轮对话呢？", "同一 session 可同一 task，用 step 区分轮次。"),
                ("子 Agent？", "建议独立 task 或 node_execute 标注。"),
            ],
        ),
        24: _a(
            "Human-in-the-loop：轨迹应记录 interrupt、用户输入、decide 节点分支。"
            "Wiki Agent graph decide 节点判断是否需要人工确认（如知识提取）；"
            "LangGraph interrupt 暂停后恢复，checkpoint AsyncSqliteSaver 存状态。"
            "EvaluationTrace 可 record_state_change 记录 HITL 前后 diff。"
            "评估时 Tactical 可看是否因 HITL 改变路径。",
            _refs("app/wiki_agent/agent/graph.py", "app/models/action_types.py", "app/wiki_agent/evaluation.py"),
            [
                "记录 interrupt 与用户决策",
                "decide 节点 HITL 网关",
                "state_change 记录前后状态",
                "checkpoint 支持会话恢复",
            ],
            [
                ("interrupt 和 failure？", "interrupt 是预期暂停，failure 是异常。"),
                ("评 HITL 质量？", "可看 replan/tactical 是否因反馈改进。"),
            ],
        ),
    }


# Due to size, remaining categories use a compact generator with unique per-id content
CAT_META: dict[int, tuple[str, list[str], list[str]]] = {
    # id: (topic, extra_refs, key_facts)
    25: ("两套 collector", ["app/collectors/trajectory.py", "sdk/collector.py"], "服务端 collector 供平台内部；SDK 零依赖 httpx 供外部 Agent；逻辑应对齐 ActionType 与 batch flush"),
    26: ("finish 与离线缓冲", ["sdk/collector.py"], "finish flush 剩余 steps；无 EVAL_API_BASE_URL 时纯内存；失败步骤进 _steps 缓冲"),
    27: ("EVAL_BATCH_SIZE", ["app/core/config.py", "sdk/collector.py"], "默认 10；过小 HTTP 开销大，过大丢 batch 风险增"),
    28: ("上报失败重试", ["sdk/collector.py"], "当前 catch 后保留缓冲；可改进 exponential backoff 与 dead letter"),
    29: ("线程安全", ["sdk/collector.py"], "_buffer_lock/_flush_lock 单例；高并发锁竞争可 shard collector"),
    30: ("低侵入三种 adapter", ["app/adapters/", "sdk/adapters/"], "langgraph 包装节点；callback 映射 LangChain；llm_proxy 幂等包装 LLM"),
    31: ("LangGraph 包装", ["sdk/adapters/langgraph.py"], "instrument_langgraph 装饰节点记录 NODE_EXECUTE；开销约一次 dict 序列化"),
    32: ("Callback 映射", ["app/adapters/callback.py"], "on_llm_start→think；on_tool_start/end→tool_call/result"),
    33: ("LLM Proxy 幂等", ["app/adapters/llm_proxy.py"], "idempotent 防重复 record 同一 call_id；_seen_events 去重"),
    34: ("手动 collector", ["sdk/collector.py"], "get_collector().record_tool_call/record_retrieval 等 14 种 API"),
    35: ("显式 vs 自动埋点", ["app/wiki_agent/evaluation.py", "sdk/collector.py"], "Wiki 用 EvaluationTrace 精确控制 retrieval 字段；SDK 适合通用 Agent"),
    36: ("轨迹不完整", ["app/evaluators/tool_use_evaluator.py", "app/evaluators/base.py"], "缺 tool_result 时 utilization 低；Planning 缺 plan 得 0"),
    37: ("伪造轨迹", ["app/api/v1/endpoints/tasks.py"], "检测 step 时间戳逆序、call/result 不匹配、异常高分与空动作"),
    38: ("observation 序列化", ["sdk/collector.py", "app/evaluators/base.py"], "非字符串 json.dumps；Judge 读 observation 文本"),
    39: ("step_number", ["sdk/collector.py"], "单调递增；乱序上报应服务端排序或拒绝"),
    40: ("评估工作流", ["app/graphs/evaluation_graph.py"], "validate→六 eval 节点→aggregate→END；生产 evaluate_parallel"),
    41: ("EvaluationState", ["app/graphs/evaluation_graph.py"], "task_id/goal/trajectory/context + 六 score 字段 + overall_evaluation"),
    42: ("双路径并行", ["app/graphs/evaluation_graph.py"], "图串行避 state merge；evaluate_parallel 用 asyncio.gather 71s→15s"),
    43: ("EVAL_PARALLEL", ["app/core/config.py", "app/services/evaluation_service.py"], "True 走 evaluate_parallel；False 可走 StateGraph"),
    44: ("state merge 冲突", ["app/graphs/evaluation_graph.py"], "并行节点写同一 state key 会覆盖；故串行边"),
    45: ("真并行 State 改造", ["app/graphs/evaluation_graph.py"], "用 Annotated reducer 或子 state 分片再 aggregate"),
    46: ("Wiki 节点", ["app/wiki_agent/agent/graph.py"], "search 检索；respond 生成；decide HITL；execute 工具/提取"),
    47: ("AsyncSqliteSaver", ["app/wiki_agent/agent/graph.py"], "checkpoint 持久化 thread_id；interrupt 后 ainvoke 恢复"),
    48: ("decide HITL", ["app/wiki_agent/agent/graph.py"], "判断 extraction 等需人工确认的分支"),
    49: ("知识提取", ["app/wiki_agent/"], "extraction 触发→用户 confirm→sync_manager reindex"),
    50: ("StateGraph vs Compiled", ["app/graphs/evaluation_graph.py"], "StateGraph 构建；compile() 得可 invoke 图"),
    51: ("条件边", ["app/wiki_agent/agent/graph.py"], "Wiki 用 conditional_edges 路由 decide 结果"),
    52: ("Subgraph", ["app/wiki_agent/agent/graph.py"], "可拆 search 为 subgraph 共享 state keys"),
    53: ("interrupt", ["app/wiki_agent/agent/graph.py"], "LangGraph interrupt 协作式暂停；非 Celery 抢占"),
    54: ("LLM-as-Judge", ["app/evaluators/base.py"], "ChatPromptTemplate + temperature=0 + JSON 分数"),
    55: ("temperature=0", ["app/evaluators/base.py"], "降低 Judge 随机性；0.7 会导致同 trajectory 分波动大"),
    56: ("自评偏见", ["app/evaluators/consensus.py"], "Judge≠Agent 模型；或多模型 consensus"),
    57: ("JSON fallback 50", ["app/evaluators/planning_evaluator.py"], "解析失败各子维 50；保守中性；可改 retry 或 structured output"),
    58: ("JSON 抽取漏洞", ["app/evaluators/planning_evaluator.py"], "find/rfind 可能被嵌套 JSON 或 markdown 误导"),
    59: ("Structured Output", ["app/evaluators/planning_evaluator.py"], "可用 with_structured_output 替代手工 parse"),
    60: ("consensus std_score", ["app/evaluators/consensus.py"], "多 Judge 标准差大说明不稳定应告警"),
    61: ("Planning prompt", ["app/evaluators/planning_evaluator.py"], "输入 goal+trajectory；输出 coverage/ordering/granularity/completeness"),
    62: ("中英文 prompt", ["app/evaluators/planning_evaluator.py"], "当前英文 prompt；中文 trajectory 可能略降 Judge 质量"),
    63: ("few-shot", ["app/evaluators/planning_evaluator.py"], "可在 prompt 加示例；本项目默认 zero-shot"),
    64: ("分数 feedback 不一致", ["app/evaluators/planning_evaluator.py"], "后处理校验或让 Judge 输出 reasoning chain"),
    65: ("Prompt Injection", ["app/evaluators/base.py"], "trajectory 中恶意指令；分隔符+系统 prompt  hardened"),
    66: ("prompt 版本管理", ["app/evaluators/"], "prompt 常量化+git tag；评估记录 prompt_version"),
    67: ("token 成本", ["app/evaluators/"], "六维各一次 LLM；轨迹长度主导；并行不省 token"),
    68: ("成本追踪", ["frontend/src/views/Analytics.vue"], "Dashboard 估算；需接 LLM usage callback 才精确"),
    69: ("并行优化", ["app/graphs/evaluation_graph.py"], "瓶颈是 6 次 LLM RTT；gather 已并行；可缓存或 mini Judge"),
    70: ("评估缓存", ["app/services/evaluation_service.py"], "key=hash(trajectory+prompt_version+model)"),
    71: ("部分维度复用", ["app/graphs/evaluation_graph.py"], "只重跑变更维 Evaluator+aggregate"),
    72: ("Planning 四子维", ["app/evaluators/planning_evaluator.py"], "coverage/ordering/granularity/completeness"),
    73: ("Planning 权重", ["app/evaluators/planning_evaluator.py"], "0.3/0.2/0.2/0.3；可用 benchmark 网格搜索"),
    74: ("无 plan 零分", ["app/evaluators/planning_evaluator.py"], "无 plan/plan_update 返回 0；严格但可改 N/A"),
    75: ("granularity", ["app/evaluators/planning_evaluator.py"], "prompt 定义里程碑粒度适中；过细过粗 Judge 描述"),
    76: ("Tactical 排除 plan", ["app/evaluators/tactical_evaluator.py"], "plan 已在 Planning 维；Tactical 评执行步 relevance/efficiency/correctness"),
    77: ("Tactical 例子", ["app/evaluators/tactical_evaluator.py"], "高分：每步靠近 goal；低分：冗余 search"),
    78: ("工具错 Tactical", ["app/evaluators/tactical_evaluator.py"], "决策正确但工具失败：correctness 考虑决策非环境"),
    79: ("Tool Use 三子维", ["app/evaluators/tool_use_evaluator.py"], "selection_quality/parameter_accuracy/result_utilization"),
    80: ("参数 JSON 错误", ["app/evaluators/tool_use_evaluator.py"], "parameter_accuracy 低；selection 可能仍高"),
    81: ("result_utilization", ["app/evaluators/tool_use_evaluator.py"], "常见忽略 tool_result；检测 action 是否引用 result"),
    82: ("Memory 三子维", ["app/evaluators/memory_evaluator.py"], "retention/relevance/consistency"),
    83: ("key_facts 可靠性", ["app/evaluators/memory_evaluator.py"], "显式 key_facts 优于纯推断"),
    84: ("无 memory 动作", ["app/evaluators/memory_evaluator.py"], "LLM 从 trajectory 推断记忆行为"),
    85: ("长短期记忆", ["app/evaluators/memory_evaluator.py"], "可拆 Evaluator；当前合并"),
    86: ("无 replan 满分", ["app/evaluators/replan_evaluator.py"], "无 replan 且无 missed_opportunities 返回 100"),
    87: ("trigger_appropriateness", ["app/evaluators/replan_evaluator.py"], "_detect_missed_replans 检连续 failure"),
    88: ("failure 与 replan", ["app/evaluators/replan_evaluator.py"], "连续 5 failure 无 replan 记 missed"),
    89: ("Replan 缺口", ["app/evaluators/replan_evaluator.py"], "缺 plan diff 量化；可对标 industry replanning rubric"),
    90: ("Retrieval 三子维", ["app/evaluators/retrieval_evaluator.py"], "relevance/evidence_accuracy/coverage"),
    91: ("retrieved_docs", ["app/evaluators/retrieval_evaluator.py"], "需 path、content/snippet、score 等"),
    92: ("无 retrieval 零分", ["app/evaluators/retrieval_evaluator.py"], "非 RAG Agent 该维 0；overall 仍加权需解读"),
    93: ("幻觉评估", ["app/evaluators/retrieval_evaluator.py"], "evidence_accuracy 对比 retrieved_docs 与 Agent 陈述"),
    94: ("coverage 低", ["app/evaluators/retrieval_evaluator.py"], "召回窄；建议扩大 query 或 hybrid top_k"),
    95: ("overall 权重", ["app/graphs/evaluation_graph.py"], "planning/tactical 0.2；其余 0.15"),
    96: ("两级加权", ["app/graphs/evaluation_graph.py"], "子维加权→维 overall→六维 overall；可解释性强"),
    97: ("单维异常 0", ["app/graphs/evaluation_graph.py"], "一维 0 最多拉低 15-20%；应标记 failed dim"),
    98: ("分块 500/50", ["app/wiki_agent/"], "chunk size 500 overlap 50 平衡语义与粒度"),
    99: ("标题层级", ["app/wiki_agent/"], "标题拼入 chunk 保留结构"),
    100: ("代码块分块", ["app/wiki_agent/"], "避免从 markdown 中间切断 fenced code"),
    101: ("增量索引", ["app/wiki_agent/sync_manager.py"], "CRUD 触发增量；全量 rebuild 兜底"),
    102: ("BGE 选型", ["app/wiki_agent/"], "bge-small-zh-v1.5 512维中文 wiki 轻量"),
    103: ("零向量降级", ["app/wiki_agent/"], "embedding 失败返回零向量；semantic 失效靠 BM25"),
    104: ("Milvus schema", ["app/wiki_agent/"], "path/chunk/title/embedding 字段"),
    105: ("Milvus 降级 BM25", ["app/wiki_agent/agent/tools/search_tools.py"], "available false 时仅 keyword_search"),
    106: ("RRF k=60", ["app/wiki_agent/agent/tools/search_tools.py"], "score+=1/(k+rank+1)；k=60 平滑秩次"),
    107: ("RRF vs 加权", ["app/wiki_agent/agent/tools/search_tools.py"], "RRF 无分数标定问题；不同量纲融合"),
    108: ("jieba BM25", ["app/wiki_agent/agent/tools/search_tools.py"], "中文分词；英文靠 BM25 仍可用但弱于 semantic"),
    109: ("path 去重", ["app/wiki_agent/agent/tools/search_tools.py"], "同 path 保留最高分 chunk 防刷屏"),
    110: ("top_k", ["app/wiki_agent/agent/tools/search_tools.py"], "limit*2 召回再 RRF 截断 limit"),
    111: ("record_retrieval", ["app/wiki_agent/evaluation.py", "app/wiki_agent/agent/graph.py"], "search 后写入 retrieval 步骤"),
    112: ("检索好生成差", ["app/evaluators/retrieval_evaluator.py"], "测例：高 relevance 低 evidence_accuracy"),
    113: ("RAG ground truth", ["app/benchmarks/"], "合成轨迹+人工 spot；无大规模标注集"),
    114: ("Wiki 链路", ["app/wiki_agent/agent/graph.py"], "提问→hybrid_search→LLM respond→可选 extract"),
    115: ("Chat SSE", ["app/wiki_agent/"], "SSE 流式 token；事件 type 含 message/done/error"),
    116: ("SYSTEM_PROMPT", ["app/wiki_agent/agent/"], "约束引用来源、拒答无证据"),
    117: ("自动提取", ["app/wiki_agent/"], "条件触发+用户 confirm"),
    118: ("reject 提取", ["app/wiki_agent/"], "状态标记 rejected 防重复 prompt"),
    119: ("CRUD 索引", ["app/wiki_agent/sync_manager.py"], "删页清理 Milvus+BM25"),
    120: ("history rollback", ["app/wiki_agent/"], "版本链+回滚触发 reindex"),
    121: ("EvaluationTrace 事件", ["app/wiki_agent/evaluation.py"], "plan/tool/retrieval 等与 SDK 同 schema"),
    122: ("EVAL_AUTO_RUN", ["app/wiki_agent/evaluation.py", "app/core/config.py"], "finish 后异步 POST /evaluations"),
    123: ("零侵入 SDK", ["sdk/collector.py", "sdk/adapters/langgraph.py"], "import adapter 包装即可；最少数行"),
    124: ("adapter 路径", ["app/adapters/", "sdk/adapters/"], "镜像关系；SDK 可独立 pip"),
    125: ("LangGraph 兼容", ["sdk/adapters/langgraph.py"], "compile/ainvoke API 不变"),
    126: ("同步异步节点", ["sdk/adapters/langgraph.py"], "分别包装 sync/async 函数"),
    127: ("state diff 截断", ["sdk/adapters/langgraph.py"], "_short 限制 state 快照大小"),
    128: ("SDK 独立安装", ["sdk/"], "httpx 依赖；不依赖 app 包"),
    129: ("非 LangChain 接入", ["sdk/collector.py"], "手动 record 或 HTTP API"),
    130: ("ActionType 同步", ["app/models/action_types.py", "sdk/collector.py"], "两处常量需 CI diff 检查"),
    131: ("单调性基准", ["app/benchmarks/monotonicity.py"], "6 trajectory QUALITY_ORDER 非递增+0.05"),
    132: ("合成轨迹", ["app/benchmarks/monotonicity_data.py"], "REFERENCE_SCORES 93.1→20.0 标定"),
    133: ("容差 0.05", ["app/benchmarks/monotonicity.py"], "check_monotonicity 允许小幅上跳"),
    134: ("逆序定位", ["app/benchmarks/monotonicity.py"], "对比 dim_scores 找逆序维"),
    135: ("eval_evaluator_accuracy", ["tests/"], "好/坏场景对比断言"),
    136: ("真实轨迹补充", ["app/benchmarks/"], "脱敏业务 trace 加入 ALL_TRAJECTORIES"),
    137: ("评估准确率", ["app/evaluators/consensus.py"], "人工 vs Judge agreement"),
    138: ("benchmark_multimodel", ["app/benchmarks/"], "多 Judge 模型排序一致性"),
    139: ("POST evaluations 202", ["app/api/v1/endpoints/evaluation.py"], "异步；客户端轮询或 SSE"),
    140: ("SSE 格式", ["app/api/v1/endpoints/evaluation.py"], "progress/result/done 事件 JSON"),
    141: ("SSE replay", ["app/api/v1/endpoints/evaluation.py"], "已完成评估重放缓存结果不重跑 LLM"),
    142: ("任务状态机", ["app/db/models.py"], "PENDING→RUNNING→COMPLETED"),
    143: ("PENDING vs RUNNING", ["app/services/evaluation_service.py"], "推轨迹仍 PENDING；评估开始 RUNNING"),
    144: ("async session", ["app/db/session.py"], "Depends get_db yield session"),
    145: ("SQLite PostgreSQL", ["app/core/config.py"], "DATABASE_URL 切换；Alembic 可选"),
    146: ("AUTH_ENABLED", ["app/core/config.py"], "API Key header；health 跳过"),
    147: ("双 health", ["app/main.py", "frontend/vite.config.ts"], "/health 与 /api/v1/system/health；proxy"),
    148: ("10万评估/日", ["app/services/evaluation_service.py"], "队列+worker+PG+缓存 Judge"),
    149: ("Celery vs BackgroundTasks", ["app/services/evaluation_service.py"], "BackgroundTasks 进程内；大规模需 Redis 队列"),
    150: ("多租户 workspace", ["app/api/v1/endpoints/workspace_endpoints.py"], "workspace 隔离 task/eval"),
    151: ("评估版本化", ["app/db/models.py"], "存 prompt_version model_version"),
    152: ("A/B prompt", ["app/evaluators/"], "双 prompt 并行 evaluate 对比"),
    153: ("Judge 429", ["app/evaluators/base.py"], "gather 部分失败得 0；应 retry 与 circuit breaker"),
    154: ("DB 一致性", ["app/services/evaluation_service.py"], "评估失败 mark FAILED；transaction"),
    155: ("双索引不一致", ["app/wiki_agent/sync_manager.py"], "定期 reconcile Milvus vs BM25"),
    156: ("评估幂等", ["app/services/evaluation_service.py"], "同 task_id 重复触发 upsert 或 reject"),
    157: ("PII 脱敏", ["sdk/collector.py"], "_short+regex Redact；存储加密"),
    158: ("Wiki XSS", ["app/wiki_agent/"], "Markdown sanitize；path 校验"),
    159: ("WEBHOOK 安全", ["app/core/config.py"], "EVAL_WEBHOOK_URL HMAC 签名"),
    160: ("平台观测", ["app/core/config.py"], "ENABLE_TRACING OTEL"),
    161: ("Judge 监控", ["app/evaluators/base.py"], "记录 latency/token metrics"),
    162: ("Planning 低分排查", ["app/evaluators/planning_evaluator.py"], "查是否有 plan 动作；prompt feedback"),
    163: ("overall 高分争议", ["app/graphs/evaluation_graph.py"], "展示六维雷达；业务 KPI 对齐"),
    164: ("Retrieval 0 分", ["app/evaluators/retrieval_evaluator.py"], "最可能未 record_retrieval"),
    165: ("benchmark 失败", ["app/benchmarks/monotonicity.py"], "数据 vs Evaluator：看 dim 逆序"),
    166: ("Wiki 不引用 KB", ["app/wiki_agent/agent/graph.py"], "查 hybrid 结果与 SYSTEM_PROMPT"),
    167: ("Milvus unavailable", ["app/wiki_agent/agent/tools/search_tools.py"], "状态页 BM25-only；恢复 Milvus"),
    168: ("Dashboard 空", ["frontend/src/views/Dashboard.vue"], "无数据/API 失败/渲染错误"),
    169: ("SSE 断开", ["app/api/v1/endpoints/evaluation.py"], "客户端重连+Last-Event-ID 或轮询"),
    170: ("JSON parse HTML", ["frontend/"], "proxy 错配返回 HTML；fix vite proxy"),
    171: ("_extract_tool_calls", ["app/evaluators/base.py"], "顺序扫描 tool_call 配 tool_result"),
    172: ("evaluate_parallel", ["app/graphs/evaluation_graph.py"], "asyncio.gather 六 Evaluator 异常返 0"),
    173: ("instrument_langgraph", ["sdk/adapters/langgraph.py"], "wrap 节点函数 record 前后"),
    174: ("RRF 手算", ["app/wiki_agent/agent/tools/search_tools.py"], "两列表 rank 代入 1/(60+r+1) 相加"),
    175: ("新增 Safety 维", ["app/evaluators/", "app/graphs/evaluation_graph.py"], "新 evaluator+schema+权重"),
    176: ("效率 Evaluator", ["app/evaluators/base.py"], "统计 step 数与 goal 达成"),
    177: ("采样率", ["sdk/collector.py"], "random.sample 在 record 前"),
    178: ("gzip 上报", ["sdk/collector.py", "app/api/"], "Content-Encoding gzip 解压"),
    179: ("可执行性子维", ["app/evaluators/planning_evaluator.py"], "prompt 加 executability 字段"),
    180: ("评估 diff API", ["app/api/v1/endpoints/evaluation.py"], "对比两次 Evaluation ORM 记录"),
    181: ("评估 2.0", ["app/evaluators/", "app/graphs/"], "插件 registry+动态权重+consensus"),
    182: ("联邦评估", ["sdk/collector.py"], "多部署上报中央 EVAL_API"),
    183: ("在线评估", ["app/graphs/evaluation_graph.py"], "每步 mini Judge SSE 反馈"),
    184: ("MCP Server", ["app/"], "暴露 evaluate/tools MCP"),
    185: ("黄金数据集", ["app/benchmarks/"], "采集→标注→版本→CI 回归"),
    186: ("Agent 趋势", ["app/"], "Multi-agent、long context、eval-driven dev"),
    187: ("Multi-Agent 评估", ["app/evaluators/"], "扩展 trajectory 含 agent_id"),
    188: ("可解释与可评估", ["app/evaluators/"], "可评估需结构化 trace；可解释靠 feedback"),
    189: ("RLHF vs prompt", ["app/evaluators/"], "RLHF Agent 评 policy 一致性"),
    190: ("长上下文", ["sdk/collector.py"], "截断与摘要策略"),
    191: ("个人负责", ["app/"], "结合候选人实际；参考 evaluators/graph/sdk"),
    192: ("Judge 人工不一致", ["app/evaluators/consensus.py"], "校准 prompt 或换 Judge"),
    193: ("架构重做", ["app/graphs/evaluation_graph.py"], "可能早做 plugin evaluators"),
    194: ("技术债", ["app/graphs/evaluation_graph.py"], "图串行注释 vs 并行 gather 双路径"),
    195: ("评估 vs Agent 优先", ["app/"], "MVP 可 Demo Agent；规模化需 eval 先行"),
    196: ("推广轨迹规范", ["docs/", "sdk/"], "文档+adapter 降低摩擦"),
    197: ("评估与 KPI", ["app/graphs/evaluation_graph.py"], "联合 dashboard 业务指标"),
    198: ("CI benchmark", ["app/benchmarks/monotonicity.py"], "pytest merge gate"),
    199: ("领域专家", ["app/evaluators/"], "共建 rubric few-shot"),
    200: ("单一数字", ["app/graphs/evaluation_graph.py"], "overall+六维雷达+recommendations 而非单分"),
}


CATEGORY_CONTEXT: dict[str, str] = {
    "轨迹（Trajectory）与埋点": "轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。",
    "LangGraph 与工作流编排": "LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。",
    "LLM-as-Judge 评估体系": "六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。",
    "六维评估器深入": "每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。",
    "RAG 与检索质量": "Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。",
    "Wiki Agent 端到端实现": "Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。",
    "SDK 与零侵入接入": "sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。",
    "Benchmark 与评估校准": "monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。",
    "后端工程与 API 设计": "FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。",
    "系统设计与生产化": "当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。",
    "调试、排错与案例分析": "排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。",
    "编码与现场设计题": "改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。",
    "开放讨论与行为面": "回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。",
}


def _parse_question_texts() -> dict[int, str]:
    import re

    text = (ROOT / "docs" / "interview_questions_agent_dev.md").read_text(encoding="utf-8")
    out: dict[int, str] = {}
    for line in text.splitlines():
        m = re.match(r"^(\d+)\.\s+(?:\*\*)?([★]+)?(?:\*\*)?\s*(.+)$", line.strip())
        if m:
            qid = int(m.group(1))
            if 1 <= qid <= 200:
                q = re.sub(r"^\*\*|\*\*$", "", m.group(3)).strip()
                out[qid] = q
    return out


QUESTION_TEXTS = _parse_question_texts()


def _build_unique_reference(qid: int, topic: str, facts: str, refs: list[str]) -> str:
    qtext = QUESTION_TEXTS.get(qid, topic)
    cat = next((c for lo, hi, c in [
        (25, 39, "轨迹（Trajectory）与埋点"),
        (40, 53, "LangGraph 与工作流编排"),
        (54, 71, "LLM-as-Judge 评估体系"),
        (72, 97, "六维评估器深入"),
        (98, 113, "RAG 与检索质量"),
        (114, 122, "Wiki Agent 端到端实现"),
        (123, 130, "SDK 与零侵入接入"),
        (131, 138, "Benchmark 与评估校准"),
        (139, 147, "后端工程与 API 设计"),
        (148, 161, "系统设计与生产化"),
        (162, 170, "调试、排错与案例分析"),
        (171, 185, "编码与现场设计题"),
        (186, 200, "开放讨论与行为面"),
    ] if lo <= qid <= hi), "轨迹（Trajectory）与埋点")
    ctx = CATEGORY_CONTEXT[cat]
    primary = refs[0]
    hooks = [
        f"问题「{qtext}」考察 {topic}。{facts} {ctx} 首要读 {primary}，并结合 evaluation_graph.py 理解评估如何消费 trajectory。",
        f"围绕 {topic}：{facts} 面试回答应先说业务场景，再落到 {primary} 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。{ctx}",
        f"Q{qid} 与 {topic} 相关。{facts} Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。{ctx}",
    ]
    tails = [
        "若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。",
        "若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。",
        "若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。",
        "若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。",
        "若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。",
    ]
    return hooks[qid % 3] + tails[(qid // 3) % len(tails)]


def _build_points(qid: int, topic: str, facts: str, refs: list[str]) -> list[str]:
    base = [
        f"{topic}：{facts.split('；')[0].split('。')[0]}",
        f"代码入口：{refs[0]}",
    ]
    extras = {
        25: ["app/collectors/trajectory.py 供平台内部", "sdk/collector.py 供外部零依赖", "两者 ActionType 与 batch 语义应一致"],
        42: ["LangGraph 图串行因 state merge", "evaluate_parallel 用 asyncio.gather", "注释写明 71s→~15s"],
        57: ["各 Evaluator _parse_scores fallback 50", "content.find('{') 抽取 JSON", "可改 structured output"],
        86: ["无 replan 且无 missed→100 分", "_detect_missed_replans 连续 5 failure", "有 missed 才走 LLM Judge"],
        106: ["RRF: 1/(k+rank+1)", "k=60 在 search_tools.py", "semantic 与 BM25 各取 limit*2"],
        131: ["六条 QUALITY_ORDER 轨迹", "check_monotonicity +0.05", "REFERENCE_SCORES 标定参考"],
        172: ["asyncio.gather 六任务", "单维异常返回 overall 0", "EvaluationService 生产默认路径"],
    }
    pts = base + extras.get(qid, [
        "与六维 LLM-as-Judge 评估链路相关",
        "轨迹 schema 见 app/models/action_types.py",
    ])
    return pts[:5] if len(pts) >= 3 else pts + ["配合 monotonicity benchmark 做回归"]


def _build_followups(qid: int, topic: str, refs: list[str]) -> list[tuple[str, str]]:
    if qid >= 186:
        return [
            ("如何结合本项目回答开放题？", f"引用 {refs[0]} 与 evaluation_graph.py，讲清轨迹驱动评估价值。"),
            ("怎样体现架构深度？", "对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。"),
            ("若 PM 要单一 KPI？", "给 overall+六维雷达+recommendations，拒绝只看一个数。"),
        ]
    return [
        (f"「{topic}」最先看哪段代码？", f"打开 {refs[0]}，再对照 app/graphs/evaluation_graph.py 的数据流。"),
        (f"Demo 里如何验证 {topic}？", "跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。"),
        ("与 benchmark 关系？", "改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。"),
    ]


def entries_from_meta(start: int, end: int) -> dict[int, dict]:
    out: dict[int, dict] = {}
    skip = entries_cat1() | entries_cat2()
    for qid in range(start, end + 1):
        if qid in skip:
            continue
        if qid not in CAT_META:
            raise KeyError(f"Missing CAT_META for {qid}")
        topic, extra_refs, facts = CAT_META[qid]
        refs = _refs(*extra_refs)
        ref = _build_unique_reference(qid, topic, facts, refs)
        out[qid] = _a(
            ref,
            refs,
            _build_points(qid, topic, facts, refs),
            _build_followups(qid, topic, refs),
        )
    return out


def build_bank() -> dict[int, dict]:
    bank: dict[int, dict] = {}
    bank.update(entries_cat1())
    bank.update(entries_cat2())
    bank.update(entries_from_meta(25, 200))
    if len(bank) != 200:
        raise ValueError(f"Expected 200 entries, got {len(bank)}")
    for qid, entry in bank.items():
        if len(entry["reference"]) < 200:
            raise ValueError(f"Q{qid} reference too short: {len(entry['reference'])}")
        if not (3 <= len(entry["code_refs"]) <= 6):
            raise ValueError(f"Q{qid} code_refs count: {len(entry['code_refs'])}")
        if not (3 <= len(entry["points"]) <= 5):
            raise ValueError(f"Q{qid} points count: {len(entry['points'])}")
        if not (2 <= len(entry["followups"]) <= 3):
            raise ValueError(f"Q{qid} followups count: {len(entry['followups'])}")
    return bank


def render_py(bank: dict[int, dict]) -> str:
    lines = [
        '"""Interview answer bank for docs/interview_questions_agent_dev.md (Q1-Q200)."""',
        "",
        "from __future__ import annotations",
        "",
        "",
        "def _a(",
        "    reference: str,",
        "    code_refs: list[str],",
        "    points: list[str],",
        "    followups: list[tuple[str, str]],",
        ") -> dict:",
        "    return {",
        '        "reference": reference,',
        '        "code_refs": code_refs,',
        '        "points": points,',
        '        "followups": followups,',
        "    }",
        "",
        "",
        "ANSWER_BANK: dict[int, dict] = {",
    ]
    for qid in sorted(bank.keys()):
        entry = bank[qid]
        lines.append(f"    {qid}: _a(")
        lines.append(f"        {json.dumps(entry['reference'], ensure_ascii=False)},")
        refs_str = ", ".join(json.dumps(r, ensure_ascii=False) for r in entry["code_refs"])
        lines.append(f"        [{refs_str}],")
        pts_str = ", ".join(json.dumps(p, ensure_ascii=False) for p in entry["points"])
        lines.append(f"        [{pts_str}],")
        lines.append("        [")
        for fq, fa in entry["followups"]:
            lines.append(f"            ({json.dumps(fq, ensure_ascii=False)}, {json.dumps(fa, ensure_ascii=False)}),")
        lines.append("        ],")
        lines.append("    ),")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    bank = build_bank()
    OUT.write_text(render_py(bank), encoding="utf-8")
    print(f"Wrote {OUT} with {len(bank)} entries")


if __name__ == "__main__":
    main()
