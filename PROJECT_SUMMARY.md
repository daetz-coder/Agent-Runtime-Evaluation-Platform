# Agent Runtime Evaluation Platform - 项目总结

## 项目概述

这是一个 **Agent Runtime Evaluation Platform**，用于评估AI Agent的运行时质量。与传统的Prompt评估工具不同，本项目专注于评估Agent的**执行过程**，而不仅仅是最终结果。

## 核心创新点

### 1. Planning Quality Score (规划质量评分)
- **Coverage**: 是否覆盖关键里程碑
- **Ordering**: 步骤顺序是否合理
- **Granularity**: 细节层次是否合适
- **Completeness**: 计划是否完整

### 2. Trajectory Quality Score (轨迹质量评分)
- 不只看结果，看整个执行轨迹
- 100步完成 vs 10步完成，评分应该不同

### 3. Memory Retention Score (记忆保持评分)
- Agent是否忘记关键事实
- 这是Long-running Agent的核心问题

## 技术栈

- **Web框架**: FastAPI
- **工作流编排**: LangGraph
- **数据库**: PostgreSQL + SQLAlchemy (异步)
- **LLM集成**: LangChain (OpenAI/Anthropic)
- **语言**: Python 3.11+

## 项目结构

```
agent-eval-platform/
├── app/
│   ├── api/v1/endpoints/    # API端点
│   │   ├── tasks.py         # 任务管理
│   │   ├── evaluation.py    # 评估执行
│   │   └── reports.py       # 报告生成
│   ├── core/                # 核心配置
│   │   └── config.py        # 应用配置
│   ├── db/                  # 数据库层
│   │   ├── database.py      # 数据库连接
│   │   └── models.py        # ORM模型
│   ├── evaluators/          # 5个评估维度 ⭐
│   │   ├── base.py          # 基础评估器
│   │   ├── planning_evaluator.py    # 规划评估
│   │   ├── tactical_evaluator.py    # 战术评估
│   │   ├── tool_use_evaluator.py    # 工具使用评估
│   │   ├── memory_evaluator.py      # 记忆评估
│   │   └── replan_evaluator.py      # 重规划评估
│   ├── graphs/              # LangGraph工作流
│   │   └── evaluation_graph.py      # 评估工作流图
│   ├── models/              # Pydantic模型
│   │   └── schemas.py       # API数据模型
│   ├── services/            # 业务逻辑层
│   │   └── evaluation_service.py    # 评估服务
│   └── main.py              # FastAPI应用入口
├── tests/                   # 测试套件
├── docs/                    # 文档
├── pyproject.toml           # 项目配置
└── README.md
```

## 核心流程

```
1. 创建任务 (Create Task)
   ↓
2. 添加执行轨迹 (Add Trajectory)
   ↓
3. 运行评估 (Run Evaluation)
   ↓
4. LangGraph工作流执行:
   - 验证输入
   - 并行运行5个评估器
   - 聚合结果
   ↓
5. 返回评估报告 (Return Report)
```

## 5个评估维度详解

### 1. Planning Evaluator (规划评估器)
评估Agent的计划质量：
- 是否遗漏关键阶段
- 步骤顺序是否合理
- 是否过细或过粗
- 是否完整

**示例**:
- 好的计划: Analyze → OAuth → Test → Docs
- 坏的计划: Open auth.py → Read line 20 → Read line 30

### 2. Tactical Evaluator (战术评估器)
评估下一步行动的质量：
- 当前状态下的行动是否相关
- 行动是否高效
- 行动是否正确

**示例**:
- 合理: 在Root Cause Analysis阶段，read auth.py
- 错误: 在Root Cause Analysis阶段，create PR

### 3. Tool Use Evaluator (工具使用评估器)
评估工具选择和使用：
- 是否选择了正确的工具
- 工具参数是否准确
- 工具结果是否有效利用

**示例**:
- 合理: 用search_code找认证代码
- 浪费: 用run_tests找认证代码

### 4. Memory Evaluator (记忆评估器)
评估记忆质量（创新点）：
- 是否保留关键事实
- 回忆的信息是否相关
- 记忆是否一致

**示例**:
- 任务: 修复JWT Bug
- Agent忘记: 项目使用JWT → 直接扣分

### 5. Replan Evaluator (重规划评估器)
评估重规划决策（最有意思）：
- 重规划触发是否合适
- 新计划质量如何
- 是否从失败中学习

**示例**:
- 连续失败5次，继续死循环 → 评分: 0
- 连续失败5次，触发Replan → 评分: 100

## API端点

### 任务管理
- `POST /api/v1/tasks/` - 创建任务
- `GET /api/v1/tasks/{task_id}` - 获取任务
- `GET /api/v1/tasks/` - 列出所有任务
- `POST /api/v1/tasks/{task_id}/trajectory` - 添加执行轨迹

### 评估执行
- `POST /api/v1/evaluations/` - 运行评估
- `GET /api/v1/evaluations/{evaluation_id}` - 获取评估结果

### 报告分析
- `GET /api/v1/reports/summary` - 获取评估摘要
- `GET /api/v1/reports/tasks/{task_id}/history` - 任务评估历史
- `GET /api/v1/reports/dimensions/{dimension}` - 维度统计

## 如何使用

### 1. 启动服务
```bash
# 安装依赖
pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env 添加API密钥

# 启动服务
python -m app.main
```

### 2. 访问API文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 3. 运行评估示例
```python
import httpx

# 1. 创建任务
response = httpx.post("http://localhost:8000/api/v1/tasks/", json={
    "goal": "Fix authentication bug",
    "context": {"project": "web-app"}
})
task_id = response.json()["id"]

# 2. 添加执行轨迹
httpx.post(f"http://localhost:8000/api/v1/tasks/{task_id}/trajectory", json=[
    {
        "step_number": 1,
        "action_type": "plan",
        "action_detail": {"steps": [{"description": "Search auth code"}]}
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "search_code", "input": {"query": "auth"}},
        "observation": "Found: auth.py"
    }
])

# 3. 运行评估
response = httpx.post("http://localhost:8000/api/v1/evaluations/", json={
    "task_id": task_id
})
evaluation = response.json()

# 4. 查看结果
print(f"Overall Score: {evaluation['evaluation']['overall_score']}")
print(f"Planning: {evaluation['evaluation']['planning']['overall']}")
print(f"Memory: {evaluation['evaluation']['memory']['overall']}")
```

## 为什么这个项目能让你脱颖而出？

### 1. 展示Agent Engineering能力
- 不只是使用Agent，而是理解Agent内部机制
- 能评估Agent的决策质量

### 2. 解决真实问题
- "Agent Demo很成功，上线以后不稳定"是真实痛点
- 市场上缺乏这类工具

### 3. 技术深度
- LangGraph工作流编排
- 异步编程
- LLM集成
- 评估指标设计

### 4. 创新性
- Planning Quality Score - 几乎没人做
- Memory Retention Score - Long-running Agent核心问题
- Replan Evaluation - 最有意思的评估维度

## 扩展方向

1. **添加更多评估维度**
   - 错误恢复能力
   - 资源使用效率
   - 安全性评估

2. **可视化仪表板**
   - 实时评估监控
   - 历史趋势分析
   - 对比分析

3. **集成更多Agent框架**
   - AutoGPT
   - BabyAGI
   - Custom Agents

4. **Benchmark支持**
   - GAIA
   - SWE-bench
   - 自定义Benchmark

## 总结

这个项目展示了你对Agent Engineering的深入理解，不仅仅是"如何让Agent做事"，更是"如何知道Agent做得好不好"。这正是未来Agent落地生产环境所需的核心能力。
