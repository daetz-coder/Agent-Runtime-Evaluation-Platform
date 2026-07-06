# Agent Runtime Evaluation Platform — 完整技术文档

> 版本：v1.0 | 最后更新：2026-07-06
> 本文档整合项目所有技术文档，覆盖背景、架构、实现、难点、面试问答。

---

## 目录

1. [项目背景与定位](#1-项目背景与定位)
2. [技术选型与理由](#2-技术选型与理由)
3. [系统架构](#3-系统架构)
4. [六维评估体系详解](#4-六维评估体系详解)
5. [评估流水线（端到端）](#5-评估流水线端到端)
6. [轨迹压缩（4 阶段）](#6-轨迹压缩4-阶段)
7. [LLM-as-Judge 一致性方案](#7-llm-as-judge-一致性方案)
8. [性能优化](#8-性能优化)
9. [回归检测与增量评估](#9-回归检测与增量评估)
10. [SDK 数据采集架构](#10-sdk-数据采集架构)
11. [API 设计](#11-api-设计)
12. [数据模型](#12-数据模型)
13. [Redis 缓存策略](#13-redis-缓存策略)
14. [核心难点与解决方案](#14-核心难点与解决方案)
15. [面试高频问答](#15-面试高频问答)
16. [常见陷阱与避坑指南](#16-常见陷阱与避坑指南)
17. [性能指标](#17-性能指标)

---

## 1. 项目背景与定位

### 1.1 现有方案的痛点

| 方案 | 覆盖范围 | 评估粒度 | 诊断能力 |
|------|----------|----------|----------|
| RAGAS | 仅 RAG 检索质量 | 检索级 | 部分 |
| LangSmith | 通用 tracing | 任务级 | ❌ |
| Prompt Evaluation | 最终输出文本 | 输出级 | ❌ |
| **本平台** | **6 维全链路** | **步骤级** | **✅** |

**核心差异**：现有方案回答"Agent 有没有做对"（结果评估），本平台回答"Agent 做得好不好"（过程评估）。

### 1.2 定位

```
❌ 不是 Prompt Evaluation（评估最终输出文本质量）
✅ 是 Agent Runtime Evaluation（评估 Agent 运行时每一步的决策质量）
```

类比：传统评估是"考试只看总分"，本平台是"考试看每道题的解题过程"。

### 1.3 与主流 Benchmark 的关系

| | AgentBench | WebArena | SWE-bench | RAGAS | **本平台** |
|---|---|---|---|---|---|
| 类型 | Benchmark | Benchmark | Benchmark | Eval Framework | **Runtime Eval Platform** |
| 评估粒度 | 任务级 | 任务级 | 任务级 | 检索级 | **步骤级** |
| 评估维度 | 1（成功率） | 1（完成率） | 1（patch 正确率） | 4（RAG 相关） | **6（全链路）** |
| 需要环境 | ✅ | ✅ | ✅ | ❌ | **❌** |
| 诊断能力 | ❌ | ❌ | ❌ | 部分 | **✅ 每步诊断** |
| 增量评估 | ❌ | ❌ | ❌ | ❌ | **✅** |
| 回归检测 | ❌ | ❌ | ❌ | ❌ | **✅** |

**互补关系**：Benchmark 告诉你"成功率 30%"，本平台告诉你"为什么 30%——是规划不行、工具用错、还是记忆丢失"。

---

## 2. 技术选型与理由

### 2.1 技术栈总览

| 类别 | 技术 | 用途 | 选型理由 |
|------|------|------|----------|
| 后端框架 | FastAPI | REST API + SSE | 原生 async，SSE 支持好，自动 OpenAPI 文档 |
| 工作流引擎 | LangGraph | 评估图编排 | 条件边、状态持久化、Human-in-the-Loop |
| ORM | SQLAlchemy 2.0 | 数据库操作 | async 支持，成熟稳定 |
| 数据库 | SQLite → PostgreSQL | 任务/轨迹/评估存储 | 开发用 SQLite 零配置，生产用 PG |
| 缓存 | Redis（可选） | LLM 结果缓存 + 限流 | 优雅降级，不可用时应用正常运行 |
| LLM | DeepSeek / GLM / Qwen | 评估裁判（LLM-as-Judge） | 多模型共识，成本低 |
| 前端 | Vue 3 + Element Plus | Dashboard | 轻量，组件丰富 |
| 可视化 | ECharts | 雷达图/趋势线/热力图 | 功能强大，免费 |
| 向量库 | Milvus Lite | Wiki Agent 知识检索 | 嵌入式，零配置 |

### 2.2 关键选型决策

**为什么选 LangGraph 而不是纯 asyncio？**
- 需要状态持久化（SQLite checkpoint）支持 HITL 暂停/恢复
- 需要条件边（简单查询跳过 RAG，复杂查询走完整管线）
- 需要可视化调试（LangGraph Studio）

**为什么 Redis 是可选的？**
- 降低部署门槛：个人开发者不需要装 Redis
- 优雅降级：所有缓存操作 try/except 后静默返回 None
- 核心功能不受影响：评估、轨迹采集、API 都能正常工作

**为什么用 LLM-as-Judge 而不是规则？**
- Agent 行为复杂，无法用简单规则判断"规划是否合理"
- LLM 能理解语义，判断"行动是否与目标相关"
- 通过锚点 + 共识机制控制评分一致性

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────┐     ┌───────────────────┐     ┌──────────────────┐
│   Frontend  │────▶│   FastAPI Server   │◀────│   SDK Collector  │
│  (Vue 3 +   │◀────│  (Async 全链路)    │     │  (Pydantic Schema)│
│   ECharts)  │     │                   │     └──────────────────┘
└─────────────┘     ├───────────────────┤
                    │   Evaluators × 6  │
                    │   (LLM-as-Judge)  │
                    ├───────────────────┤     ┌──────────────────┐
                    │   Redis Cache     │     │   SQLite / PG    │
                    │   (可选，优雅降级) │     │   (任务/轨迹/评估)│
                    └───────────────────┘     └──────────────────┘
```

### 3.2 两个核心子系统

| 子系统 | 说明 |
|--------|------|
| **评估引擎** | 6 个并行 LLM-as-Judge 评估器 + 多模型共识 + 4 阶段轨迹压缩 |
| **Wiki Agent** | RAG 知识库问答（四级混合检索 + Query 改写 + 双层记忆 + HITL CRUD） |

### 3.3 数据流

```
SDK Collector → API → DB → 评估服务 → 6 评估器并行 → DB → 报表 API → Dashboard
                     ↓
               Redis 缓存（LLM 结果 24h / 报表 5min / Dashboard 30s）
```

### 3.4 中间件链

```
请求 → CORS → CorrelationIdMiddleware → AuthMiddleware → RateLimitMiddleware → PrometheusMiddleware → 路由
```

---

## 4. 六维评估体系详解

### 4.1 维度总览

| 维度 | 权重 | 子指标 | 评估器文件 |
|------|------|--------|-----------|
| 规划质量（Planning） | 20% | 覆盖率、顺序性、粒度、完整性 | `planning_evaluator.py` |
| 战术决策（Tactical） | 20% | 相关性、效率、正确性 | `tactical_evaluator.py` |
| 工具使用（Tool Use） | 15% | 选择质量、参数准确性、结果利用 | `tool_use_evaluator.py` |
| 记忆保持（Memory） | 15% | 保持力、相关性、一致性 | `memory_evaluator.py` |
| 重规划（Replan） | 15% | 触发适当性、适应质量、学习能力 | `replan_evaluator.py` |
| 检索质量（Retrieval） | 15% | 相关性、证据准确性、覆盖度 | `retrieval_evaluator.py` |

### 4.2 子指标详解（20 项）

**Planning（4 项）**
- 覆盖率 Coverage（30%）：计划是否覆盖所有必要里程碑
- 顺序性 Ordering（20%）：步骤顺序是否合理，依赖关系是否正确
- 粒度 Granularity（20%）：细化程度是否适当（过细/过粗都扣分）
- 完整性 Completeness（30%）：是否考虑边界情况、错误处理

**Tactical（3 项）**
- 相关性 Relevance（35%）：行动是否与当前状态和目标相关
- 效率 Efficiency（30%）：是否有不必要的绕路
- 正确性 Correctness（35%）：专家是否会做同样的事

**Tool Use（3 项）**
- 选择质量 Selection Quality（40%）：是否选择了最合适的工具
- 参数准确性 Parameter Accuracy（30%）：参数是否正确完整
- 结果利用 Result Utilization（30%）：工具结果是否被有效利用

**Memory（3 项）**
- 保持力 Retention（45%）：整个执行过程中是否记住关键事实
- 相关性 Relevance（30%）：回忆的信息是否与当前任务相关
- 一致性 Consistency（25%）：记忆是否前后一致，无矛盾

**Replan（3 项）**
- 触发适当性 Trigger Appropriateness（35%）：重规划时机是否恰当
- 适应质量 Adaptation Quality（35%）：新计划是否解决了问题
- 失败中学习 Learning from Failure（30%）：是否避免了旧错误

**Retrieval（3 项）**
- 相关性 Relevance（35%）：检索文档与问题的相关程度
- 证据准确性 Evidence Accuracy（35%）：回答是否准确引用检索内容
- 覆盖度 Coverage（30%）：检索结果是否包含充分信息

### 4.3 评分锚点示例（Planning - 覆盖率）

| 分数 | 锚点表现 |
|------|----------|
| 0 | 完全没有规划，或计划与目标毫无关系 |
| 25 | 仅覆盖了目标的 1-2 个方面，遗漏了超过一半的关键步骤 |
| 50 | 覆盖了主要步骤，但遗漏了 2-3 个关键里程碑 |
| 75 | 覆盖了绝大部分里程碑，仅遗漏 1 个次要步骤 |
| 100 | 完整覆盖所有必要里程碑，包括分析、实现、测试、文档 |

### 4.4 适用性自动标记

不是所有轨迹都涉及所有维度。不适用的维度自动从总分中剔除：

```python
# ToolUse：没有工具调用时标记不适用
if not tool_calls:
    return ToolUseScore(applicable=False, not_applicable_reason="...")

# Replan：Agent 顺利完成时标记不适用
if not replan_events and not missed_opportunities:
    return ReplanScore(applicable=False, not_applicable_reason="...")

# 加权计算时，不适用维度从分子分母同时剔除
overall = Σ(weight × score) / Σ(weight)  # 仅对适用维度
```

---

## 5. 评估流水线（端到端）

### 5.1 流程图

```
SDK 采集轨迹 → API 入库 → 评估服务 → 轨迹压缩 → 6 评估器并行 → 汇总分数 → 入库 → 报表
                                    ↓
                              Redis 缓存检查
                              (相同 prompt 24h 命中)
```

### 5.2 双执行模式

```python
if settings.EVAL_PARALLEL:
    # 默认：6 评估器 asyncio.gather 并行（~15s）
    return await evaluate_parallel(goal, trajectory)
else:
    # 调试：LangGraph StateGraph 串行（~71s），有完整 trace
    return await evaluation_graph.invoke(...)
```

### 5.3 评估器内部流程

```
输入：goal + trajectory + context
    ↓
提取相关步骤（plan / tool_call / memory_* / retrieval 等）
    ↓
格式化为文本（4 阶段压缩后）
    ↓
构造 prompt（含评分锚点 + format_instructions）
    ↓
三级降级调用 LLM：
  1. with_structured_output（GPT-4/Claude）
  2. PydanticOutputParser（DeepSeek）
  3. 手动 JSON 解析（兜底）
    ↓
Pydantic Schema 校验（ge=0, le=100）
    ↓
计算加权子指标分数
    ↓
返回 XxxScore（含 overall + feedback + llm_suggestions）
```

### 5.4 幂等性设计

- `create_evaluation`：同一 task 的 IN_PROGRESS 评估已存在时，返回已有记录
- `create_task`：提供 ID 时幂等
- Stream claim：Redis SETNX 原子操作，防止并发评估同一任务

---

## 6. 轨迹压缩（4 阶段）

### 6.1 为什么需要压缩

Agent 轨迹可能有 200+ 步，直接送给 LLM 评估会消耗 50k+ token。压缩管线减少 80% token。

### 6.2 四阶段管线

```
原始轨迹（200 步）
    ↓ Stage 1: 重要性过滤
    保留: plan, tool_call, tool_result, memory_*, retrieval, evidence, failure, replan, think
    丢弃: node_execute, tool_decision, state_change 等噪声
    ↓ Stage 2: Think 截断
    think 步骤的 observation 截断到 200 字符
    ↓ Stage 3: 滑动窗口
    保留最近 30 步 + "锚点"步骤（plan, failure）
    ↓ Stage 4: 格式化
    输出结构化文本，头部显示 total/omitted/showing 计数
    ↓
压缩后轨迹（~40 步）
```

### 6.3 关键设计决策

- **锚点保留**：PLAN 和 FAILURE 步骤永远保留——没有初始计划就无法评估规划质量，没有失败就无法评估重规划
- **完全确定性**：不调用 LLM，速度快且可复现
- **不可变操作**：创建浅拷贝而不是修改原始对象

---

## 7. LLM-as-Judge 一致性方案

### 7.1 问题

同一个轨迹问两次可能打出不同的分。需要三种机制控制一致性。

### 7.2 方案 A：显式评分锚点

每个子指标定义 0/25/50/75/100 五档的具体行为描述。LLM 对照锚点打分而不是凭感觉。

### 7.3 方案 B：多模型共识

```
DeepSeek Chat  ──→  Planning: 78  ─┐
GLM-4          ──→  Planning: 82  ─┤→ mean=80, std=2.0（高一致性）
Qwen Plus      ──→  Planning: 80  ─┘
```

三级优先级：
1. 跨厂商共识（DeepSeek + GLM + Qwen + OpenAI + Anthropic）
2. 同厂商多模型（deepseek-chat + deepseek-reasoner）
3. 温度多样性（同模型 temp=0 vs 0.7）

std < 2.0 = 高一致性（可信），std > 10.0 = 分歧大（需优化评分标准）。

### 7.4 方案 C：Pydantic Structured Output

三级降级策略：

```
with_structured_output（GPT-4/Claude 支持）
    ↓ 检测到 "response_format unavailable" → 立即降级
PydanticOutputParser（DeepSeek 等模型可用）
    ↓ 解析失败 → 重试 3 次，附带错误反馈
手动 JSON 解析（最后兜底）
```

好处：
- 分数范围强制 0-100（Pydantic `ge=0, le=100`）
- 校验失败自动重试 3 次
- 解析失败不再静默返回默认 50 分

---

## 8. 性能优化

### 8.1 优化层次

| 层次 | 优化手段 | 提速倍数 | 原理 |
|------|----------|----------|------|
| 1 | 并行评估 | 5x | 6 评估器 asyncio.gather |
| 2 | LLM 结果缓存 | 10x+ | SHA-256 prompt 哈希，24h TTL |
| 3 | 增量评估 | 3x | 只重跑受影响的维度 |
| 4 | 轨迹压缩 | 80% token 减少 | 4 阶段确定性压缩 |
| 5 | Redis 缓存 | sub-10ms | 报表/Dashboard/Task 缓存 |

### 8.2 LLM 结果缓存

```python
cache_key = f"llm:{evaluator_name}:{model_name}:{prompt_hash}"
# prompt_hash = SHA-256(inputs JSON)[:16]
# 相同轨迹+目标+模型 = 命中缓存，24h 内不重复调用 LLM
```

### 8.3 增量评估

```python
# 变化-维度映射
CHANGE_DIMENSION_MAP = {
    "plan": ["planning", "tactical"],
    "tool_call": ["tool_use"],
    "retrieval": ["retrieval"],
    "memory_write": ["memory", "replan"],
}
# 只重跑受影响的 2-3 个维度，其余复用旧分数
```

### 8.4 Redis 优雅降级

```python
async def cache_get(key):
    try:
        return await redis.get(key)
    except Exception:
        return None  # Redis 不可用时静默降级，不崩溃
```

---

## 9. 回归检测与增量评估

### 9.1 回归检测

```python
# 不同维度有不同的敏感度阈值
THRESHOLDS = {
    "overall": -5.0,      # 总分下降 5 分就触发
    "tool_use": -8.0,
    "planning": -10.0,
}

# 双重检测
has_regression = (overall_delta < threshold) or any(d.is_regression for d in dims)
```

输出示例：`Regression detected! Planning: 72->58 (-14). Overall: 75->68 (-7).`

### 9.2 轨迹对比（DiffService）

逐步对比两个轨迹，检测 added/removed/changed 步骤，解释回归原因。

---

## 10. SDK 数据采集架构

### 10.1 三种接入模式

| 模式 | 适用场景 | 侵入性 |
|------|----------|--------|
| Instrument（自动埋点） | LangChain/LangGraph 应用 | 零侵入，自动 hook |
| Proxy（LLM 代理） | 非 LangChain 应用 | 包装 LLM 调用 |
| Callback（手动埋点） | 完全控制 | 手动调用 collector |

### 10.2 14 种 ActionType

| ActionType | 用途 | Detail Schema |
|------------|------|---------------|
| `plan` | 初始计划 | steps, milestones |
| `plan_update` | 计划更新 | next_action, remaining_steps |
| `tool_call` | 工具调用 | tool_name, input |
| `tool_result` | 工具结果 | success, error_type, duration_ms |
| `memory_write` | 写记忆 | key, value, memory_type |
| `memory_read` | 读记忆 | key, hit, value |
| `think` | 思考 | thought |
| `replan` | 重规划 | reason, new_plan |
| `failure` | 失败 | error_type, error_message, recoverable |
| `retrieval` | 知识检索 | query, source, result_count |
| `evidence` | 证据池 | evidence_type, sources |
| `state_change` | 状态变化 | trigger, diff |
| `node_execute` | 节点执行 | node_name |
| `tool_decision` | 工具决策 | decision, reason |

每种 ActionType 有独立的 Pydantic Schema，构造时 `field_validator` 自动截断过长字段。

---

## 11. API 设计

### 11.1 核心端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/tasks` | POST/GET | 创建/查询任务 |
| `/api/v1/evaluations` | POST/GET | 触发/查询评估 |
| `/api/v1/evaluations/{id}/replay` | GET | 逐步回放调试 |
| `/api/v1/evaluations/{id}/judge-raw` | GET | Judge 透明度面板 |
| `/api/v1/evaluations/diff` | GET | 轨迹对比 |
| `/api/v1/evaluations/incremental` | POST | 增量评估 |
| `/api/v1/reports` | GET | 分析报表 |
| `/api/v1/benchmark` | POST/GET | 基准测试 |
| `/api/v1/settings` | GET/PUT | 配置管理 |
| `/api/v1/system/health` | GET | 健康检查 |

### 11.2 SSE 流式评估

评估进度通过 Server-Sent Events 实时推送。

---

## 12. 数据模型

### 12.1 核心实体

- **AgentTask**：任务（goal, status, created_at）
- **Trajectory**：轨迹（task_id, steps JSON）
- **Evaluation**：评估结果（task_id, 6 维分数, overall, feedback）
- **EvaluationStep**：评估步骤详情（dimension, score, judge_raw）

### 12.2 Judge 透明度

每个评估记录保存 `_judge_raw`（原始 prompt + response + model + latency），支持 "Judge Panel" UI。

---

## 13. Redis 缓存策略

| 场景 | TTL | 理由 |
|------|-----|------|
| LLM 评估结果 | 24h | 相同输入 = 相同输出 |
| 报表聚合 | 5min | 聚合查询 O(N)，Dashboard 高频刷新 |
| Dashboard 计数器 | 30s | 高频刷新 |
| Task 查询 | 60s | 评估流程内重复查询 |
| 接口限流 | 滑动窗口 | 防止 LLM API 费用失控 |

---

## 14. 核心难点与解决方案

### 14.1 LLM-as-Judge 评分不一致

**问题**：同一轨迹问两次可能打出不同分数。

**解决方案**：
- 显式评分锚点（0/25/50/75/100 五档行为描述）
- 多模型共识（mean + std 量化一致性）
- Pydantic Structured Output（强制分数范围 0-100）

### 14.2 轨迹 Token 爆炸

**问题**：200 步轨迹消耗 50k+ token。

**解决方案**：4 阶段确定性压缩（重要性过滤 → Think 截断 → 滑动窗口 → 格式化），减少 80% token。

### 14.3 DeepSeek 不支持 Structured Output

**问题**：`with_structured_output` 返回 400 错误。

**解决方案**：三级降级（`with_structured_output` → `PydanticOutputParser` → 手动解析）。检测到 `response_format unavailable` 立即降级，不浪费重试次数。

### 14.4 评估维度适用性

**问题**：不是所有轨迹都涉及所有维度。

**解决方案**：`applicable=False` 标记 + 权重归一化（不适用维度从分子分母同时剔除）。

### 14.5 Redis 不可用

**问题**：Redis 挂了怎么办？

**解决方案**：所有缓存操作 try/except 后静默返回 None/False，应用正常运行，只是慢一点。

### 14.6 并发评估同一任务

**问题**：多个客户端同时触发同一任务的评估。

**解决方案**：`create_evaluation` 幂等 + Redis SETNX 分布式锁。

---

## 15. 面试高频问答

### Q1：你们的评估体系和 RAGAS 有什么区别？

**A**：RAGAS 只评 RAG 检索质量（4 个指标），我们评 Agent 运行时全链路（6 维 20 个子指标）。RAGAS 是单维度结果评估，我们是多维度过程评估。另外我们支持增量评估、回归检测、多模型共识，这些 RAGAS 都没有。

### Q2：LLM-as-Judge 的评分一致性怎么保证？

**A**：三种机制。第一，显式评分锚点，每个子指标定义 0/25/50/75/100 五档的具体行为描述，LLM 对照锚点打分。第二，多模型共识，用 DeepSeek + GLM + Qwen 独立评分，计算均值和标准差，std < 2.0 表示高一致性。第三，Pydantic Structured Output，强制分数范围 0-100，校验失败自动重试。

### Q3：轨迹压缩是怎么做的？

**A**：4 阶段确定性压缩。第一步重要性过滤，只保留 plan、tool_call、failure 等高价值动作类型。第二步 Think 截断，将 think 步骤截断到 200 字符。第三步滑动窗口，保留最近 30 步加锚点步骤（plan 和 failure 永远保留）。第四步格式化输出。整个过程不调用 LLM，纯确定性，200 步压缩到约 40 步，减少 80% token。

### Q4：为什么用 Redis 但又说可选？

**A**：Redis 用于 LLM 结果缓存、报表聚合缓存和接口限流。但设计上是可选依赖——所有缓存操作都 try/except 后静默返回 None，Redis 不可用时应用正常运行，只是慢一点。这样降低了部署门槛。

### Q5：增量评估是怎么实现的？

**A**：通过 DiffService 对比两个轨迹的差异，然后用一个变化-维度映射表判断哪些维度受影响。比如 plan 变了影响 planning 和 tactical，tool_call 变了影响 tool_use。只重跑受影响的维度，其余直接复用旧分数。通常节省 2/3 评估时间。

### Q6：评估器的 Pydantic Structured Output 是怎么降级的？

**A**：三级降级。首先尝试 with_structured_output（API 级 function calling），如果检测到 "response_format unavailable" 错误就立即降级到 PydanticOutputParser（在 prompt 中注入 JSON Schema），如果还失败就降级到手动 JSON 解析。每级最多重试 3 次。

### Q7：6 个评估器的权重是怎么定的？

**A**：Planning 和 Tactical 各 20% 最高，因为规划和战术决策对 Agent 成功影响最大。Tool Use、Memory、Replan、Retrieval 各 15%。权重可通过配置调整。不适用的维度自动从总分中剔除，权重归一化。

### Q8：多模型共识的成本是多少？

**A**：3 个 provider 并行，耗时与单模型相当（约 15-30s），但 LLM 调用次数是 3 倍。通过 LLM 结果缓存（24h TTL）缓解——相同轨迹重复评估时只调用一次。std < 2.0 时可以只用单模型节省成本。

### Q9：回归检测的阈值是怎么定的？

**A**：不同维度不同敏感度。overall 阈值 -5 分（总分下降 5 分就触发），tool_use 阈值 -8 分，其他维度 -10 分。双重检测：总分下降 OR 任一维度大幅下降。阈值可通过构造函数注入，CI 环境用更紧的阈值。

### Q10：轨迹中的 "幽灵计划" 是什么？

**A**：任务创建时附带的 `{goal, context}` 条目，没有实际计划内容。这些不是真正的规划步骤，评估时需要过滤掉。过滤逻辑是：只有包含 steps、milestones、plan、content 之一的 plan 步骤才被认为是真正的计划。

### Q11：SDK 的三种接入模式有什么区别？

**A**：Instrument 模式零侵入，自动 hook LangChain/LangGraph 的回调。Proxy 模式包装 LLM 调用，适用于非 LangChain 应用。Callback 模式手动调用 collector，完全控制。推荐用 Instrument 模式。

### Q12：Redis 的滑动窗口限流是怎么实现的？

**A**：用 Redis Sorted Set，score 是时间戳。原子 pipeline：zremrangebyscore（删除过期请求）+ zadd（添加当前请求）+ zcard（计数）+ expire（设置 TTL）。Redis 不可用时限流禁用（返回 True, 0）。

### Q13：评估结果的 "Judge Panel" 是什么？

**A**：每个评估记录保存 _judge_raw（LLM 调用的原始 prompt + response + model + latency）。用户可以通过 /judge-raw API 查看评委是怎么打分的，实现评估透明度。

### Q14：怎么验证评估体系的有效性？

**A**：单调递减验证——人为劣化轨迹（逐步删除关键步骤），验证分数单调下降。实测 93.1 → 20.0，证明评估体系能区分好坏轨迹。

### Q15：项目中有哪些优雅降级的设计？

**A**：四处。Redis 不可用时缓存操作静默返回 None。Celery 不可用时评估降级为同步执行。Docker 不可用时 tool_use 评估降级为 LLM-only 判断。Reranker 模型不可用时跳过 rerank 返回 RRF 顺序。

---

## 16. 常见陷阱与避坑指南

### 陷阱 1：DeepSeek 不支持 with_structured_output

DeepSeek 全系列模型（chat、reasoner、v4-flash）都不支持 function calling。必须用 PydanticOutputParser 作为主要方案，with_structured_output 只对 GPT-4/Claude 有效。

### 陷阱 2：LLM 缓存键缺少模型名

缓存键必须包含模型名，否则多模型共识会共享同一条缓存记录，导致 std=0 的假象。

```python
cache_key = f"llm:{evaluator_name}:{model_name}:{prompt_hash}"
#                                         ^^^^^^^^^^ 不能省略
```

### 陷阱 3：滑动窗口丢失初始计划

如果不保留锚点步骤，滑动窗口会截断初始计划，导致规划评估器无法工作。PLAN 和 FAILURE 步骤必须永远保留。

### 陷阱 4：Redis 连接池泄漏

使用 async Redis 时必须正确关闭连接池，否则进程退出时会卡住。用 `async with` 或 `try/finally` 确保清理。

### 陷阱 5：PydanticOutputParser 的 format_instructions 必须注入

如果 prompt 模板中没有 `{format_instructions}` 变量，PydanticOutputParser 不会注入 Schema 描述，LLM 就不知道该返回什么格式。每个评估器的 prompt 末尾都需要加 `{format_instructions}`。

### 陷阱 6：SQLite 并发写入

SQLite 在并发写入时会锁表。开发环境用 SQLite 没问题，但生产环境必须切换到 PostgreSQL。

### 陷阱 7：轨迹中的 observation 字段可能为 None

评估器必须处理 `step.observation is None` 的情况，否则格式化时会报错。

---

## 17. 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 评估维度 × 子指标 | 6 × 3~4 = 20 项 | 全链路覆盖 |
| 轨迹动作类型 | 14 种 | Pydantic Schema 约束 |
| SDK 接入模式 | 3 种 | Instrument / Proxy / Callback |
| 单次全评估耗时 | 15-30s | 6 评估器并行 |
| 增量评估耗时 | 5-10s | 只重跑 2-3 个维度 |
| 轨迹压缩率 | ~80% | 200 步 → 40 步 |
| LLM 缓存 TTL | 24h | 相同输入 = 相同输出 |
| 多模型共识开销 | 3x | 并行执行，耗时与单模型相当 |
| 综合分单调递减验证 | 93.1 → 20.0 | 人为劣化验证 |
| 检索基准（Wiki Agent） | Top-1: 75%, MRR: 0.825 | BGE-small-zh + RRF |
