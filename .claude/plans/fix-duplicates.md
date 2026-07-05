# 重复代码修复方案

## 目标
消除项目中 7 组重复代码，统一为单一数据源。

---

## 修复 #1: DIMENSION_LABELS → 提取到共享常量模块

**当前状态**：`evaluation_graph.py:31` 和 `evaluation_service.py:36` 定义了完全相同的字典。

**方案**：
1. 新建 `app/constants.py`，将 `DIMENSION_LABELS` 放入
2. `app/graphs/evaluation_graph.py` 改为 `from app.constants import DIMENSION_LABELS`
3. `app/services/evaluation_service.py` 改为 `from app.constants import DIMENSION_LABELS`

**风险**：🟢 极低，纯常量提取

---

## 修复 #2: cache.py → wiki_agent 使用平台 cache

**当前状态**：`app/wiki_agent/cache.py` 是 `app/core/cache.py` 的精简复制。
唯一消费者：`app/wiki_agent/session/store.py`（只用 `cache_get`, `cache_set`, `cache_delete`）。

**关键差异**：wiki_agent cache 用 `"wiki:"` key 前缀，core 用 `"eval:"` 前缀。
**处理方式**：在 store.py 中手动加 `"wiki:"` 前缀，保持 key 空间隔离。

**关键发现**：`app/main.py` 已在 line 59 调用 `init_redis()`，line 61 才调用 `wiki_agent_startup()`。
所以 core cache 的 Redis 在 wiki_agent 启动前就已经初始化好了，无需改 bootstrap。

**方案**：
1. `app/wiki_agent/session/store.py` 改为 `from app.core.cache import cache_get, cache_set, cache_delete`
2. store.py 中现有的 key 已经带 `"wiki:"` 前缀（如 `"wiki:sessions:list"`），core cache 会再加 `"eval:"` 前缀
3. Redis key 会从 `"wiki:wiki:sessions:list"` 变为 `"eval:wiki:sessions:list"`，缓存会短暂失效但自动重建
4. 删除 `app/wiki_agent/cache.py`

**风险**：🟢 低，初始化时序已确认正确，key 变化仅影响缓存（自动重建）

---

## 修复 #3: llm_factory → 添加交叉引用注释（不合并）

**当前状态**：`wiki_agent/agent/llm_factory.py` 是 `agent_runtime/llm_factory.py` 的功能子集。
签名不兼容：函数名不同、参数不同、返回类型不同。

**关键发现**：`agent_runtime/llm_factory.py` **不支持** `streaming` 和 `max_tokens` 参数，
而 wiki_agent 的 graph.py 依赖这两个参数进行流式输出。无法简单委托。

**方案**：保留两个工厂，但添加交叉引用注释说明关系：
- `wiki_agent/agent/llm_factory.py` 顶部添加注释：
  "注意：此工厂与 app/agent_runtime/llm_factory.py 功能有重叠。
   后者支持 5 个 provider 但不支持 streaming/max_tokens。
   本工厂专为 wiki_agent 的流式输出需求定制。"

**风险**：🟢 零，仅添加注释

---

## 修复 #4: ActionType → SDK 消除重复定义

**当前状态**：`app/models/action_types.py` 和 `sdk/collector.py` 定义了完全相同的 14 个常量。
SDK 是独立包，不应依赖 `app.*`。

**方案**：将 ActionType 移入 SDK 包内作为规范定义，app 层 re-export：
1. 保留 `sdk/collector.py` 中的 `ActionType` 作为规范定义（它已经在那了）
2. `app/models/action_types.py` 改为 `from sdk.collector import ActionType`（re-export）
3. 添加注释说明规范定义在 SDK 中

**风险**：🟢 低，已有 `app/collectors/__init__.py` 从 sdk 导入的先例

---

## 修复 #5: config LLM 配置 → wiki_agent 引用平台配置

**当前状态**：5 个 LLM 相关 key 在两份 Settings 中重复定义。
20 个文件 import wiki_agent config，不宜大改。

**方案**：最小改动 — 在 wiki_agent config 中引用平台的 LLM key，避免硬编码重复默认值：
```python
# app/wiki_agent/config.py
from app.core.config import settings as platform_settings

class WikiAgentSettings(BaseSettings):
    # LLM 配置 — 复用平台设置
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = platform_settings.DEEPSEEK_BASE_URL
    DEEPSEEK_MODEL: str = platform_settings.DEEPSEEK_MODEL
    ZHIPUAI_API_KEY: str = ""
    ...
```

**风险**：🟢 低，只是消除硬编码的重复默认值

---

## 修复 #6: TEST_SET → 提取到共享 fixtures

**当前状态**：`scripts/eval_retrieval_standalone.py` 和 `scripts/eval_query_rewrite_ab.py`
定义了完全相同的 TEST_SET（20 条）和 `hit_rate_at_k`、`mean_reciprocal_rank` 辅助函数。

**方案**：
1. 新建 `scripts/_fixtures.py`，放入 TEST_SET 和两个辅助函数
2. 两个脚本改为 `from scripts._fixtures import TEST_SET, hit_rate_at_k, mean_reciprocal_rank`

**风险**：🟢 极低

---

## 修复 #7: TrajectoryRecorder vs TrajectoryCollector — 暂不合并

**原因**：
- `record_tool_call()` 语义不同（一个合并 CALL+RESULT，一个分开）
- `TrajectoryRecorder` 被 `agent_runtime/` 的 6 个文件和测试使用
- `TrajectoryCollector` 被 SDK adapters 和 app/collectors 使用
- 合并需要大量调用方适配，风险高

**当前处理**：添加交叉引用注释，说明两者的关系和差异。
后续可考虑让 TrajectoryRecorder 内部包装 TrajectoryCollector。

---

## 执行顺序

1. #1 DIMENSION_LABELS（最简单，零风险）
2. #6 TEST_SET fixtures（简单，零风险）
3. #3 llm_factory 注释（零风险，仅注释）
4. #4 ActionType re-export（简单，低风险）
5. #5 config 引用（简单，低风险）
6. #2 cache.py 合并（中等，需验证 Redis 初始化）
7. #7 TrajectoryRecorder 注释（仅添加注释）
