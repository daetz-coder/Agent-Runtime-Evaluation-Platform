# Q042: 代码注释写「LangGraph 并行评估」，但实际图是串行的；生产环境却用 `asyncio.gather` 并行。请解释这个「双路径」设计的原因。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q042 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★★★ |

## 问题

代码注释写「LangGraph 并行评估」，但实际图是串行的；生产环境却用 `asyncio.gather` 并行。请解释这个「双路径」设计的原因。

## 参考答案

本平台的评估工作流存在两条执行路径：一条是基于 LangGraph `StateGraph` 的串行图，另一条是基于 `asyncio.gather` 的并行函数。这不是设计矛盾，而是针对不同场景的有意选择。理解这个"双路径"设计需要从 LangGraph 的状态合并机制说起。

**1. LangGraph StateGraph 为何必须串行**

`create_evaluation_graph`（`app/graphs/evaluation_graph.py:374-419`）构建的 `StateGraph` 使用 `EvaluationState`（第 50-69 行）作为共享状态类型。这是一个 `TypedDict`，包含 6 个评估维度的分数字段（`planning_score`、`tactical_score`、`tool_use_score` 等）。

LangGraph 的 `StateGraph` 在每个节点边界执行状态合并（state merge）：当前节点返回一个状态字典，LangGraph 将其与已有状态合并后传递给下一个节点。这个机制在串行场景下工作良好——每个节点读取完整状态、写入自己的字段、LangGraph 合并后传递给下一个节点。

但当 6 个评估节点并发执行时，问题出现了：每个节点都会返回一个包含自己维度分数的状态字典（如 `evaluate_planning` 返回 `{"planning_score": ...}`，第 125 行），LangGraph 的状态合并机制无法正确处理多个节点同时写入不同字段的情况。虽然从理论上讲不同节点写入的 key 不冲突，但 LangGraph 的当前实现（截至编写时）并不支持真正的 fan-out/fan-in 并发模式——它期望节点按顺序依次执行，每个节点基于前一个节点的完整输出产生新的状态。

代码注释明确说明了这一点（第 406 行）：

```python
# After validation, run evaluations sequentially to avoid state conflicts
```

因此，图的边被设计为严格串行链（第 407-413 行）：

```python
workflow.add_edge("validate_input", "evaluate_planning")
workflow.add_edge("evaluate_planning", "evaluate_tactical")
workflow.add_edge("evaluate_tactical", "evaluate_tool_use")
workflow.add_edge("evaluate_tool_use", "evaluate_memory")
workflow.add_edge("evaluate_memory", "evaluate_replan")
workflow.add_edge("evaluate_replan", "evaluate_retrieval")
workflow.add_edge("evaluate_retrieval", "aggregate_results")
```

**2. `evaluate_parallel` 绕过 LangGraph 直接并发**

为了获得并行加速，平台实现了独立的 `evaluate_parallel` 函数（`app/graphs/evaluation_graph.py:422-477`）。该函数完全绕过 LangGraph 的 `StateGraph`，直接使用 `asyncio.gather`（第 456 行）并发执行 6 个评估器：

```python
tasks = [
    _eval("planning", PlanningEvaluator),
    _eval("tactical", TacticalEvaluator),
    _eval("tool_use", ToolUseEvaluator),
    _eval("memory", MemoryEvaluator),
    _eval("replan", ReplanEvaluator),
    _eval("retrieval", RetrievalEvaluator),
]
results = await asyncio.gather(*tasks)
```

每个 `_eval` 辅助函数（第 434-446 行）独立实例化评估器、调用 `evaluate()`、捕获异常并返回结果元组。由于每个评估器都是无状态的（每次调用都创建新实例），且它们只读取共享的 `trajectory` 数据而不修改它，因此并发执行不存在竞态条件。

注释标注了性能提升（第 429 行）：

```python
# 比串行快约 5 倍（71s → ~15s）。
```

这 5 倍加速来源于：每个评估器需要调用 LLM（通常 2-10 秒），6 个评估器串行执行总耗时约 60-70 秒，并发执行时总耗时取决于最慢的那个评估器（通常 10-15 秒）。

**3. 生产环境的路径选择**

`EvaluationService.run_evaluation`（`app/services/evaluation_service.py:346-468`）根据配置选择执行路径。第 427 行读取配置：

```python
use_parallel = getattr(settings, "EVAL_PARALLEL", True)  # 默认并行
```

配置默认值定义于 `app/core/config.py:99`：

```python
EVAL_PARALLEL: bool = True
```

当 `use_parallel=True` 时（第 430-448 行），服务直接调用 `evaluate_parallel()`，然后通过 `_build_overall_from_parallel`（第 1005-1031 行）将结果规范化为 `OverallEvaluation` 对象。当 `use_parallel=False` 时（第 449-451 行），服务调用 `create_evaluation_graph().ainvoke(state)` 走 LangGraph 串行路径。

**4. 串行图存在的价值**

既然生产默认用并行，串行图为何还要保留？有三个实际用途：

**调试与开发：** 串行图提供逐步执行的 trace，开发者可以看到每个评估节点的输入状态和输出状态，便于排查评估器问题。LangGraph 内置的可视化工具（如 LangSmith 集成）依赖图结构来展示执行轨迹。

**SSE 流式模式：** 平台支持 SSE（Server-Sent Events）沙箱流式评估模式（`evaluation_service.py:287` 的 `stream_mode` 参数），前端需要按顺序接收每个评估维度的结果。串行图的节点执行顺序天然对应 SSE 事件的推送顺序。

