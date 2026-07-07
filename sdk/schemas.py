"""
sdk.schemas — 14 种 ActionType 的 Pydantic Schema 定义

每种 ActionType 的 action_detail 都有对应的 Pydantic 模型，用于：
1. Agent 生成轨迹时的格式约束（record 时自动校验）
2. 评估器 LLM 的结构化输出（with_structured_output）
3. 数据序列化/反序列化的类型安全
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── 内部工具 ──────────────────────────────────────────────────


def _short(value: Any, limit: int = 4000) -> Any:
    """截断过长的值，防止轨迹数据过大。"""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, dict):
        return {str(k): _short(v, limit) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_short(v, limit) for v in value[:50]]
    return _short(str(value), limit)


# ── 规划类 ──────────────────────────────────────────────


class PlanDetail(BaseModel):
    """PLAN — 初始计划"""

    goal: str = Field(description="任务目标")
    context: Optional[Dict[str, Any]] = Field(default=None, description="任务上下文")
    steps: Optional[List[str]] = Field(default=None, description="计划步骤列表")
    milestones: Optional[List[str]] = Field(default=None, description="里程碑列表")


class PlanUpdateDetail(BaseModel):
    """PLAN_UPDATE — 计划动态更新"""

    milestone_status: Optional[Dict[str, str]] = Field(default=None, description="各里程碑完成状态")
    next_action: str = Field(description="下一步计划")
    reason: str = Field(default="", description="更新原因")
    remaining_steps: Optional[List[str]] = Field(default=None, description="剩余步骤")


class ReplanDetail(BaseModel):
    """REPLAN — 重规划"""

    reason: str = Field(description="重规划原因")
    new_plan: str = Field(default="", description="新计划内容")
    trigger: str = Field(default="", description="触发条件（如 tool_failure, user_cancel）")


# ── 工具类 ──────────────────────────────────────────────


class ToolCallDetail(BaseModel):
    """TOOL_CALL — 工具调用"""

    tool_name: str = Field(description="工具名称")
    input: Optional[Dict[str, Any]] = Field(default=None, description="工具输入参数")
    duration_ms: Optional[float] = Field(default=None, description="调用耗时（毫秒）")

    @field_validator("input", mode="before")
    @classmethod
    def _truncate_input(cls, v: Any) -> Any:
        return _short(v)


class ToolResultDetail(BaseModel):
    """TOOL_RESULT — 工具返回"""

    tool_name: str = Field(description="工具名称")
    success: bool = Field(default=True, description="是否成功")
    error_type: Optional[str] = Field(default=None, description="错误类型（失败时）")
    duration_ms: Optional[float] = Field(default=None, description="调用耗时（毫秒）")


class ToolDecisionDetail(BaseModel):
    """TOOL_DECISION — 工具选择决策"""

    tool_name: str = Field(description="选择的工具名称")
    node_name: Optional[str] = Field(default=None, description="决策所在的节点")
    input: Optional[Dict[str, Any]] = Field(default=None, description="决策时的输入上下文")
    step: Optional[int] = Field(default=None, description="当前步骤号")


# ── 记忆类 ──────────────────────────────────────────────


class MemoryWriteDetail(BaseModel):
    """MEMORY_WRITE — 记忆写入"""

    key: str = Field(description="记忆键名（如 key_facts, user_preference）")
    value: Any = Field(description="记忆值")
    source: str = Field(default="", description="数据来源（如 llm_extraction, user_input）")
    memory_type: str = Field(default="fact", description="记忆类型（fact, preference, context）")

    @field_validator("value", mode="before")
    @classmethod
    def _serialize_value(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v
        return json.dumps(v, ensure_ascii=False, default=str)[:2000]


class MemoryReadDetail(BaseModel):
    """MEMORY_READ — 记忆读取"""

    key: str = Field(description="记忆键名")
    value: Optional[Any] = Field(default=None, description="读取到的值")
    context: str = Field(default="", description="读取上下文")
    hit: bool = Field(default=True, description="是否命中")

    @field_validator("value", mode="before")
    @classmethod
    def _serialize_value(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            return v
        return json.dumps(v, ensure_ascii=False, default=str)[:2000]


# ── 状态类 ──────────────────────────────────────────────


class StateChangeDetail(BaseModel):
    """STATE_CHANGE — 状态变化"""

    node_name: str = Field(description="关联的节点名称")
    trigger: str = Field(default="", description="触发变化的原因")
    diff: Optional[Dict[str, Any]] = Field(default=None, description="before/after 差异")


class NodeExecuteDetail(BaseModel):
    """NODE_EXECUTE — 节点执行"""

    node_name: str = Field(description="节点名称")
    input: Optional[Any] = Field(default=None, description="节点输入")
    output: Optional[Any] = Field(default=None, description="节点输出")

    @field_validator("input", "output", mode="before")
    @classmethod
    def _truncate_large_fields(cls, v: Any) -> Any:
        return _short(v)


# ── 推理类 ──────────────────────────────────────────────


class ThinkDetail(BaseModel):
    """THINK — 思考/推理（也用于 LLM 调用记录）"""

    thought: str = Field(description="思考内容")
    model: str = Field(default="", description="模型名称（LLM 调用时）")
    messages: Optional[Any] = Field(default=None, description="发送的消息（LLM 调用时）")
    response: Optional[Any] = Field(default=None, description="模型响应（LLM 调用时）")
    duration_ms: Optional[float] = Field(default=None, description="调用耗时（毫秒）")

    @field_validator("messages", "response", mode="before")
    @classmethod
    def _truncate_llm_fields(cls, v: Any) -> Any:
        return _short(v, 1000)


# ── 异常类 ──────────────────────────────────────────────


class FailureDetail(BaseModel):
    """FAILURE — 失败/异常"""

    error_type: str = Field(description="错误类型（如 TimeoutError, ValueError）")
    error_message: str = Field(description="错误消息")
    context: str = Field(default="", description="错误上下文")
    recoverable: bool = Field(default=True, description="是否可恢复")
    node_name: str = Field(default="", description="关联的节点")
    stack_trace: Optional[str] = Field(default=None, description="堆栈跟踪")

    @field_validator("error_message", mode="before")
    @classmethod
    def _truncate_message(cls, v: str) -> str:
        return str(v)[:2000]

    @field_validator("stack_trace", mode="before")
    @classmethod
    def _truncate_stack(cls, v: Optional[str]) -> Optional[str]:
        return v[:1000] if v else v


# ── 检索类 ──────────────────────────────────────────────


class RetrievedDoc(BaseModel):
    """检索到的单个文档"""

    title: str = Field(default="", description="文档标题")
    path: str = Field(default="", description="文档路径")
    snippet: str = Field(default="", description="文档摘要")
    score: Optional[float] = Field(default=None, description="相关性分数")

    @field_validator("snippet", mode="before")
    @classmethod
    def _truncate_snippet(cls, v: str) -> str:
        return str(v)[:500]


class RetrievalDetail(BaseModel):
    """RETRIEVAL — 知识检索"""

    query: str = Field(description="检索查询文本")
    source: str = Field(default="", description="检索来源（如 hybrid_search, bm25）")
    result_count: int = Field(default=0, description="结果数量")
    duration_ms: Optional[float] = Field(default=None, description="检索耗时")
    retrieved_docs: Optional[List[RetrievedDoc]] = Field(default=None, description="检索结果文档列表")


class EvidenceSource(BaseModel):
    """证据来源统计"""

    retrieved_docs_count: int = Field(default=0, description="检索文档数")
    tool_results_count: int = Field(default=0, description="工具结果数")
    memory_results_count: int = Field(default=0, description="记忆结果数")
    chat_history_count: int = Field(default=0, description="对话历史数")


class EvidenceDetail(BaseModel):
    """EVIDENCE — 证据池构建"""

    evidence_type: str = Field(description="证据类型（如 rag_context, final_answer）")
    context: str = Field(default="", description="上下文描述")
    sources: Optional[EvidenceSource] = Field(default=None, description="证据来源统计")
    final_prompt_messages: Optional[List[Dict[str, str]]] = Field(default=None, description="最终 prompt 消息")
    final_response: Optional[str] = Field(default=None, description="Agent 最终回复内容（final_answer 类型时）")
    session_id: Optional[str] = Field(default=None, description="会话 ID")
    total_message_count: int = Field(default=0, description="消息总数")

    @field_validator("final_prompt_messages", mode="before")
    @classmethod
    def _truncate_messages(cls, v: Optional[List[Dict[str, str]]]) -> Optional[List[Dict[str, str]]]:
        if v is None:
            return v
        return [
            {"role": m.get("role", "unknown"), "content": str(m.get("content", ""))[:1000]}
            for m in v
        ]


# ── Schema 注册表 ──────────────────────────────────────

ACTION_DETAIL_SCHEMAS: Dict[str, type[BaseModel]] = {
    "plan": PlanDetail,
    "plan_update": PlanUpdateDetail,
    "replan": ReplanDetail,
    "tool_call": ToolCallDetail,
    "tool_result": ToolResultDetail,
    "tool_decision": ToolDecisionDetail,
    "memory_write": MemoryWriteDetail,
    "memory_read": MemoryReadDetail,
    "state_change": StateChangeDetail,
    "node_execute": NodeExecuteDetail,
    "think": ThinkDetail,
    "failure": FailureDetail,
    "retrieval": RetrievalDetail,
    "evidence": EvidenceDetail,
}
