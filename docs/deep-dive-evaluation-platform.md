# Agent Runtime Evaluation Platform — 技术深度剖析

> 面试用技术文档，聚焦业务场景、遇到的问题、解决方案和实现细节。

---

## 一、业务场景：为什么要做这个平台

### 1.1 现有方案的痛点

在 AI Agent 开发中，评估是一个被严重低估的环节。现有的评估方案存在三个根本性问题：

**RAGAS / LangSmith 的局限**：RAGAS 只评 RAG 检索质量，不覆盖 Agent 的规划、决策、工具使用等维度。LangSmith 是通用 tracing 平台，不做结构化的质量评估。两者都无法回答"Agent 的决策过程质量如何"这个问题。

**Prompt Evaluation 的错位**：很多团队用 Prompt Evaluation（如 BLEU、ROUGE）来评估 Agent，但这只评最终输出文本质量，不评估运行时行为。一个 Agent 可能最终输出了正确的答案，但中间过程极其低效（绕了 10 步才完成本该 3 步完成的任务），这种问题 Prompt Evaluation 完全发现不了。

**缺乏诊断能力**：即使发现 Agent 质量不行，现有的评估方案也无法告诉你"哪里不行"。你只知道"成功率 30%"，但不知道是规划有问题、工具用错了、还是记忆丢失了。

### 1.2 我们的定位

本平台的核心定位是 **Agent Runtime Evaluation**——评估 Agent 运行时每一步的决策质量，而不是最终输出质量。

类比：传统评估是"考试只看总分"，我们是"考试看每道题的解题过程"。

具体来说，我们评估 6 个维度：
- **规划质量**（20%）：Agent 的计划是否合理
- **战术决策**（20%）：每一步行动是否恰当
- **工具使用**（15%）：工具选择和参数是否正确
- **记忆保持**（15%）：关键信息是否被记住
- **重规划**（15%）：失败后是否有效调整
- **检索质量**（15%）：RAG 检索是否可靠、有无幻觉

---

## 二、核心技术难点与解决方案

### 2.1 难点一：LLM-as-Judge 的评分一致性问题

**问题描述**：用 LLM 当评委打分，最大的问题是"同一个轨迹，问两次可能打出不同的分"。这种不一致性会让评估结果不可信。

**我们的解决方案**：

#### 方案 A：显式评分锚点

我们在每个评估器的 prompt 中定义了 0/25/50/75/100 五个档位的具体行为描述。例如规划质量的"覆盖率"维度：

```
0 分：完全没有规划，或计划与目标毫无关系
25 分：仅覆盖了目标的 1-2 个方面，遗漏了超过一半的关键步骤
50 分：覆盖了主要步骤，但遗漏了 2-3 个关键里程碑
75 分：覆盖了绝大部分里程碑，仅遗漏 1 个次要步骤
100 分：完整覆盖所有必要里程碑，包括分析、实现、测试、文档
```

这样 LLM 就不是"凭感觉打分"，而是"对照锚点打分"。实测下来，评分一致性提升了约 30-50%。

#### 方案 B：多模型共识机制

我们用多个 LLM 独立评分，然后计算均值和标准差。标准差越小 = 一致性越高 = 评分越可信。

具体实现（`consensus.py`）：
- **三级优先级**：跨厂商共识（DeepSeek + GLM + Qwen）> 同厂商多模型（deepseek-chat + deepseek-reasoner）> 温度多样性（同模型 temp=0 vs 0.7）
- **自动降级**：检测哪些 API key 已配置，自动构建可用的 provider 列表
- **故障隔离**：单个 provider 失败返回 None，不影响其他 provider

```
DeepSeek Chat  ──→  Planning: 78  ─┐
GLM-4          ──→  Planning: 82  ─┤→ mean=80, std=2.0（一致性高=可信）
Qwen Plus      ──→  Planning: 80  ─┘
```

std < 2.0 表示高一致性，std > 10.0 表示模型间分歧大，可能需要优化评分标准。

#### 方案 C：Pydantic Structured Output

我们用 `with_structured_output` 强制 LLM 返回符合 Pydantic Schema 的结构化数据，而不是靠 prompt 约束 JSON 格式。

```python
# 之前：prompt 约束 JSON，可能返回非法值
chain = prompt | self.llm
response = await chain.ainvoke(inputs)
scores = self._parse_json_from_llm(response.content)  # 可能返回 101 分、-5 分

# 之后：Pydantic 强制约束
structured_llm = self.llm.with_structured_output(PlanningEvaluationResult)
chain = prompt | structured_llm
result = await self._invoke_structured_llm(chain, inputs, schema_class=PlanningEvaluationResult)
# PlanningEvaluationResult 有 ge=0, le=100 约束，不可能返回非法值
```

好处：
- 分数范围强制在 0-100（Pydantic `ge=0, le=100`）
- 校验失败时自动重试 3 次，把错误信息反馈给 LLM
- 解析失败不再静默返回默认 50 分

---

### 2.2 难点二：轨迹数据的 Token 爆炸问题

