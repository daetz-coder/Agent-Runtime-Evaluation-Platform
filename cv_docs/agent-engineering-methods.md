# Agent Engineering 方法综述：区别、联系与选型指南

> 本文档系统梳理当前主流的 Agent 工程方法，分析其核心思想、架构差异、适用场景及相互关系。

---

## 目录

1. [概述](#1-概述)
2. [核心方法详解](#2-核心方法详解)
   - 2.1 [Chain of Thought (CoT)](#21-chain-of-thought-cot)
   - 2.2 [ReAct (Reasoning + Acting)](#22-react-reasoning--acting)
   - 2.3 [Plan-and-Execute](#23-plan-and-execute)
   - 2.4 [Reflexion](#24-reflexion)
   - 2.5 [Tool Use / Function Calling](#25-tool-use--function-calling)
   - 2.6 [Tree of Thoughts (ToT)](#26-tree-of-thoughts-tot)
   - 2.7 [LATS (Language Agent Tree Search)](#27-lats-language-agent-tree-search)
   - 2.8 [Multi-Agent Systems](#28-multi-agent-systems)
   - 2.9 [Cognitive Architecture (认知架构)](#29-cognitive-architecture-认知架构)
3. [方法对比矩阵](#3-方法对比矩阵)
4. [方法之间的关系图谱](#4-方法之间的关系图谱)
5. [工程框架与方法的映射](#5-工程框架与方法的映射)
6. [选型指南](#6-选型指南)
7. [发展趋势](#7-发展趋势)

---

## 1. 概述

**Agent Engineering** 是指围绕大语言模型（LLM）构建具备自主决策、工具调用、环境交互能力的智能体的工程方法论。不同于传统的 prompt engineering 侧重单轮/多轮对话优化，Agent Engineering 关注的是：

- **行动循环**（Perception → Reasoning → Action → Feedback）
- **外部工具集成**（API、数据库、代码执行等）
- **任务分解与规划**（将复杂目标拆解为可执行步骤）
- **自我修正与学习**（从错误中恢复并改进策略）

### 1.1 从 Prompt Engineering 到 Agent Engineering 的演进

```
Prompt Engineering  →  Chain of Thought  →  ReAct  →  Plan-and-Execute  →  Multi-Agent
     (静态输入)         (推理增强)        (推理+行动)     (规划+执行分离)       (协作智能体)
```

每一阶段都在前一阶段的基础上增加了新的能力维度。

---

## 2. 核心方法详解

### 2.1 Chain of Thought (CoT)

**论文**: *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models* (Wei et al., 2022)

**核心思想**: 通过在 prompt 中引导模型"逐步思考"，将复杂推理分解为中间步骤，显著提升数学、逻辑、常识推理等任务的准确率。

**工作流程**:

```
输入问题 → [思考步骤1] → [思考步骤2] → ... → [最终答案]
```

**关键特征**:
- **纯推理**：不涉及外部工具调用或环境交互
- **静态执行**：步骤在一次生成中完成，无动态决策
- **Prompt 驱动**：通过 few-shot 示例或指令引导模型输出推理链

**变体**:
| 变体 | 特点 |
|------|------|
| Zero-shot CoT | 仅添加"Let's think step by step" |
| Few-shot CoT | 提供带推理过程的示例 |
| Auto-CoT | 自动生成推理示例 |
| Self-Consistency | 多条推理路径投票选最优 |

**适用场景**: 数学推理、逻辑题、分类解释、单步知识问答

**局限**: 无法与外部世界交互；错误在推理链中会累积传播

---

### 2.2 ReAct (Reasoning + Acting)

**论文**: *ReAct: Synergizing Reasoning and Acting in Language Models* (Yao et al., 2022)

**核心思想**: 将推理（Thought）和行动（Action）交替进行，形成 **Thought → Action → Observation** 的循环。模型在每一步既可以思考当前状态，也可以调用外部工具获取新信息。

**工作流程**:

```
Thought: 我需要查找X的信息
Action: search("X的相关信息")
Observation: [搜索结果]
Thought: 根据结果，我还需要...
Action: lookup("具体细节")
Observation: [查找结果]
Thought: 现在我可以回答了
Action: finish("最终答案")
```

**关键特征**:
- **推理与行动交织**：每一步都可选择思考或行动
- **环境反馈驱动**：Observation 来自真实工具返回，引导后续推理
- **轨迹可追踪**：Thought 提供了决策的可解释性
- **单 Agent 模式**：由一个 Agent 完成所有工作

**与 CoT 的区别**:

| 维度 | CoT | ReAct |
|------|-----|-------|
| 外部交互 | 无 | 有（工具调用） |
| 信息来源 | 仅模型内部知识 | 内部知识 + 外部实时数据 |
| 错误修正 | 无法修正 | 可根据 Observation 调整 |
| 适用范围 | 封闭推理任务 | 需要外部信息的开放任务 |

**适用场景**: 问答系统、信息检索增强、代码调试、数据分析

**局限**: 单步决策可能缺乏全局规划；长任务中容易偏离目标

---

### 2.3 Plan-and-Execute

**论文**: *Plan-and-Solve Prompting* (Wang et al., 2023) 及 LangChain 实践

**核心思想**: 将任务分为 **规划阶段（Planner）** 和 **执行阶段（Executor）** 两个明确分离的模块。Planner 生成高层计划，Executor 逐步执行并可选择性地请求计划调整。

**工作流程**:

```
用户目标
    ↓
[Planner] → 生成计划: [Step1, Step2, Step3, ...]
    ↓
[Executor] → 执行 Step1 → 结果1
[Executor] → 执行 Step2 → 结果2
[Executor] → 执行 Step3 → 结果3
    ↓
[可选: Re-planner] → 根据执行结果调整后续计划
    ↓
最终输出
```

**架构模式**:

```python
# 典型的 Plan-and-Execute 架构
class PlanAndExecuteAgent:
    def __init__(self):
        self.planner = LLM(role="planner")      # 负责生成计划
        self.executor = LLM(role="executor")    # 负责执行步骤
        self.replanner = LLM(role="replanner")  # 负责计划调整

    def run(self, goal):
        plan = self.planner.generate(goal)
        results = []
        for step in plan:
            result = self.executor.execute(step, context=results)
            results.append(result)
            if self.needs_replan(result):
                plan = self.replanner.adjust(plan, results)
        return synthesize(results)
```

**与 ReAct 的关键区别**:

| 维度 | ReAct | Plan-and-Execute |
|------|-------|-------------------|
| 规划方式 | 隐式（每步即时决策） | 显式（预先生成全局计划） |
| 全局视野 | 弱（贪心式推进） | 强（有全局计划指导） |
| 适用任务复杂度 | 中低复杂度 | 高复杂度、多步骤任务 |
| 灵活性 | 高（随时可改变方向） | 中（需通过 Re-planner 调整） |
| Token 消耗 | 较低 | 较高（需多次 LLM 调用） |

**适用场景**: 复杂研究任务、多步骤数据处理、项目管理类任务、需要长期规划的场景

**局限**: 初始计划质量影响全局；Re-planning 的开销较大

---

### 2.4 Reflexion

**论文**: *Reflexion: Language Agents with Verbal Reinforcement Learning* (Shinn et al., 2023)

**核心思想**: 引入 **自我反思（Self-Reflection）** 机制。Agent 在完成任务后，由一个 **Evaluator** 评估结果，失败时生成 **自然语言反思**，将反思存入记忆，在下次尝试时利用这些反思避免重复犯错。

**工作流程**:

```
尝试1: 执行任务 → 失败 → [Reflector] 生成反思: "我在X步骤犯了Y错误，应该Z"
尝试2: 带着反思记忆重新执行 → 失败 → [Reflector] 生成新的反思
尝试3: 带着所有反思记忆重新执行 → 成功
```

**核心组件**:

```
┌─────────────────────────────────────────┐
│              Reflexion Loop              │
│                                          │
│  Actor ──→ Evaluator ──→ Reflector      │
│    ↑           │             │           │
│    │        判断成功/失败    生成反思       │
│    │             ↓             ↓         │
│    └─────── Memory (反思记忆库) ←────────┘
│                                          │
└─────────────────────────────────────────┘
```

**与 ReAct 的区别**:

| 维度 | ReAct | Reflexion |
|------|-------|-----------|
| 学习机制 | 无（每次独立） | 从失败中学习 |
| 记忆 | 仅当前任务上下文 | 跨尝试的反思记忆 |
| 重试策略 | 盲目重试 | 带反思指导的重试 |
| 适用场景 | 单次执行 | 需要迭代改进的任务 |

**适用场景**: 代码生成与调试、游戏策略优化、复杂推理任务、需要试错的探索性任务

**局限**: 需要多次尝试，成本高；反思质量依赖 Evaluator 能力

---

### 2.5 Tool Use / Function Calling

**代表**: OpenAI Function Calling、Anthropic Tool Use、Google Gemini Function Calling

**核心思想**: 将外部工具（函数）的定义以结构化 schema 的形式提供给 LLM，由模型决定何时调用哪个工具、传入什么参数，系统执行后将结果返回给模型。

**工作流程**:

```
用户请求
    ↓
LLM 分析意图 → 选择工具 → 生成参数 (JSON)
    ↓
系统执行工具调用
    ↓
工具返回结果 → LLM 整合结果 → 回复用户
```

**工具定义示例**:

```json
{
  "name": "get_weather",
  "description": "获取指定城市的天气信息",
  "parameters": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string",
        "description": "城市名称"
      },
      "unit": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"]
      }
    },
    "required": ["city"]
  }
}
```

**与其他方法的关系**:
- Tool Use 是 ReAct 中 **Action** 的具体实现形式
- Plan-and-Execute 的 Executor 通过 Tool Use 完成具体步骤
- Multi-Agent 之间通过 Tool Use 进行通信

**适用场景**: API 集成、数据查询、自动化工作流、企业系统对接

**局限**: 工具选择依赖 prompt 质量；复杂工具链需要精心编排

---

### 2.6 Tree of Thoughts (ToT)

**论文**: *Tree of Thoughts: Deliberate Problem Solving with Large Language Models* (Yao et al., 2023)

**核心思想**: 将推理过程从线性链扩展为 **树状结构**。每一步可以生成多个候选思路，通过评估函数选择最优路径，支持回溯。

**工作流程**:

```
           初始问题
          /   |   \
      思路A  思路B  思路C    ← 候选生成
        |     |      |
      评估   评估   评估     ← 价值评估
        ↓            ↓
      思路A1      思路C1     ← 选择扩展
        |            |
      评估         评估
        ↓            ↓
      最终答案    (丢弃)
```

**搜索策略**:
- **BFS（广度优先）**: 探索所有思路的当前层
- **DFS（深度优先）**: 深入探索最有前途的路径
- **Beam Search**: 维护固定数量的候选路径

**与 CoT 的对比**:

| 维度 | CoT | ToT |
|------|-----|-----|
| 推理结构 | 线性链 | 树状 |
| 探索方式 | 单路径 | 多路径并行探索 |
| 回溯能力 | 无 | 有 |
| 计算成本 | 低 | 高（多次 LLM 调用） |
| 适用问题 | 中等复杂度 | 需要全局搜索的复杂问题 |

**适用场景**: 创意写作、数学证明、策略规划、需要探索多种可能性的问题

---

### 2.7 LATS (Language Agent Tree Search)

**论文**: *Language Agent Tree Search Unifies Reasoning, Acting, and Planning in Language Models* (Zhou et al., 2023)

**核心思想**: 将 **蒙特卡洛树搜索（MCTS）** 与 LLM Agent 结合。通过模拟、评估、回溯的循环，统一了推理、行动和规划。

**工作流程**:

```
选择 (Selection)  →  扩展 (Expansion)  →  模拟 (Simulation)  →  回溯 (Backpropagation)
     ↑                                                           |
     └───────────────────────────────────────────────────────────┘
```

**与 ReAct 和 ToT 的融合**:

```
LATS = ReAct (行动能力) + ToT (树搜索) + MCTS (价值评估)
```

| 维度 | ReAct | ToT | LATS |
|------|-------|-----|------|
| 行动能力 | ✓ | ✗ | ✓ |
| 树搜索 | ✗ | ✓ | ✓ |
| 价值评估 | ✗ | LLM 评估 | MCTS + LLM |
| 回溯 | ✗ | ✓ | ✓ |
| 规划 | 隐式 | 显式 | 显式 |

**适用场景**: 复杂决策问题、需要多步规划与行动的任务、代码生成与优化

---

### 2.8 Multi-Agent Systems

**代表框架**: AutoGen、CrewAI、MetaGPT、LangGraph Multi-Agent

**核心思想**: 由多个具有不同角色、能力的 Agent 协作完成任务。每个 Agent 专注于特定子任务，通过通信协议协调行动。

**架构模式**:

#### 模式一：层级式（Hierarchical）

```
            ┌─────────┐
            │ Manager  │  ← 协调者，分配任务
            └────┬────┘
           ┌─────┼─────┐
           ↓     ↓     ↓
        AgentA AgentB AgentC  ← 执行者
```

#### 模式二：对等式（Peer-to-Peer）

```
        AgentA ←→ AgentB
           ↕         ↕
        AgentC ←→ AgentD
```

#### 模式三：辩论式（Debate）

```
        AgentA ──论点──→ AgentB
            ↑               |
            └──反驳─────────┘
                  ↓
            Moderator 裁决
```

**多 Agent 通信模式**:

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| 请求-响应 | Agent A 向 Agent B 发送请求 | 工具调用式协作 |
| 发布-订阅 | Agent 广播消息，相关 Agent 订阅 | 事件驱动系统 |
| 共享黑板 | 所有 Agent 读写共享状态 | 需要全局协调的场景 |
| 辩论 | Agent 互相质疑、论证 | 需要多角度验证的决策 |

**与单 Agent 方法的对比**:

| 维度 | 单 Agent | Multi-Agent |
|------|----------|-------------|
| 任务分解 | Agent 内部隐式分解 | 显式分配给不同角色 |
| 专业化 | 一个 Agent 兼顾所有能力 | 每个 Agent 专注特定能力 |
| 可扩展性 | 受限于单上下文窗口 | 可通过增加 Agent 扩展 |
| 复杂度 | 低 | 高（需管理通信和协调） |
| 成本 | 较低 | 较高（多次 LLM 调用） |

**适用场景**: 软件开发（产品经理+架构师+程序员+测试）、研究团队模拟、复杂工作流自动化

---

### 2.9 Cognitive Architecture (认知架构)

**代表**: SOAR、ACT-R 在 LLM 时代的复兴，以及 OpenAI 的 Swarm、Anthropic 的 Agent 设计模式

**核心思想**: 借鉴认知科学理论，将 Agent 的内部结构分为多个功能模块，模拟人类的认知过程。

**典型架构**:

```
┌──────────────────────────────────────────────────────┐
│                    Agent 认知架构                      │
│                                                       │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐          │
│  │ 感知模块 │───→│ 推理模块 │───→│ 行动模块 │          │
│  │Perception│    │Reasoning │    │  Action  │          │
│  └─────────┘    └────┬────┘    └─────────┘          │
│                      │                                │
│                 ┌────┴────┐                           │
│                 │ 记忆系统 │                           │
│                 │ Memory   │                           │
│                 └─────────┘                           │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐          │
│  │工作记忆  │    │长期记忆  │    │情景记忆  │          │
│  │Working   │    │Long-term │    │Episodic  │          │
│  │Memory    │    │Memory    │    │Memory    │          │
│  └─────────┘    └─────────┘    └─────────┘          │
│                                                       │
│  ┌─────────────────────────────────────────┐         │
│  │ 元认知模块 (Metacognition)               │         │
│  │ - 自我监控  - 策略选择  - 资源分配       │         │
│  └─────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────┘
```

**与前述方法的关系**: 认知架构是一种 **设计框架**，而 ReAct、Reflexion 等是该框架下的 **具体实现策略**。

---

## 3. 方法对比矩阵

### 3.1 核心维度对比

| 方法 | 推理能力 | 行动能力 | 规划能力 | 自我修正 | 多Agent | 记忆 | 复杂度 |
|------|:--------:|:--------:|:--------:|:--------:|:-------:|:----:|:------:|
| CoT | ★★★ | ✗ | ✗ | ✗ | ✗ | ✗ | 低 |
| ReAct | ★★ | ★★★ | ★ | ★ | ✗ | 低 | 低 |
| Plan-and-Execute | ★★ | ★★ | ★★★ | ★★ | ✗ | 中 | 中 |
| Reflexion | ★★ | ★★ | ★ | ★★★ | ✗ | 高 | 中 |
| Tool Use | ★ | ★★★ | ✗ | ✗ | ✗ | 低 | 低 |
| ToT | ★★★ | ✗ | ★★ | ✗ | ✗ | ✗ | 中 |
| LATS | ★★★ | ★★ | ★★★ | ★★ | ✗ | 中 | 高 |
| Multi-Agent | ★★ | ★★ | ★★ | ★ | ★★★ | 中 | 高 |

### 3.2 适用场景对比

| 方法 | 最佳适用场景 | 不适用场景 |
|------|-------------|-----------|
| CoT | 数学推理、逻辑题、分类解释 | 需要外部信息的任务 |
| ReAct | 信息检索问答、简单工具调用 | 需要长期规划的复杂任务 |
| Plan-and-Execute | 多步骤研究、复杂工作流 | 简单的单轮问答 |
| Reflexion | 代码生成调试、策略优化 | 一次性任务、实时响应 |
| Tool Use | API 集成、数据查询 | 纯推理任务 |
| ToT | 创意生成、数学证明 | 实时交互、简单任务 |
| LATS | 复杂决策、代码优化 | 简单任务、低延迟场景 |
| Multi-Agent | 软件开发、研究模拟 | 简单任务、资源受限场景 |

---

## 4. 方法之间的关系图谱

### 4.1 继承与演化关系

```
                    Chain of Thought (CoT)
                    /                    \
                   /                      \
         Self-Consistency           ReAct (推理+行动)
         (多路径推理)               /     |       \
                |                 /      |        \
                ↓               /       |         \
           Tree of Thoughts    /    Tool Use    Reflexion
           (树搜索推理)        /    (工具实现)   (自我反思)
                  \          /         |           |
                   \        /          |           |
                    LATS ──────────────┘           |
              (MCTS + Agent)                       |
                    |                              |
                    ↓                              |
             Plan-and-Execute ←────────────────────┘
             (规划与执行分离)
                    |
                    ↓
             Multi-Agent Systems
             (多智能体协作)
```

### 4.2 组合关系

这些方法并非互斥，实际工程中常常组合使用：

| 组合模式 | 描述 | 示例 |
|----------|------|------|
| ReAct + Reflexion | 带反思的行动循环 | Agent 执行失败后生成反思，改进策略重试 |
| Plan-and-Execute + ReAct | Planner 生成计划，Executor 用 ReAct 执行每步 | LangChain Plan-and-Execute |
| Multi-Agent + ReAct | 每个 Agent 内部使用 ReAct | CrewAI、AutoGen |
| ToT + Reflexion | 树搜索中结合反思评估 | LATS 的变体 |
| Tool Use + ReAct | ReAct 中通过 Function Calling 调用工具 | 当前主流 Agent 框架 |

---

## 5. 工程框架与方法的映射

| 框架 | 主要方法 | 特点 |
|------|----------|------|
| **LangChain** | ReAct, Plan-and-Execute, Tool Use | 生态丰富，模块化 |
| **LangGraph** | 状态机式 Agent, Multi-Agent | 图结构，支持复杂流程 |
| **AutoGen** | Multi-Agent, 对话式协作 | 微软出品，企业级 |
| **CrewAI** | Multi-Agent, 角色扮演 | 简单易用，角色定义清晰 |
| **MetaGPT** | Multi-Agent, SOP 驱动 | 模拟软件公司流程 |
| **OpenAI Assistants** | Tool Use, ReAct | 原生集成，开箱即用 |
| **Anthropic Claude** | Tool Use, Extended Thinking | 结构化工具调用，长思考 |
| **BabyAGI** | Task-Driven, Plan-and-Execute | 任务分解与优先级管理 |
| **AutoGPT** | ReAct + 目标驱动 | 全自主执行，但稳定性不足 |

---

## 6. 选型指南

### 6.1 决策流程图

```
开始
  │
  ├─ 任务是否需要外部信息/工具？
  │   ├─ 否 → CoT 或 ToT（取决于复杂度）
  │   └─ 是 ↓
  │
  ├─ 任务是否可以分解为明确步骤？
  │   ├─ 是 → Plan-and-Execute
  │   └─ 否 ↓
  │
  ├─ 任务是否需要多次尝试/迭代改进？
  │   ├─ 是 → Reflexion
  │   └─ 否 ↓
  │
  ├─ 任务是否需要多种专业能力协作？
  │   ├─ 是 → Multi-Agent
  │   └─ 否 ↓
  │
  └─ ReAct（通用默认选择）
```

### 6.2 按场景推荐

| 场景 | 推荐方法 | 理由 |
|------|----------|------|
| 客服问答 | ReAct + Tool Use | 需要检索知识库和调用 API |
| 代码生成 | Reflexion + ReAct | 需要反复调试修正 |
| 数据分析报告 | Plan-and-Execute | 多步骤、需要规划 |
| 内容创作 | ToT + CoT | 需要探索多种创意方向 |
| 企业自动化 | Multi-Agent + Tool Use | 复杂流程、多系统集成 |
| 研究调研 | Plan-and-Execute + Reflexion | 需要规划和迭代 |
| 游戏 AI | LATS + Reflexion | 需要搜索和策略优化 |

### 6.3 成本与效果权衡

```
效果 ↑
     │                    ★ LATS
     │               ★ Multi-Agent
     │          ★ Reflexion
     │     ★ Plan-and-Execute
     │  ★ ReAct
     │ ★ CoT
     │★ Tool Use
     └──────────────────────────→ 成本
```

---

## 7. 发展趋势

### 7.1 当前趋势

1. **从单 Agent 到 Multi-Agent**: 多 Agent 协作成为处理复杂任务的主流范式
2. **从无状态到有状态**: 长期记忆、会话管理、状态持久化越来越重要
3. **从文本到多模态**: Agent 能处理图像、音频、视频等多种模态
4. **从 Prompt 到微调**: 针对 Agent 场景的模型微调（如 Toolformer、Gorilla）
5. **从框架到平台**: Agent 开发从代码框架向低代码/无代码平台演进

### 7.2 未来方向

- **自主学习**: Agent 能从经验中持续学习和改进（RLHF → RLAIF → Agent Learning）
- **世界模型**: Agent 内部构建环境模型，支持更准确的规划
- **安全与对齐**: 确保 Agent 行为符合人类意图和价值观
- **标准化协议**: Agent 之间通信的标准化（如 MCP、A2A 协议）
- **人机协作**: 不是完全自主，而是与人类高效协作

---

## 附录：术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 推理链 | Chain of Thought | 逐步推理的过程 |
| 行动循环 | Action Loop | Agent 感知-推理-行动的循环 |
| 工具调用 | Tool Use / Function Calling | Agent 调用外部函数的能力 |
| 自我反思 | Self-Reflection | Agent 对自身行为的评估和改进 |
| 规划器 | Planner | 负责生成执行计划的组件 |
| 执行器 | Executor | 负责执行具体步骤的组件 |
| 认知架构 | Cognitive Architecture | Agent 内部功能模块的组织结构 |
| 树搜索 | Tree Search | 探索多种可能路径的搜索策略 |
| 蒙特卡洛树搜索 | MCTS | 结合随机模拟和树搜索的算法 |

---

> **文档版本**: v1.0  
> **最后更新**: 2026-06-30  
> **作者**: Agent Runtime Evaluation Platform Team
