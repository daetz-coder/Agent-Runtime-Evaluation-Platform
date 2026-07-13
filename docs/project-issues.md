# 项目问题记录与解决方案

> Wiki-Agent + Runtime Evaluation Platform 开发过程中遇到的典型问题、
> 现象、处理方式与效果。按严重程度排列。

---

## 目录

1. [轨迹粒度不一致 — 同一事件类型字段结构各异](#1-轨迹粒度不一致)
2. [评估器与轨迹格式脱节 — 统一 TOOL_CALL 后评估器仍在过滤旧类型](#2-评估器与轨迹格式脱节)
3. [DeepSeek 不支持 with_structured_output — LLM Judge 三级降级策略](#3-deepseek-不支持-with_structured_output)
4. [HITL 中断导致轨迹分裂 — 同一个任务的轨迹被拆到两个 task](#4-hitl-中断导致轨迹分裂)
5. [并行评估竞态 — 6 个评估器同时写 DB 导致事务冲突](#5-并行评估竞态)
6. [一致性指标无法证明 — 简历上的数字没有测量工具支撑](#6-一致性指标无法证明)
7. [LangGraph 异步节点包装 — instrument_langgraph 对 async 节点的兼容](#7-langgraph-异步节点包装)
8. [LLM Proxy 递归死循环 — __getattr__ 导致无限递归](#8-llm-proxy-递归死循环)
9. [计划与执行脱节 — _generate_plan 的输出从未影响实际执行](#9-计划与执行脱节)
10. [Windows GBK 编码导致终端输出乱码](#10-windows-gbk-编码导致终端输出乱码)

---

## 1. 轨迹粒度不一致

### 背景

改造前，4 个 LangGraph 节点各自手动调用 `collector.record_*()` 采集轨迹。每个节点开发者凭感觉决定传什么字段。

### 现象

```
NODE_EXECUTE 类型，四个节点传的字段完全不同：

search 节点：
  record_node_execute("search", input_data=state_before)
  → state_before 是完整 state 摘要（messages_count, last_message, 所有 K/V）

respond 节点：
  record_node_execute("respond", input_data={"ai_response": "", "stage": ...})
  → 只传了 2 个字段

decide 节点：
  record_node_execute("decide", input_data={"user_message": state["user_message"][:100]})
  → 只传 user_message 前 100 字符

execute 节点：
  record_node_execute("execute", input_data={"decision": ...})
  → 只有 input_data，完全没有 output_data
```

STATE_CHANGE 的 diff 深度也完全不同：

```
search:  完整 diff（messages, wiki_results, facts 的变化）
decide:  只有一个字段："stage" 从 "respond" 变成 "decide"
```

### 根因

手动 `record_*()` 没有强制契约。每个节点按自己的理解传参。代码审查无法逐行检查每个 record 调用是否传了完整字段。

### 解决方案

两步改造：

**第一步**：用 `instrument_langgraph` 替代手动 `record_*()`。
所有 NODE_EXECUTE / STATE_CHANGE / FAILURE 由 wrapper 自动记录，使用统一的 `_extract_state_summary()` 和 `_extract_result_summary()` 摘要算法。

```python
# wrapper 统一处理，所有节点走同一段代码：
state_before = self._extract_state_summary(state)  # 统一摘要算法
result = await node_func(state, config)
state_after = self._extract_result_summary(result) # 统一摘要算法
self._collector.record_node_execute(node_name, input_data=state_before)
self._collector.record_state_change(state_before, state_after, ...)
```

**第二步**：域特定事件（plan / retrieval / memory / evidence 等）改为 `_events` 返回 + 统一 TOOL_CALL 格式。使用 `_tc()` / `_tr()` 辅助函数保证结构一致。

```python
# 改造前：各节点写不同格式的 dict
{"action_type": "plan", "action_detail": {"goal": ..., "steps": ...}}

# 改造后：全部用 _tc() 统一构建
_tc("plan", {"goal": ..., "steps": ...})
→ 内部：ToolCallDetail(tool_name="plan", input={...}).model_dump()
```

### 效果

NODE_EXECUTE 事件：4 个节点的字段结构**完全相同**（同一套摘要算法）。
STATE_CHANGE 事件：所有节点 diff 一致（before=state 摘要, after=result 摘要）。
FAILURE 事件：所有节点自动捕获异常，6 字段统一格式（含 stack_trace）。
域特定事件：全部通过 ToolCallDetail / ToolResultDetail 约束。

---

## 2. 评估器与轨迹格式脱节

### 背景

我们把域事件统一成了 `TOOL_CALL` + `tool_name`，但评估器（evaluators）仍然按旧的 action_type 过滤轨迹。

### 现象

```python
# 轨迹层已经输出：
{"action_type": "tool_call", "action_detail": {"tool_name": "plan", "input": {...}}}

# 评估器仍然在找：
if step.action_type == ActionType.PLAN:  # 永远找不到！
   ...

if step.action_type == ActionType.RETRIEVAL:  # 永远找不到！
   ...

if step.action_type in (ActionType.MEMORY_WRITE, ActionType.MEMORY_READ):  # 找不到！
   ...
```

6 个评估器中 5 个有硬编码的旧 action_type 过滤。评估器读到的轨迹永远是空的，打出的分数是默认 0 分。

### 根因

评估器和轨迹采集器由不同时间、不同需求驱动开发。轨迹格式改了，评估器没有同步更新。

### 解决方案

在 `BaseEvaluator` 中新增 3 个辅助方法，统一下游过滤逻辑：

```python
@staticmethod
def _is_tool(step, tool_name):
    """判断是否为指定 tool_name 的 TOOL_CALL"""
    return step.action_type == ActionType.TOOL_CALL and step.action_detail.get("tool_name") == tool_name

@staticmethod
def _is_any_tool(step, *tool_names):
    """判断是否为多个 tool_name 之一"""
    return step.action_type == ActionType.TOOL_CALL and step.action_detail.get("tool_name") in tool_names

@staticmethod
def _tool_input(step):
    """安全读取 TOOL_CALL 的 input 子字段"""
    return step.action_detail.get("input") or {}
```

然后逐个文件更新过滤条件：

| 文件 | 修改处数 | 改了什么 |
|---|---|---|
| `base.py` | 8 个 `_extract_*` | 旧: `step.action_type == ActionType.PLAN` → 新: `self._is_tool(step, "plan")` |
| `tactical_evaluator.py` | 12 处 | `step.action_type == "replan"` → `tool_name == "replan"` |
| `replan_evaluator.py` | 9 处 | `step.action_type == "replan"` → `_is_tool(step, "replan")` |
| `retrieval_evaluator.py` | 2 处 | `s.action_type in ("retrieval", "tool_call")` → `tool_name == "retrieval"` |
| `trajectory_compressor.py` | 2 处集合 | `IMPORTANT_TYPES` 从 10 种缩减为 7 种基础事件 |

### 效果

评估器恢复工作。同一套 `_is_tool()` / `_tool_input()` 方法在全部评估器中复用，确保过滤逻辑一致。后续再改轨迹格式时只需更新辅助方法，不必逐个文件修改。

---

## 3. DeepSeek 不支持 with_structured_output

### 背景

LangChain 的 `with_structured_output()` 依赖模型的 function calling / tool use 能力。DeepSeek 的 API 兼容 OpenAI 协议但**不支持 `json_schema` 模式的 `response_format`**。

### 现象

```python
structured_llm = self.llm.with_structured_output(RetrievalEvaluationResult)
result = await structured_llm.ainvoke(prompt)
# → NotImplementedError: with_structured_output is not implemented for this model.
```

整个评估流程在 DeepSeek 上完全跑不通。

### 根因

`base.py:_try_structured_output()` 默认返回 `None`（跳过），但不是所有评估器都走到了降级路径。部分评估器直接在 `evaluate()` 中调用了 `with_structured_output` 而没有兜底。

### 解决方案

实现三级降级策略：

```
第 1 级: with_structured_output      → API 级 function calling
                                         只对 Anthropic / OpenAI 有效
第 2 级: PydanticOutputParser         → Prompt 注入 JSON Schema
                                         所有模型通用
第 3 级: 手动 JSON 解析               → 正则 + 花括号平衡匹配 + 贪心兜底
                                         所有模型通用
```

```python
async def _invoke_structured_llm(self, chain, inputs, schema_class, max_retries=3, prompt=None):
    # 策略 1
    result = await self._try_structured_output(chain, inputs, schema_class, max_retries)
    if result: return result

    # 策略 2
    if prompt:
        result = await self._try_pydantic_parser(prompt, inputs, schema_class, max_retries)
        if result: return result

    # 策略 3
    return await self._try_manual_parse(chain, inputs, schema_class)
```

### 效果

| 模型 | 策略 | 成功率 |
|---|---|---|
| Claude (Anthropic) | with_structured_output | ~100% |
| GPT-4o | with_structured_output | ~100% |
| DeepSeek V3 | PydanticOutputParser | ~96% |
| GLM-4 | PydanticOutputParser | ~93% |
| Qwen-Max | PydanticOutputParser | ~95% |
| 任意模型（兜底） | 手动 JSON 解析 | ~85% |

---

## 4. HITL 中断导致轨迹分裂

### 背景

Wiki-Agent 的 execute 节点使用 LangGraph 的 `interrupt()` 实现 HITL（人机协作）。用户确认前图执行暂停，确认后再恢复。

### 现象

同一个对话任务被拆成了两个独立的评估 task：

```
第一次请求（search → respond → decide → execute → interrupt）
  → collector.start_async() 创建了 task_A
  → search/respond/decide 的轨迹写入 task_A
  → execute 中断，finish_async() 标记 task_A 完成

第二次请求（resume: execute → CRUD）
  → collector.start_async() 创建了 task_B
  → execute 的 CRUD 轨迹写入 task_B
  → finish_async() 标记 task_B 完成
```

评估时 task_A 只有中途轨迹没有最终结果，task_B 只有最终结果没有上下文。单独看任何一个都不完整。

### 根因

`run_chat_stream` 的 `finally` 块在中断时调用了 `finish_async()`，结束了第一个 task。恢复时 `resume_and_execute` 调用 `collector.start_async()` 创建了新 task。

### 解决方案

在 `resume_and_execute` 中不创建新 task，而是 attach 到已有 task：

```python
async def resume_and_execute(thread_id, confirm, *, session_id=None):
    collector = get_collector()

    # 先从 checkpoint 读取第一次请求时保存的 eval_task_id
    existing_task_id = None
    try:
        state_snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        if state_snapshot and state_snapshot.values:
            existing_task_id = state_snapshot.values.get("eval_task_id")
    except Exception:
        pass

    if existing_task_id:
        collector.attach(existing_task_id)  # ← 复用已有 task
    else:
        # 兜底：查数据库
        existing_task_id = await _find_task_by_thread_id(thread_id)
        if existing_task_id:
            collector.attach(existing_task_id)
```

同时在 search 节点把 `eval_task_id` 存进 WikiState，让它随 checkpoint 一起保存：

```python
return {**state, "eval_task_id": collector.task_id, ...}
```

### 效果

单个对话任务的所有轨迹（search → respond → decide → interrupt → resume → execute → CRUD）写入**同一个 task**，评估器看到完整的执行过程。

---

## 5. 并行评估竞态

### 背景

6 个评估器串行运行总耗时约 71 秒。改为 `asyncio.gather` 并行后，预期降到约 15 秒。

### 现象

并行后偶尔出现评估结果缺失或分数异常：

```
偶现：某个维度分数为 0，但日志显示该评估器执行成功
偶现：多个评估器返回相同分数（怀疑互相污染）
偶现：数据库报 IntegrityError（主键冲突）
```

### 根因

三个独立问题叠加：

1. **LLM 限流**：6 个评估器同时调用同一个 API，触发 QPS 限流，部分请求返回 429 或被静默降级
2. **评估器共享 LLM 实例**：默认 LLM 实例是单例，多协程并发调用线程不安全
3. **评估结果写入 DB 时的 `flush` 冲突**：多个评估器同时写同一条 Evaluation 记录

### 解决方案

```python
# 1. 限流控制
semaphore = asyncio.Semaphore(3)  # 最多 3 个并发 LLM 调用

async def _eval_with_limit(dim_name, EvalClass):
    async with semaphore:
        ev = EvalClass()
        result = await ev.evaluate(goal=goal, trajectory=trajectory, context=context)
        return dim_name, result

# 2. 每个评估器独立 LLM 实例
# 创建时 llm=None 会自动创建新实例，不共享

# 3. 评估结果分离：每个维度独立写入，不竞争同一行
# evaluate_parallel() 返回 dict，由调用方统一聚合后写入
```

### 效果

```
串行:  71.2s  (6 个维度 × ~12s/个)
并行(无限): 15.3s (但偶发限流错误)
并行(限流3): 22.8s (稳定，无错误)
并行(限流6): 18.1s (偶发限流，但模型侧自动重试)
→ 最终采用 限流6 + 重试 3 次
```

---

## 6. 一致性指标无法证明

### 背景

简历中写有"行为锚点使评分一致性提升 30-50%"，但代码库中没有任何测量基础设施来支撑这个数字。

### 现象

面试官追问"一致性具体指什么？怎么测量的？"时，回答口径不一致：

- "同一样本重复评估的方差下降"
- "不同模型之间的排序一致性"
- "与人工评分的相关性"

每次回答的定义都不完全一致，数字口径不确定。

### 根因

开发初期凭观察印象写入了这个指标，没有建立正式的实验流程。

### 解决方案

建立 `scripts/benchmark_consistency.py` 实验脚本：

- 6 条覆盖不同质量水平的测试轨迹（好 / 差 / 冗余 / 幻觉 / REPLAN / 混乱）
- 每条轨迹重复评估 5 次
- 对比 无锚点 Prompt  vs  带锚点 Prompt
- 输出：方差、MAD、ICC(2,1)、Spearman 秩相关系数

### 效果

实验结果**没有支持**原来的 30-50% 改善：

```
方差改善：-345%（锚点方差反而更大）
ICC(2,1)：0.59 → 0.63（轻微改善）
```

**结论：** 锚点的长 Prompt 引入了更多自由度，没有降低方差。简历上的数字被证伪。

改用 ICC(2,1) + Spearman 排序一致性作为主指标，重新校准评估系统。

---

## 7. LangGraph 异步节点包装

### 背景

`instrument_langgraph` 需要自动包装 Agent 的节点函数，但节点函数可能是同步或异步的，而且 LangGraph 内部对节点函数的签名有特定要求。

### 现象

```python
graph.add_node("search", search)  # search 是 async def
# instrument_langgraph 包装后报错：
# TypeError: 'coroutine' object is not iterable
# 或：TypeError: can't pickle coroutine objects
```

### 根因

包装器没有区分 sync 和 async 函数。对 async 函数用了 sync 包装方式。

### 解决方案

```python
def _wrap_node(self, node_name, node_func):
    # 自动检测是否为 async 函数
    if inspect.iscoroutinefunction(node_func):
        return self._wrap_node_async(node_name, node_func)
    else:
        return self._wrap_node_sync(node_name, node_func)
```

同时处理 LangGraph 的 `RunnableConfig` 参数传递：

```python
def _accepts_config(node_func):
    # 检测节点函数是否接受 config 参数
    return "config" in inspect.signature(node_func).parameters

async def _call_node_async(node_func, state, config):
    if _accepts_config(node_func):
        return await node_func(state, config)
    return await node_func(state)
```

### 效果

同步/异步透明兼容。无论节点是 `def` 还是 `async def`，包装器自动选择正确的处理方式。

---

## 8. LLM Proxy 递归死循环

### 背景

`create_proxy_llm()` 是 SDK 的第二种接入模式：透明包装 ChatModel，自动记录 LLM 调用轨迹。

### 现象

```python
llm = create_proxy_llm(ChatZhipuAI(...))
response = llm.invoke("Hello")
# → RecursionError: maximum recursion depth exceeded
```

### 根因

`ProxyChatModel` 的 `__getattr__` 方法：

```python
def __getattr__(self, name):
    return getattr(self._original_llm, name)
```

当访问 `self._original_llm` 本身时（比如在 `__init__` 阶段 `self._original_llm` 还没赋值），`__getattr__` 被触发，又回去找 `_original_llm`，陷入无限递归。

### 解决方案

```python
class ProxyChatModel(BaseChatModel):
    def __init__(self, original_llm, **kwargs):
        super().__init__(**kwargs)
        # 用 object.__setattr__ 绕过 __getattr__
        object.__setattr__(self, "_original_llm", original_llm)
        object.__setattr__(self, "_collector", get_collector())

    def __getattr__(self, name):
        # 保护私有属性
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._original_llm, name)
```

### 效果

消除了递归。同时保护 `_` 开头的私有属性不让 `__getattr__` 拦截。

---

## 9. 计划与执行脱节

### 背景

`_generate_plan()` 在 search 节点内部被调用，输出一个步骤列表，但没有被任何后续节点使用。

### 现象

```python
# search 节点
plan = await _generate_plan(user_msg)
# plan = {"steps": [{"milestone": "search"}, {"milestone": "respond"}]}

# 然后... plan 就再也没被用过
events.append(_tc("plan", {...}))  # 仅记录

return {**state, "wiki_results": ..., "_events": events}
#                    ↑ 没有 plan
```

用户问"Python 装饰器怎么用？给我讲讲原理和例子"，`_generate_plan` 生成了：
- ["解释装饰器原理", "展示语法", "给实际例子"]

但检索仍然只搜了原始问题，回答也没有按这三个子主题组织。

### 根因

开发初期把 `_generate_plan` 当作"评估素材"而非"执行指导"。计划生成和执行两条线没有打通。

### 解决方案（当前正在进行）

将 `plan` 加入 WikiState，流过整个图：

```
search 节点:
  plan = _generate_plan(user_msg)     → state["plan"]
  plan.steps 展开为子查询             → 多路检索
  plan 录进 _events                   → 评估器

respond 节点:
  plan 注入 SystemPrompt              → LLM 按大纲输出
  "请按以下大纲组织回答：①原理 ②语法 ③例子"
```

### 效果

待实现。预期：Agent 回答从"一段式"变为"结构化 TOC 式"，检索覆盖面随子主题数线性增加。

---

## 10. Windows GBK 编码导致终端输出乱码

### 背景

开发环境是 Windows 11 中文版，默认终端编码为 GBK。

### 现象

```python
print("阶段 1/2: 基线评估（无行为锚点）...")
# 输出：ΪD 1/2: ����������������
# 所有中文字符变成乱码，调试信息无法阅读
```

### 根因

Python 在 Windows 上默认使用 `sys.stdout.encoding = 'gbk'`，中文字符在 GBK 中可显示，但部分符号（如 `²`、异常字符）不在 GBK 字符集内，导致 `UnicodeEncodeError`。

### 解决方案

```python
# 临时解决：设置环境变量
PYTHONIOENCODING=utf-8 python -m scripts.benchmark_consistency

# 长期解决：脚本头部检测编码
import sys
if sys.platform == "win32" and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
```

### 效果

UTF-8 下中文正常显示。但 PowerShell 终端本身需要先设置 `$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8`，否则显示仍会乱码。

---

## 问题统计

| 类别 | 数量 | 典型修复周期 | 影响面 |
|---|---|---|---|
| 数据一致性（轨迹粒度 / 评估器脱节） | 2 | 2-3 天 | 评估准确性 |
| 框架兼容性（with_structured_output） | 1 | 1 天 | 模型可用性 |
| 并发/性能（并行评估竞态） | 1 | 1 天 | 响应速度 |
| 状态管理（HITL 轨迹分裂） | 1 | 1 天 | 数据完整性 |
| 递归/死循环（LLM Proxy） | 1 | 半天 | 系统可用性 |
| 编码问题（GBK / 乱码） | 1 | 半天 | 调试效率 |
| 指标可信度（一致性 30-50%） | 1 | 1 天（实验）+ 长期迭代 | 简历可信度 |
| 业务流程（计划与执行脱节） | 1 | 实施中 | Agent 回答质量 |

---

## 经验总结

1. **数据格式统一必须在第一天完成**。轨迹事件的结构不一致导致后续所有评估器、压缩器、监控面板都跟着不同步，修一个脱节的地方要改 5 个文件。

2. **不要相信没有工具支撑的数字**。30-50% 一致性提升写进简历时感觉很合理，实际建 Benchmark 一跑发现完全不成立。任何指标必须有可复现的测量脚本。

3. **降级策略比功能本身更重要**。with_structured_output 对国产模型普遍不可用，三级降级（API → Parser → 手动解析）让系统在任意模型上都能运行。

4. **HITL 需要考虑数据关联性**。`interrupt()` 天然会把一个操作拆成两个 HTTP 请求，如果不显式绑定同一个 task_id，轨迹就被拆散了。

5. **Instrumentation 代码会随业务代码一起腐烂**。手动 record_*() 的粒度会随着开发者更替或时间推移越来越不一致。框架级的自动采集（`instrument_langgraph`）是唯一能保持长期一致的手段。
