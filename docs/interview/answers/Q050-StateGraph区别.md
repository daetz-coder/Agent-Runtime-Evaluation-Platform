# Q050: LangGraph 的 `StateGraph` 和 `CompiledStateGraph` 区别是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q050 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★★ |

## 问题

LangGraph 的 `StateGraph` 和 `CompiledStateGraph` 区别是什么？

## 参考答案

`StateGraph` 和 `CompiledStateGraph` 是 LangGraph 中图的两个生命周期阶段，分别对应"构建期"和"运行期"。

**StateGraph 是构建器（Builder）**。它提供 `add_node()`、`add_edge()`、`add_conditional_edges()`、`set_entry_point()` 等方法，用于声明式地定义工作流拓扑。此时图只是一张蓝图，节点函数尚未被校验，边也未被检查是否存在环或悬空引用。在本项目中，`create_evaluation_graph()`（`evaluation_graph.py:374-419`）先创建 `StateGraph(EvaluationState)`（第 391 行），然后依次添加 8 个节点（第 394-401 行）和定义边（第 404-416 行）。

**CompiledStateGraph 是编译产物**。调用 `StateGraph.compile()` 后返回 `CompiledStateGraph` 实例（第 419 行），它具备以下特性：(1) 拓扑已校验——确保无悬空节点、入口已设置；(2) 执行顺序已优化——内部确定节点调度策略；(3) 提供 `.invoke()` 和 `.ainvoke()` 方法，可直接传入初始状态执行整个图。

**可变性区别**：StateGraph 在构建阶段可反复修改（增删节点和边），而 CompiledStateGraph 是不可变的——编译后不能再添加节点。如需修改，必须回到 StateGraph 重新构建并再次 compile。

**SDK 包装层**：本项目的 SDK 为两种类型分别提供了透明包装器。`InstrumentedStateGraph`（`sdk/adapters/langgraph.py:66-309`）拦截 `add_node()` 调用（第 105-111 行），在每个节点函数外包裹一层 instrumentation 逻辑，自动记录 `node_execute`、`state_change`、`failure` 等事件。`InstrumentedCompiledGraph`（第 312-375 行）则包装 `ainvoke()` 和 `invoke()` 方法（第 321-371 行），在图执行前后记录 THINK 事件，并捕获执行异常。`instrument_langgraph()` 函数（第 378-410 行）通过 `isinstance` 检查类型，自动分发到对应的包装器。

总结：StateGraph 是"画图纸"，CompiledStateGraph 是"造好的机器"。前者定义结构，后者执行逻辑。

## 代码依据

- `app/graphs/evaluation_graph.py:391` — `workflow = StateGraph(EvaluationState)` 创建构建器
- `app/graphs/evaluation_graph.py:394-401` — add_node 添加 8 个节点
- `app/graphs/evaluation_graph.py:404-416` — add_edge / set_entry_point 定义拓扑
- `app/graphs/evaluation_graph.py:419` — `return workflow.compile()` 编译为 CompiledStateGraph
- `sdk/adapters/langgraph.py:66-309` — InstrumentedStateGraph 包装构建期
- `sdk/adapters/langgraph.py:105-111` — 拦截 add_node() 包装节点 runnable
- `sdk/adapters/langgraph.py:312-375` — InstrumentedCompiledGraph 包装运行期
- `sdk/adapters/langgraph.py:321-345` — 包装 ainvoke() 记录 THINK 事件
- `sdk/adapters/langgraph.py:378-410` — instrument_langgraph 类型分发

## 回答要点

- StateGraph 是构建器，提供 add_node/add_edge 等方法定义拓扑蓝图
- CompiledStateGraph 是 compile() 的返回值，提供 invoke/ainvoke 执行方法
- StateGraph 可变（可增删节点），CompiledStateGraph 不可变
- SDK 为两者分别提供 InstrumentedStateGraph 和 InstrumentedCompiledGraph 透明包装
- instrument_langgraph() 通过 isinstance 检查自动选择包装器

## 常见追问

**Q: 为什么不直接在 CompiledStateGraph 上包装节点？**

A: 因为 compile() 之后节点已经固化，无法再替换其 runnable。`InstrumentedStateGraph` 必须在构建阶段拦截 `add_node()`（第 105-111 行），在 LangGraph 创建 `StateNodeSpec` 后、compile 之前，将 spec 中的 runnable 替换为带 instrumentation 的包装版本。这是唯一能在编译前注入监控逻辑的时间窗口。

**Q: 如果传入一个已经 compile 过的图给 instrument_langgraph 会怎样？**

A: `instrument_langgraph()`（第 378-410 行）会检测到它是 `CompiledStateGraph` 实例，返回 `InstrumentedCompiledGraph` 包装器。此时无法再包装单个节点，只能在 `ainvoke()`/`invoke()` 级别记录整体执行的开始、结束和异常。

## 相关题目

- [Q040](../answers/Q040-评估工作流.md)
- [Q054](../answers/Q054-LLM-as-Judge.md)
