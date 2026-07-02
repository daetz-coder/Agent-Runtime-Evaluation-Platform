在 Multi-Agent 里，最推荐的设计是：

> **主 Agent 有全局 State，子 Agent 有局部 State；子 Agent 不直接改全局 State，而是提交 Patch / Result，由主 Runtime 合并。**

可以理解成：

```text
Global State（主状态）
      │
      ├── SubAgent A Local State
      ├── SubAgent B Local State
      └── SubAgent C Local State
```

不是所有 Agent 共享一个可随便写的 State。

------

## 1. 如何防止 subAgent 冲突？

核心原则：

> **分区、隔离、合并。**

### 任务分区

主 Agent 下发任务时，要明确每个 subAgent 的边界：

```text
Agent A：只负责检索文档
Agent B：只负责评测答案
Agent C：只负责生成总结
```

或者：

```text
Agent A：只修改 src/parser/*
Agent B：只修改 tests/*
Agent C：只修改 docs/*
```

这样可以减少资源冲突。

------

### 写权限隔离

不要让所有 subAgent 都能写同一个文件、同一个 DB 表、同一个 State 字段。

例如：

```python
state = {
    "retrieval_result": None,   # Retriever 写
    "eval_result": None,        # Evaluator 写
    "final_answer": None        # Writer 写
}
```

每个 Agent 只写自己的 namespace：

```python
state["agents"]["retriever"]
state["agents"]["evaluator"]
state["agents"]["writer"]
```

------

### Patch 合并

子 Agent 不直接写全局结果，而是返回：

```python
{
    "agent_id": "retriever",
    "patch": {
        "retrieved_docs": [...]
    }
}
```

主 Agent / Runtime 负责合并：

```text
SubAgent Result
      ↓
Validate
      ↓
Merge into Global State
```

这就像 Git：

```text
branch → pull request → review → merge
```

------

## 2. State 是一个还是多个？

推荐是：

```text
一个 Global State
多个 Local State
```

也就是：

```text
Supervisor State
      │
      ├── Worker A State
      ├── Worker B State
      └── Worker C State
```

### Global State 存什么？

全局事实、任务计划、共享结果：

```python
class GlobalState(TypedDict):
    user_task: str
    plan: list[dict]
    completed_tasks: list[str]
    shared_artifacts: dict
    agent_results: dict
    final_answer: str
```

### Local State 存什么？

子 Agent 自己的执行过程：

```python
class WorkerState(TypedDict):
    task_id: str
    agent_id: str
    local_context: str
    tool_results: list
    output: dict
    errors: list
```

------

## 3. State 如何同步？

同步不是“实时共享所有内容”，而是**事件式同步**。

```text
Global State
   ↓ 派发任务
Local State
   ↓ 执行
Result / Patch
   ↓
Global State 合并
```

流程：

```text
Supervisor
   │
   ├── Send(task A) → Worker A
   ├── Send(task B) → Worker B
   └── Send(task C) → Worker C

Worker A/B/C 各自执行

   ↓

返回结果

   ↓

Reducer / Aggregator 合并到 Global State
```

------

## 4. 在 LangGraph 里怎么做？

LangGraph 里通常用：

```text
Send()
```

给多个 Worker 发任务。

```python
from langgraph.types import Send

def dispatch_workers(state):
    return [
        Send("worker", {
            "task": task,
            "agent_id": f"worker_{i}"
        })
        for i, task in enumerate(state["tasks"])
    ]
```

每个 worker 收到的是自己的局部输入：

```python
def worker(state):
    result = do_task(state["task"])

    return {
        "agent_results": [{
            "agent_id": state["agent_id"],
            "result": result
        }]
    }
```

然后用 reducer 合并：

```python
from typing import Annotated
import operator

class GlobalState(TypedDict):
    tasks: list[str]
    agent_results: Annotated[list[dict], operator.add]
```

这里的关键是：

```python
Annotated[list[dict], operator.add]
```

表示多个 worker 返回的 `agent_results` 会被追加合并，而不是互相覆盖。

------

## 5. 最容易出错的地方

不要这样：

```python
state["result"] = ...
```

多个 subAgent 同时写：

```python
result
```

会冲突。

应该这样：

```python
state["agent_results"].append({
    "agent_id": "...",
    "result": ...
})
```

或者按 agent_id 分 namespace：

```python
state["agent_results"]["worker_1"] = ...
state["agent_results"]["worker_2"] = ...
```

------

## 6. 最佳实践一句话

> **Global State 负责共享事实和最终汇总；Local State 负责子任务执行；subAgent 只返回增量结果，不直接修改全局真相；最终由 Supervisor/Aggregator 统一验证、去重、冲突解决和合并。**