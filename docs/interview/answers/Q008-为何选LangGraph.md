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