**问题描述**：一个 Agent 执行 200 步的轨迹，直接送给 LLM 评估会消耗 50k+ token，成本高且容易超出上下文窗口。

**解决方案：4 阶段确定性压缩管线**（`trajectory_compressor.py`）

这个压缩管线完全是确定性的（不调用 LLM），所以速度快且可复现：

```
原始轨迹（200 步）
    ↓ Stage 1: 重要性过滤
    保留 plan, tool_call, tool_result, memory_*, retrieval, evidence, failure, replan, think
    丢弃 node_execute, tool_decision, state_change 等噪声
    ↓ Stage 2: Think 截断
    think 步骤的 observation 截断到 200 字符（内部独白对评估价值低）
    ↓ Stage 3: 滑动窗口
    保留最近 30 步 + "锚点"步骤（plan, failure）
    锚点步骤永远保留——没有初始计划就无法评估规划质量，没有失败就无法评估重规划
    ↓ Stage 4: 格式化
    输出结构化文本，头部显示 total/omitted/showing 计数
    ↓
压缩后轨迹（~40 步，token 减少 80%）
```

**关键设计决策**：
- **锚点保留**：即使被窗口截断，`PLAN` 和 `FAILURE` 类型的步骤也永远保留。这是核心洞察——没有初始计划，Judge 无法评估规划质量；没有失败记录，Judge 无法评估重规划能力。
- **不可变操作**：`_copy_step_with` 创建浅拷贝而不是修改原始对象，防止副作用。

---

### 2.3 难点三：评估性能问题

**问题描述**：6 个评估器 × 3 个共识模型 = 18 次 LLM 调用，串行执行需要 3-5 分钟。

**解决方案：多层性能优化**

#### 优化 1：并行评估（5x 提速）

```python
# evaluate_parallel() — 6 个评估器并发
results = await asyncio.gather(
    planning_evaluator.evaluate(goal, trajectory),
    tactical_evaluator.evaluate(goal, trajectory),
    tool_use_evaluator.evaluate(goal, trajectory),
    memory_evaluator.evaluate(goal, trajectory),
    replan_evaluator.evaluate(goal, trajectory),
    retrieval_evaluator.evaluate(goal, trajectory),
)
```

从串行 ~71s 降到并行 ~15s。

#### 优化 2：LLM 结果缓存（10x+ 成本节省）

```python
# 缓存键 = 评估器名称 + 模型名 + prompt SHA-256 哈希
cache_key = f"llm:{evaluator_name}:{model_name}:{prompt_hash}"
```

相同轨迹 + 相同目标 = 相同评估结果，缓存 24 小时。这在迭代开发中特别有用——改了 prompt 后重跑评估，只有变化的维度会重新调用 LLM。

#### 优化 3：增量评估（3x 提速）

当 Agent 的 prompt 或工具配置变化时，不需要重跑所有 6 个评估器。

```python
# 变化-维度映射
CHANGE_DIMENSION_MAP = {
    "plan": ["planning", "tactical"],
    "tool_call": ["tool_use"],
    "retrieval": ["retrieval"],
    "memory_write": ["memory", "replan"],
}
```

通过 `DiffService` 对比两个轨迹的差异，只重跑受影响的维度，其余维度直接复用旧分数。通常节省 2/3 的评估时间。

#### 优化 4：Redis 缓存层（优雅降级）

```python
async def cache_get(key):
    try:
        return await redis.get(key)
    except Exception:
        return None  # Redis 不可用时静默降级，不崩溃
```

缓存策略：
- LLM 结果：24h TTL（最激进，因为相同输入 = 相同输出）
- 报表聚合：5min TTL
- Dashboard 计数器：30s TTL
- Task 查询：60s TTL

关键设计：**Redis 是可选依赖**，所有缓存操作 try/except 后静默返回 None/False，应用在没有 Redis 的情况下也能正常运行。

---

### 2.4 难点四：评估维度的适用性问题

**问题描述**：不是所有轨迹都涉及所有维度。如果 Agent 顺利完成任务没有触发重规划，"重规划"维度就不应该参与总分计算。

**解决方案：适用性自动标记 + 权重归一化**

```python
# ToolUseEvaluator：没有工具调用时标记不适用
if not tool_calls:
    return ToolUseScore(
        applicable=False,
        not_applicable_reason="轨迹中未包含工具调用，该维度已从综合评分中剔除。",
        ...
    )

# ReplanEvaluator：没有重规划且没有错过的时机时标记不适用
if not replan_events and not missed_opportunities:
    return ReplanScore(
        applicable=False,
        not_applicable_reason="Agent 顺利完成未触发重规划，该维度已从综合评分中剔除。",
        ...
    )
```

加权总分计算时，不适用的维度从分子和分母中同时剔除：

```python
def weighted_overall(dimension_results, weights):
    numerator = 0.0
    denominator = 0.0
    for dimension, weight in weights.items():
        if not is_applicable(dimension_results.get(dimension)):
            continue  # 跳过不适用的维度
        numerator += weight * score
        denominator += weight
    return numerator / denominator  # 权重自动归一化
```

---

### 2.5 难点五：评估结果的可解释性