**未来 LangGraph 原生并发支持：** LangGraph 社区正在讨论 fan-out/fan-in 模式的原生支持。当 LangGraph 提供 `add_conditional_edges` 的并发变体或 `Send` API 的稳定版本时，串行图可以原地升级为并发图，而 `evaluate_parallel` 函数可以被废弃，消除双路径的维护成本。

**5. 两条路径的结果一致性**

两条路径产生的评估结果在数学上应该一致——每个评估器的输入（goal、trajectory、context）完全相同，评估逻辑也完全相同。唯一差异在于：串行路径通过 `EvaluationState` TypedDict 传递中间结果，`_with_defaults`（第 90-99 行）会填充缺失字段；并行路径直接收集结果字典，通过 `_build_overall_from_parallel` 规范化。两条路径最终都通过 `weighted_overall`（`app/evaluators/scoring.py:25-44`）计算加权总分，确保一致性。

## 代码依据

- `app/graphs/evaluation_graph.py:50-69` — `EvaluationState` TypedDict，6 个评估维度的分数字段
- `app/graphs/evaluation_graph.py:374-419` — `create_evaluation_graph` 构建串行 StateGraph
- `app/graphs/evaluation_graph.py:406` — 注释 "run evaluations sequentially to avoid state conflicts"
- `app/graphs/evaluation_graph.py:407-413` — 串行边链：validate_input -> evaluate_planning -> ... -> aggregate_results
- `app/graphs/evaluation_graph.py:422-477` — `evaluate_parallel` 独立并发函数，使用 `asyncio.gather`
- `app/graphs/evaluation_graph.py:429` — 注释 "比串行快约 5 倍（71s -> ~15s）"
- `app/graphs/evaluation_graph.py:456` — `results = await asyncio.gather(*tasks)`
- `app/services/evaluation_service.py:427` — `use_parallel = getattr(settings, "EVAL_PARALLEL", True)`
- `app/services/evaluation_service.py:430-448` — 并行路径：调用 `evaluate_parallel()` + `_build_overall_from_parallel`
- `app/services/evaluation_service.py:449-451` — 串行路径：调用 `create_evaluation_graph().ainvoke(state)`
- `app/core/config.py:99` — `EVAL_PARALLEL: bool = True` 默认并行
- `app/evaluators/scoring.py:25-44` — `weighted_overall` 两条路径共用的加权总分计算

## 回答要点

- LangGraph StateGraph 的状态合并机制不支持多个节点并发写入不同字段，因此评估图必须设计为串行
- `evaluate_parallel` 完全绕过 LangGraph，使用 `asyncio.gather` 直接并发执行 6 个评估器，获得约 5 倍加速（71s -> ~15s）
- 生产环境默认 `EVAL_PARALLEL=True`，走并行路径；串行图保留用于调试、SSE 流式模式和未来 LangGraph 原生并发支持
- 每个评估器是无状态的（每次创建新实例），只读共享 trajectory 数据，并发执行无竞态条件
- 两条路径的评估结果在数学上一致，最终都通过 `weighted_overall` 计算加权总分
- `asyncio.gather` 中单个评估器失败不影响其他评估器（`_eval` 辅助函数捕获异常返回 None）

## 常见追问

**Q: 既然 `evaluate_parallel` 不用 LangGraph，为什么还叫它在 `evaluation_graph.py` 里？**

A: 历史原因和模块组织。`evaluate_parallel` 最初是从串行图的节点逻辑中抽取出来的，两者共享相同的评估器类和评分逻辑。放在同一个模块中便于维护一致性——当新增评估维度时，开发者只需在一个文件中同时更新串行图和并行函数。如果未来 LangGraph 支持原生并发，`evaluate_parallel` 可以被废弃，串行图升级为并发图，迁移成本最低。

**Q: `asyncio.gather` 如果某个评估器超时怎么办？**

A: 当前实现中没有单个评估器的超时控制——`asyncio.gather` 会等待所有任务完成。如果某个评估器的 LLM 调用卡住（如 API 端点无响应），整个评估会一直等待。可以通过 `asyncio.wait_for` 或 `asyncio.gather(return_exceptions=True)` 添加超时保护，但这会增加复杂度。当前的兜底方案是：每个评估器的 `_invoke_llm_cached`（`app/evaluators/base.py:294-372`）底层依赖 LangChain 的 HTTP 客户端，通常有默认超时。

**Q: 为什么不用 `concurrent.futures.ThreadPoolExecutor`？**

A: 因为评估器的瓶颈是 LLM API 调用（I/O 密集型），`asyncio.gather` 配合 LangChain 的 `ainvoke` 异步接口可以充分利用事件循环的并发能力，无需线程切换开销。如果用线程池，每个线程都会阻塞在 HTTP 请求上，虽然也能并发，但线程创建和上下文切换的成本高于协程。

**Q: 串行图的 `_with_defaults` 和并行路径的 `_build_overall_from_parallel` 有什么区别？**

A: `_with_defaults`（`app/graphs/evaluation_graph.py:90-99`）为每个维度的 Pydantic 模型填充缺失字段（如 coverage、ordering 等），确保 `PlanningScore(**planning)` 不会因缺少字段而报错。`_build_overall_from_parallel`（`app/services/evaluation_service.py:1005-1031`）则负责将 `evaluate_parallel` 返回的扁平字典规范化为 `OverallEvaluation` 对象，包括计算 overall_score、构建 summary 和 recommendations。两者职责不同，但最终都确保评估结果的结构完整性。

## 相关题目

- [Q040](../answers/Q040-LangGraph状态管理.md)
- [Q043](../answers/Q043-评估器并发安全.md)
- [Q044](../answers/Q044-SSE流式评估.md)
