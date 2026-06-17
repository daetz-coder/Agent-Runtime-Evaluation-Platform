# Agent Evaluation SDK 集成指南

## 概述

Agent Evaluation SDK 让你可以轻松将评估功能集成到任意 Agent 中，无需手动输入轨迹。

## 安装

```bash
# 基础安装
pip install agent-eval-sdk

# 或者本地安装
cd sdk && pip install -e .
```

## 集成方式

### 方式 1: 装饰器 (最简单)

```python
from agent_eval_sdk import track_agent, SDKConfig

config = SDKConfig(api_base_url="http://localhost:8000")

@track_agent(config=config)
def my_agent(query: str, tracker=None):
    # 记录计划
    tracker.record_plan({"steps": ["search", "analyze", "fix"]})
    
    # 执行任务
    result = do_something(query)
    tracker.record_tool_call("do_something", {"query": query}, output=result)
    
    return result
```

### 方式 2: 上下文管理器

```python
from agent_eval_sdk import AgentTracker, SDKConfig

config = SDKConfig(api_base_url="http://localhost:8000")

with AgentTracker(config, goal="Fix bug") as tracker:
    tracker.record_plan({"steps": ["step1", "step2"]})
    tracker.record_tool_call("tool1", {"param": "value"}, output="result")
```

### 方式 3: LangChain 回调 (自动收集)

```python
from agent_eval_sdk import AgentTracker, AgentEvalCallbackHandler, SDKConfig

config = SDKConfig(api_base_url="http://localhost:8000")

with AgentTracker(config, goal="Search codebase") as tracker:
    handler = AgentEvalCallbackHandler(tracker)
    
    # 传给 LangChain
    llm = ChatOpenAI(callbacks=[handler])
    agent = create_agent(llm, tools, callbacks=[handler])
    
    # 自动收集轨迹!
    result = agent.invoke({"input": "..."})
```

## 集成到不同框架

### LangChain Agent

```python
from agent_eval_sdk import AgentTracker, AgentEvalCallbackHandler, SDKConfig
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor

def run_langchain_agent(query: str):
    config = SDKConfig(api_base_url="http://localhost:8000")
    
    with AgentTracker(config, goal=query) as tracker:
        # 创建回调处理器
        handler = AgentEvalCallbackHandler(tracker)
        
        # 创建 LangChain 组件
        llm = ChatOpenAI(model="gpt-4", callbacks=[handler])
        tools = [search_tool, read_tool]
        agent = create_react_agent(llm, tools, callbacks=[handler])
        executor = AgentExecutor(agent=agent, tools=tools, callbacks=[handler])
        
        # 运行 - 自动收集轨迹
        result = executor.invoke({"input": query})
        
        return result["output"]
```

### 自定义 Agent

```python
from agent_eval_sdk import AgentTracker, SDKConfig

def run_custom_agent(goal: str):
    config = SDKConfig(api_base_url="http://localhost:8000")
    
    with AgentTracker(config, goal=goal) as tracker:
        # 记录初始计划
        plan = generate_plan(goal)
        tracker.record_plan(plan)
        
        # 执行循环
        for step in plan["steps"]:
            result = execute_step(step)
            tracker.record_tool_call(
                name=step["tool"],
                input=step["params"],
                output=str(result)
            )
            
            # 检查是否需要重规划
            if should_replan(result):
                new_plan = generate_new_plan()
                tracker.record_replan(
                    reason="Step failed",
                    new_plan=new_plan
                )
                # 使用新计划继续...
```

### 命令行工具

```python
from agent_eval_sdk import AgentTracker, SDKConfig
import subprocess

def run_command_tool(command: str):
    config = SDKConfig(api_base_url="http://localhost:8000")
    
    with AgentTracker(config, goal=f"Run: {command}") as tracker:
        tracker.record_plan({"steps": ["execute_command"]})
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        tracker.record_tool_call(
            name="subprocess",
            input={"command": command},
            output=result.stdout
        )
        
        if result.returncode != 0:
            tracker.record_think(f"Command failed with code {result.returncode}")
        
        return result.stdout
```

