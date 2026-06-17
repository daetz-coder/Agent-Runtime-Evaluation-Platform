# Agent Evaluation SDK

自动收集 Agent 执行轨迹并上报到评估平台。

## 安装

```bash
# 基础安装
pip install agent-eval-sdk

# 包含 LangChain 集成
pip install agent-eval-sdk[langchain]

# 本地开发安装
cd sdk && pip install -e .
```

## 快速开始

### 方式 1: 装饰器 (最简单)

```python
from agent_eval_sdk import track_agent, SDKConfig

config = SDKConfig(api_base_url="http://localhost:8000")

@track_agent(config=config)
def my_agent(query: str, tracker=None):
    # 记录计划
    tracker.record_plan({"steps": ["search", "analyze", "fix"]})
    
    # 记录工具调用
    result = search_code(query)
    tracker.record_tool_call("search_code", {"query": query}, output=result)
    
    # 记录思考
    tracker.record_think("Found the issue in auth.py")
    
    # 记录另一个工具调用
    fix_code("auth.py")
    tracker.record_tool_call("edit_file", {"file": "auth.py"})
    
    return "Fixed!"

# 运行
result = my_agent("login bug")
```

### 方式 2: 上下文管理器

```python
from agent_eval_sdk import AgentTracker, SDKConfig

config = SDKConfig(api_base_url="http://localhost:8000")

with AgentTracker(config, goal="Fix login bug", context={"project": "webapp"}) as tracker:
    tracker.record_plan({"steps": ["reproduce", "diagnose", "fix", "test"]})
    
    tracker.record_tool_call("search_code", {"query": "login"}, output="found auth.py")
    tracker.record_think("The issue is in JWT validation")
    tracker.record_tool_call("edit_file", {"path": "auth.py"})
    tracker.record_tool_call("run_tests", {"path": "tests/"}, output="All passed")
```

### 方式 3: LangChain 回调 (自动收集)

```python
from agent_eval_sdk import AgentTracker, AgentEvalCallbackHandler, SDKConfig
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent

config = SDKConfig(api_base_url="http://localhost:8000")

# 创建追踪器
tracker = AgentTracker(config, goal="Search codebase")
tracker.start_task()

# 创建回调处理器
handler = AgentEvalCallbackHandler(tracker)

# 创建 LLM 和 Agent
llm = ChatOpenAI(callbacks=[handler])
tools = [search_tool, read_tool]
agent = create_react_agent(llm, tools, callbacks=[handler])

# 运行 Agent - 自动收集轨迹!
result = agent.invoke({"input": "Find authentication code"})

# 完成
tracker.complete_task()
```

### 方式 4: 手动 API

```python
from agent_eval_sdk import AgentTracker, SDKConfig

config = SDKConfig(api_base_url="http://localhost:8000")
tracker = AgentTracker(config)

# 手动控制生命周期
task_id = tracker.start_task(
    goal="Implement user registration",
    context={"framework": "FastAPI"}
)

# 手动记录每个步骤
tracker.record_plan({
    "steps": [
        {"description": "Design database model"},
        {"description": "Implement email verification"},
        {"description": "Create registration API"},
    ]
})

tracker.record_tool_call(
    name="search_code",
    input={"query": "user model"},
    output="Found: models/user.py"
)

tracker.record_think("User model exists, need to add verification fields")

tracker.record_replan(
    reason="Tests failed on email validation",
    new_plan=[
        {"description": "Fix email regex"},
        {"description": "Re-run tests"},
    ]
)

# 完成
tracker.complete_task()
```

## 配置选项

```python
from agent_eval_sdk import SDKConfig

config = SDKConfig(
    # 后端连接
    api_base_url="http://localhost:8000",  # 评估平台地址
    api_key=None,                          # API Key (可选)
    api_timeout=30.0,                      # 请求超时(秒)

    # 批量上报
    batch_size=20,           # 每批上报的步骤数
    flush_interval=5.0,      # 自动刷新间隔(秒)
    max_queue_size=10000,    # 队列最大容量

    # 重试
    max_retries=3,           # 最大重试次数
    retry_base_delay=1.0,    # 重试基础延迟(秒)
    retry_max_delay=30.0,    # 最大重试延迟

    # 行为
    auto_start_task=True,        # 自动创建任务
    auto_run_evaluation=False,   # 轨迹上报后自动运行评估
    collect_llm_calls=True,      # 自动收集 LLM 调用
    collect_tool_calls=True,     # 自动收集工具调用
)
```

