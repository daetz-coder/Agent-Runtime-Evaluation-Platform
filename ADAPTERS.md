# Agent Evaluation Platform - 适配器使用指南

## 🎯 核心理念

**可插拔、零侵入、一行集成**

不需要修改原有代码，只需要替换一行即可自动收集轨迹。

---

## 📦 三种集成方式

### 方式 1: LangGraph Adapter（推荐）

适用于使用 LangGraph 构建的 Agent。

```python
# 原来的代码
graph = build_graph()

# 替换为 ↓
from app.adapters.langgraph import instrument_langgraph
graph = instrument_langgraph(build_graph())

# 后续使用完全相同
result = await graph.ainvoke(initial_state)
```

**自动收集：**
- 节点执行记录
- 状态变化
- 工具调用
- LLM 调用

---

### 方式 2: LLM Proxy

适用于任何使用 LangChain 的框架。

```python
# 原来的代码
llm = ChatZhipuAI(...)

# 替换为 ↓
from app.adapters.llm_proxy import create_proxy_llm
llm = create_proxy_llm(ChatZhipuAI(...))

# 后续使用完全相同
response = llm.invoke("Hello")
```

**自动收集：**
- LLM 输入输出
- 工具调用决策
- 响应时间

---

### 方式 3: LangChain Callback

适用于需要更细粒度控制的场景。

```python
from app.adapters.callback import create_callback_handler

# 创建 handler
handler = create_callback_handler()

# 传入 LLM
llm = ChatZhipuAI(callbacks=[handler])

# 或传入 Agent
agent = create_agent(llm, tools, callbacks=[handler])
```

**自动收集：**
- LLM 调用详情
- 工具调用详情
- 链执行详情

---

## 🚀 快速开始

### 1. 启动评估平台

```bash
# 终端 1: 启动后端
cd D:\Agent\Runtime\Evaluation\Platform
python -m app.main

# 终端 2: 启动前端
cd D:\Agent\Runtime\Evaluation\Platform\frontend
npm run dev
```

### 2. 在你的 Agent 中集成

#### LangGraph Agent

```python
# 在 graph.py 或 main.py 中添加
from app.adapters.langgraph import instrument_langgraph

# 替换 build_graph()
graph = instrument_langgraph(build_graph())
```

#### 其他 LangChain Agent

```python
# 在创建 LLM 时
from app.adapters.llm_proxy import create_proxy_llm

llm = create_proxy_llm(ChatZhipuAI(...))
```

### 3. 运行你的 Agent

```bash
python your_agent.py
```

### 4. 查看评估结果

访问 http://localhost:3000 查看评估结果。

---

## 📊 评估维度

| 维度 | 评估内容 |
|------|----------|
| **规划质量** | Agent 的计划是否合理 |
| **战术决策** | 每一步行动是否正确 |
| **工具使用** | 工具调用是否准确 |
| **记忆保持** | 是否记住关键信息 |
| **重规划** | 是否需要重新规划 |

---

## 🔧 配置选项

在 `.env` 中配置：

```env
# 启用/禁用评估
EVAL_ENABLED=true

# 自动收集
EVAL_AUTO_COLLECT=true

# 批量大小
EVAL_BATCH_SIZE=10
```

---

## 💡 示例

### LangGraph Agent 示例

```python
from langgraph.graph import StateGraph, END
from app.adapters.langgraph import instrument_langgraph

# 定义你的 Agent
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("agent", call_agent)
    g.add_node("tools", run_tools)
    g.add_edge("agent", "tools")
    g.add_edge("tools", "agent")
    return g

# 原来的代码
# graph = build_graph()

# 替换为 ↓
graph = instrument_langgraph(build_graph())

# 使用
result = await graph.compile().ainvoke(initial_state)
```

### LLM Proxy 示例

```python
from langchain_community.chat_models import ChatZhipuAI
from app.adapters.llm_proxy import create_proxy_llm

# 原来的代码
# llm = ChatZhipuAI(...)

# 替换为 ↓
llm = create_proxy_llm(ChatZhipuAI(
    model_name="glm-4",
    zhipuai_api_key="your-key",
))

# 使用
response = llm.invoke("Hello")
```

---

## 🎨 工作原理

```
你的 Agent 代码
    │
    ├── instrument_langgraph(graph)
    │   └── 包装所有节点，自动记录执行
    │
    ├── create_proxy_llm(llm)
    │   └── 包装 LLM，自动记录调用
    │
    └── create_callback_handler()
        └── 注入回调，自动记录事件
           │
           ▼
    TrajectoryCollector（收集器）
    - 收集所有轨迹数据
    - 批量上报到后端
           │
           ▼
    评估平台后端
    - 存储轨迹数据
    - 运行评估器
    - 生成评估报告
           │
           ▼
    评估平台前端
    - 可视化展示
    - 分析报告
```

---

## ❓ 常见问题

### Q: 需要修改原有代码吗？

A: **不需要！** 只需要替换一行代码即可。

### Q: 性能影响大吗？

A: **几乎没有影响。** 数据收集和上报都在后台进行。

### Q: 评估平台没有运行怎么办？

A: **不影响 Agent 运行。** 数据会在本地缓存，等平台启动后再上报。

### Q: 可以只收集部分数据吗？

A: **可以。** 通过配置 `EVAL_AUTO_COLLECT=false`，然后手动调用收集方法。

### Q: 支持哪些框架？

A: **支持所有 LangChain 系框架**，包括 LangGraph、LangChain Agent 等。

---

## 📚 相关文档

- [架构设计](docs/architecture.md)
- [API 文档](docs/api.md)
- [评估器说明](app/evaluators/README.md)