## 配置选项

```python
config = SDKConfig(
    # 后端地址
    api_base_url="http://localhost:8000",
    
    # 自动行为
    auto_start_task=True,        # 第一次 record_*() 时自动创建任务
    auto_run_evaluation=True,    # complete_task() 时自动运行评估
    
    # 批量上报
    batch_size=20,               # 每批上报步骤数
    flush_interval=5.0,          # 自动刷新间隔(秒)
    
    # 重试
    max_retries=3,               # 网络错误重试次数
)
```

## 记录方法

| 方法 | 说明 |
|------|------|
| `record_plan(plan)` | 记录计划 |
| `record_tool_call(name, input, output)` | 记录工具调用 |
| `record_think(thought)` | 记录思考 |
| `record_replan(reason, new_plan)` | 记录重规划 |

## 完整示例

```python
from agent_eval_sdk import AgentTracker, SDKConfig, track_agent

# 示例 1: 装饰器方式
@track_agent(config=SDKConfig(api_base_url="http://localhost:8000"))
def fix_bug_agent(bug_description: str, tracker=None):
    """自动追踪的 Agent"""
    
    # 1. 制定计划
    tracker.record_plan({
        "steps": ["reproduce", "diagnose", "fix", "test"]
    })
    
    # 2. 复现问题
    tracker.record_tool_call(
        "run_tests",
        {"test": "test_login"},
        output="2 tests failed"
    )
    
    # 3. 诊断
    tracker.record_think("Login fails when JWT token expires")
    
    # 4. 修复
    tracker.record_tool_call(
        "edit_file",
        {"file": "auth.py", "change": "Add token refresh"},
        output="Fixed"
    )
    
    # 5. 测试
    tracker.record_tool_call(
        "run_tests",
        {"test": "test_login"},
        output="All tests passed"
    )
    
    return "Bug fixed!"


# 示例 2: 上下文管理器方式
def search_agent(query: str):
    """使用上下文管理器的 Agent"""
    
    config = SDKConfig(api_base_url="http://localhost:8000")
    
    with AgentTracker(config, goal=query) as tracker:
        # 搜索
        results = search(query)
        tracker.record_tool_call("search", {"query": query}, output=str(results))
        
        # 分析
        analysis = analyze(results)
        tracker.record_think(f"Found {len(results)} results")
        
        # 生成报告
        report = generate_report(analysis)
        tracker.record_tool_call("generate_report", {"data": analysis}, output=report)
        
        return report


# 运行
if __name__ == "__main__":
    # 运行装饰器方式
    result1 = fix_bug_agent("Login fails after token expires")
    print(f"Result 1: {result1}")
    
    # 运行上下文管理器方式
    result2 = search_agent("authentication code")
    print(f"Result 2: {result2}")
```

## 查看结果

运行后，访问评估平台查看结果：

1. **前端界面**: http://localhost:3000
   - 仪表板: 查看总体统计
   - 任务管理: 查看所有任务
   - 评估详情: 查看详细评分

2. **API 接口**:
   ```bash
   # 获取评估摘要
   curl http://localhost:8000/api/v1/reports/summary
   
   # 获取任务列表
   curl http://localhost:8000/api/v1/tasks/
   ```

## 注意事项

1. **后台线程**: SDK 使用后台线程上报数据，`record_*()` 方法是非阻塞的
2. **自动任务**: 设置 `auto_start_task=True` 时，第一次 `record_*()` 会自动创建任务
3. **批量上报**: 数据会先缓存，达到 `batch_size` 或 `flush_interval` 时批量发送
4. **优雅关闭**: `complete_task()` 或 `with` 块结束时会刷新所有剩余数据
5. **错误处理**: 网络错误会自动重试，不会影响 Agent 运行