## 记录方法

| 方法 | 说明 | 参数 |
|------|------|------|
| `record_plan(plan)` | 记录计划步骤 | `plan`: dict, 包含 steps 等 |
| `record_tool_call(name, input, output)` | 记录工具调用 | `name`: 工具名, `input`: 输入参数, `output`: 输出结果 |
| `record_think(thought)` | 记录思考过程 | `thought`: 思考内容 |
| `record_replan(reason, new_plan)` | 记录重规划 | `reason`: 重规划原因, `new_plan`: 新计划 |
| `record_step(action_type, action_detail, observation)` | 通用记录 | 自定义动作类型 |

## 集成到现有 Agent

### LangChain Agent

```python
from agent_eval_sdk import AgentTracker, AgentEvalCallbackHandler, SDKConfig

def run_langchain_agent(query: str):
    config = SDKConfig(api_base_url="http://localhost:8000")
    
    with AgentTracker(config, goal=query) as tracker:
        handler = AgentEvalCallbackHandler(tracker)
        
        llm = ChatOpenAI(callbacks=[handler])
        agent = create_agent(llm, tools, callbacks=[handler])
        
        result = agent.invoke({"input": query})
        return result
```

### AutoGPT / BabyAGI

```python
from agent_eval_sdk import AgentTracker, SDKConfig

def run_custom_agent(goal: str):
    config = SDKConfig(api_base_url="http://localhost:8000")
    
    with AgentTracker(config, goal=goal) as tracker:
        # 在 Agent 循环中记录步骤
        while not done:
            plan = generate_plan(goal)
            tracker.record_plan(plan)
            
            for step in plan["steps"]:
                result = execute_step(step)
                tracker.record_tool_call(
                    name=step["tool"],
                    input=step["params"],
                    output=result
                )
                
                if need_replan(result):
                    tracker.record_replan(
                        reason="Step failed",
                        new_plan=generate_new_plan()
                    )
                    break
```

### 命令行工具

```python
from agent_eval_sdk import AgentTracker, SDKConfig

def main():
    config = SDKConfig(api_base_url="http://localhost:8000")
    
    tracker = AgentTracker(config)
    tracker.start_task(goal="Process command line task")
    
    try:
        # 你的命令行逻辑
        tracker.record_tool_call("execute_command", {"cmd": "ls -la"}, output="...")
        # ...
    finally:
        tracker.complete_task()

if __name__ == "__main__":
    main()
```

## 数据流

```
Agent Code
    │
    ├── tracker.record_plan(...)
    ├── tracker.record_tool_call(...)
    ├── tracker.record_think(...)
    └── tracker.record_replan(...)
           │
           ▼
    ┌─────────────────┐
    │ TrajectoryCollector │  (本地收集，自动编号)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  AsyncReporter   │  (后台线程，批量上报)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  HTTP POST       │  /api/v1/tasks/{id}/trajectory
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  评估平台后端     │  (FastAPI + LangGraph)
    └─────────────────┘
```

## 与后端 API 对齐

SDK 的数据格式与后端完全兼容：

| SDK 操作 | HTTP 方法 | 端点 |
|---------|----------|------|
| 创建任务 | POST | `/api/v1/tasks/` |
| 上报轨迹 | POST | `/api/v1/tasks/{task_id}/trajectory` |
| 触发评估 | POST | `/api/v1/evaluations/` |
| 查询评估 | GET | `/api/v1/evaluations/{eval_id}` |

## 注意事项

1. **后台线程**: SDK 使用后台线程上报数据，`record_*()` 方法是非阻塞的
2. **自动任务**: 设置 `auto_start_task=True` 时，第一次 `record_*()` 会自动创建任务
3. **批量上报**: 数据会先缓存，达到 `batch_size` 或 `flush_interval` 时批量发送
4. **优雅关闭**: `complete_task()` 会刷新所有剩余数据
5. **错误处理**: 网络错误会自动重试，不会影响 Agent 运行