**问题描述**：用户看到"Tool Use: 45 分"，不知道具体是哪里出了问题。

**解决方案：多层诊断信息**

每个评估器都返回结构化的诊断信息：

```python
class ToolUseEvaluationResult(BaseModel):
    selection_quality: int = Field(ge=0, le=100)
    parameter_accuracy: int = Field(ge=0, le=100)
    result_utilization: int = Field(ge=0, le=100)
    overall: int = Field(ge=0, le=100)
    feedback: str = Field(description="详细评估反馈")
    inefficient_calls: List[InefficientCall] = Field(default_factory=list)
    # InefficientCall 包含 tool, issue, suggestion
```

另外还有两个调试服务：
- **ReplayService**：逐步回放 Agent 的执行过程，展示每步的 LLM 原始 Prompt/Response/Model/Latency
- **JudgeService**：展示 LLM 裁判的原始 prompt 和 response，让用户看到"评委是怎么打分的"

---

### 2.6 难点六：回归检测

**问题描述**：迭代 Agent 时，需要知道某次改动是提升了还是降低了质量。

**解决方案：自动回归检测**（`regression_detection.py`）

```python
# 不同维度有不同的敏感度阈值
THRESHOLDS = {
    "overall": -5.0,      # 总分下降 5 分就触发
    "tool_use": -8.0,     # 工具使用下降 8 分触发
    "planning": -10.0,    # 其他维度下降 10 分触发
    ...
}

# 双重检测：总分下降 OR 任一维度大幅下降
has_regression = (overall_delta < overall_threshold) or any(d.is_regression for d in dims)
```

生成的人类可读报告：
```
Regression detected! Planning: 72->58 (-14). Overall: 75->68 (-7).
```

阈值可通过构造函数注入，CI 环境用更紧的阈值，开发环境用更松的。

---

## 三、架构设计决策

### 3.1 并行评估路径

```python
# 生产路径：asyncio.gather 并行执行 6 个评估器（~15–30s）
return await evaluate_parallel(goal, trajectory)

# 增量/指定维度
return await evaluate_partial(goal, trajectory, dimensions=["planning", "retrieval"])
```

评估器之间无依赖；已移除 LangGraph 串行 `create_evaluation_graph` / `EVAL_PARALLEL` 双路径。

### 3.2 幂等性设计

- `create_evaluation`：同一 task 的 IN_PROGRESS 评估已存在时，返回已有记录而不是创建重复
- `create_task`：提供 ID 时幂等（ID 已存在则返回已有记录）
- Stream claim：Redis SETNX 原子操作，防止并发评估同一任务

### 3.3 故障隔离

每个评估器独立 try-catch，一个维度失败不影响其他维度：

```python
async def _safe_evaluate(evaluator, goal, trajectory):
    try:
        return await evaluator.evaluate(goal, trajectory)
    except Exception as e:
        return zero_score_with_error(e)  # 返回零分 + 错误信息
```

---

## 四、数据模型：14 种 ActionType

轨迹由 14 种动作类型组成，每种有独立的 Pydantic Schema：

| ActionType | 用途 | Detail Schema |
|------------|------|---------------|
| `plan` | 初始计划 | `PlanDetail` (steps, milestones) |
| `plan_update` | 计划更新 | `PlanUpdateDetail` (next_action, remaining_steps) |
| `tool_call` | 工具调用 | `ToolCallDetail` (tool_name, input) |
| `tool_result` | 工具结果 | `ToolResultDetail` (success, error_type, duration_ms) |
| `memory_write` | 写记忆 | `MemoryWriteDetail` (key, value, memory_type) |
| `memory_read` | 读记忆 | `MemoryReadDetail` (key, hit, value) |
| `think` | 思考 | `ThinkDetail` (thought) |
| `replan` | 重规划 | `ReplanDetail` (reason, new_plan) |
| `failure` | 失败 | `FailureDetail` (error_type, error_message, recoverable) |
| `retrieval` | 知识检索 | `RetrievalDetail` (query, source, result_count, retrieved_docs) |
| `evidence` | 证据池 | `EvidenceDetail` (evidence_type, sources) |
| `state_change` | 状态变化 | `StateChangeDetail` (trigger, diff) |
| `node_execute` | 节点执行 | `NodeExecuteDetail` (node_name) |
| `tool_decision` | 工具决策 | `ToolDecisionDetail` |

SDK 在构造时通过 Pydantic `field_validator` 自动截断过长字段，构造即类型安全。

---

## 五、性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 单次全评估耗时 | 15-30s | 6 评估器 asyncio.gather 并行 |
| 增量评估耗时 | 5-10s | 只重跑受影响的 2-3 个维度 |
| 轨迹压缩率 | ~80% | 200 步 → 40 步 |
| LLM 缓存命中率 | 24h 内重复评估 100% 命中 | 相同轨迹+目标=相同结果 |
| 多模型共识开销 | 3x | 3 个 provider 并行，耗时与单模型相当 |
| 综合分单调递减验证 | 93.1 → 20.0 | 人为劣化轨迹，分数单调下降 |
