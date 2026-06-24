# Q8: 为什么选择 LangGraph 而不是纯 LangChain AgentExecutor、AutoGen、CrewAI？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q008 |
| 分类 | 项目理解与动机 |
| 难度 | ★★ |

## 问题

为什么选择 LangGraph 而不是纯 LangChain AgentExecutor、AutoGen、CrewAI？

## 参考答案

LangGraph 提供 StateGraph、checkpoint、interrupt、条件边，适合 Wiki Agent 与评估 workflow 编排。evaluation_graph.py 用 StateGraph 串行六节点（注释说明并行用 evaluate_parallel + asyncio.gather）。相比 AgentExecutor 单链、AutoGen 对话式、CrewAI 角色分工，LangGraph 节点级可观测与 adapter 包装更自然：sdk/adapters/langgraph.py 的 instrument_langgraph 透明包装节点记录 NODE_EXECUTE。评估侧与 Agent 侧可共用 LangGraph 生态。

>我选择 LangGraph，主要是因为这个项目不是普通聊天 Agent，而是 Agent Runtime Evaluation 平台。它需要显式状态、条件边、checkpoint、节点级可观测和低侵入埋点。LangGraph 的 StateGraph 能很好地表达 Agent 的执行状态机，也方便把每个节点包装成可记录的 `NODE_EXECUTE`。相比之下，AgentExecutor 更偏单链执行，AutoGen 更偏多 Agent 对话，CrewAI 更偏角色任务协作，它们都可以作为被评估对象接入，但不如 LangGraph 适合作为平台内部的标准编排框架。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `sdk/adapters/langgraph.py`
- `app/wiki_agent/agent/graph.py`

## 回答要点

- StateGraph + checkpoint 适合长会话 Wiki
- instrument_langgraph 低侵入埋点
- 评估图与 Agent 图分离但技术栈统一
- evaluate_parallel 生产路径用 gather 而非图并行

## 常见追问

**Q: 为什么评估图串行？**

A: LangGraph state merge 冲突；生产用 evaluate_parallel。

**Q: AutoGen 呢？**

A: 多 Agent 对话轨迹 schema 难统一，需额外 adapter。

## 相关题目

- [Q007](../answers/Q007-Wiki-Agent角色.md)
- [Q009](../answers/Q009-为何选FastAPI.md)
