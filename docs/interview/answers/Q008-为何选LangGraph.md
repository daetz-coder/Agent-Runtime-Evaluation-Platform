# Q008: 为什么选择 LangGraph 而不是纯 LangChain AgentExecutor、AutoGen、CrewAI？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q008 |
| 分类 | 项目理解与动机 |
| 难度 | ★★ |

## 问题

为什么选择 LangGraph 而不是纯 LangChain AgentExecutor、AutoGen、CrewAI？

## 参考答案

选择 LangGraph 的核心原因是它将 agent 执行流程显式建模为有向图（节点 + 边），而非隐藏在 AgentExecutor 的黑盒循环中。这对「轨迹驱动评估」平台至关重要。

**显式状态管理。** LangGraph 的 `StateGraph` 要求开发者用 `TypedDict` 定义状态结构，每个节点以 `(state) -> state_delta` 的形式读写状态。在 `app/agent_runtime/graph.py:205` 中，`AgentState` 明确声明了 `messages`、`current_step`、`done`、`final_answer` 等字段。这种显式声明让轨迹记录变得自然——每个节点的输入输出就是状态快照，无需从黑盒 agent 中反向推断。

**拓扑可见性。** `app/agent_runtime/graph.py:208-211` 展示了 `add_conditional_edges` 的用法：`think_and_act` 节点根据 `done` 状态决定是回到自身还是终止。评估器（如 `app/graphs/evaluation_graph.py:374-419`）同样用 StateGraph 建模 6 维评估流程。这种拓扑可见性是 AgentExecutor 不提供的——后者只有一个隐式的 `while not done` 循环。

**Checkpoint 与 human-in-the-loop。** LangGraph 内置 `AsyncSqliteSaver` checkpoint 机制，Wiki Agent 利用它实现了对话中断与恢复（interrupt/resume），这是 AutoGen 和 CrewAI 都需要额外实现的能力。

**LangChain 生态兼容。** LangGraph 原生集成 LangChain 的 LLM、Tool、Callback 体系。`sdk/adapters/callback.py` 中的 `EvalCallbackHandler` 可以直接挂载到 LangGraph 节点调用的 LLM 上，无需适配层。

**权衡：** LangGraph 的 `StateGraph` 在并行节点场景下存在状态合并限制（参见 Q042 双路设计）。`app/graphs/evaluation_graph.py:422-477` 的 `evaluate_parallel` 就是绕过 StateGraph、直接用 `asyncio.gather` 实现并行评估的例子。但总体而言，LangGraph 的拓扑可见性、checkpoint 能力和生态兼容性远超这一限制带来的影响。

## 代码依据

- `app/agent_runtime/graph.py:205` — `StateGraph(AgentState)` 用 TypedDict 定义 agent 状态
- `app/agent_runtime/graph.py:208-211` — `add_conditional_edges` 实现 ReAct 循环的条件跳转
- `app/graphs/evaluation_graph.py:374-419` — 评估工作流同样以 StateGraph 建模
- `app/graphs/evaluation_graph.py:422-477` — `evaluate_parallel` 绕过 StateGraph 用 asyncio.gather
- `app/wiki_agent/agent/graph.py` — Wiki Agent 使用 LangGraph checkpoint（AsyncSqliteSaver）

## 回答要点

- LangGraph 的 StateGraph 将 agent 流程显式建模为节点+边，拓扑可见，方便轨迹埋点
- TypedDict 状态声明使节点输入输出透明，天然适合轨迹记录
- Checkpoint 机制（AsyncSqliteSaver）支持 human-in-the-loop（中断/恢复）
- 原生兼容 LangChain 生态（LLM/Tool/Callback），SDK adapter 即插即用
- 已知限制：StateGraph 并行状态合并能力弱，项目用 asyncio.gather 补充

## 常见追问

**Q: 如果 AgentExecutor 也能跑 ReAct，为什么不直接用它？**

A: AgentExecutor 内部是一个 `while not done` 黑盒循环，我们无法在循环中间插入 checkpoint 或条件分支。LangGraph 的 `add_conditional_edges`（graph.py:208）让每一步的路由逻辑都是显式的，评估器可以精确知道 agent 在第几步做了什么决策。

**Q: AutoGen 的 multi-agent 对话模型不是更适合复杂场景吗？**

A: AutoGen 擅长多 agent 协作对话，但本项目的核心是「评估单个 agent 的轨迹质量」，不需要多 agent 协调。而且 AutoGen 不提供 LangChain 原生的 Callback 接口，我们的 `EvalCallbackHandler` 无法直接复用。

## 相关题目

- [Q042](../answers/Q042-评估并行化与状态合并.md)
- [Q025](../answers/Q025-两套collector对比.md)
