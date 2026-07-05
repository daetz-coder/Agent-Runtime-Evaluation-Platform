"""
评估器 LLM 输出的 Pydantic Schema

用 with_structured_output 约束 LLM 输出格式，替代手动 JSON 解析。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InefficientCall(BaseModel):
    """低效工具调用"""

    tool: str = Field(description="工具名称")
    issue: str = Field(description="问题描述")
    suggestion: str = Field(description="改进建议")


class ToolUseEvaluationResult(BaseModel):
    """ToolUseEvaluator 输出"""

    selection_quality: int = Field(ge=0, le=100, description="选择质量分数")
    parameter_accuracy: int = Field(ge=0, le=100, description="参数准确性分数")
    result_utilization: int = Field(ge=0, le=100, description="结果利用分数")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")
    inefficient_calls: List[InefficientCall] = Field(default_factory=list, description="低效调用列表")


class PlanningEvaluationResult(BaseModel):
    """PlanningEvaluator 输出"""

    coverage: int = Field(ge=0, le=100, description="覆盖度分数")
    ordering: int = Field(ge=0, le=100, description="顺序性分数")
    granularity: int = Field(ge=0, le=100, description="粒度分数")
    completeness: int = Field(ge=0, le=100, description="完整性分数")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")


class TacticalEvaluationResult(BaseModel):
    """TacticalEvaluator 输出"""

    relevance: int = Field(ge=0, le=100, description="相关性分数")
    efficiency: int = Field(ge=0, le=100, description="效率分数")
    correctness: int = Field(ge=0, le=100, description="正确性分数")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")


class MemoryEvaluationResult(BaseModel):
    """MemoryEvaluator 输出"""

    retention: int = Field(ge=0, le=100, description="保持度分数")
    relevance: int = Field(ge=0, le=100, description="相关性分数")
    consistency: int = Field(ge=0, le=100, description="一致性分数")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")


class ReplanEvaluationResult(BaseModel):
    """ReplanEvaluator 输出"""

    trigger_appropriateness: int = Field(ge=0, le=100, description="触发时机分数")
    adaptation_quality: int = Field(ge=0, le=100, description="适应质量分数")
    learning_from_failure: int = Field(ge=0, le=100, description="失败学习分数")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")


class RetrievalEvaluationResult(BaseModel):
    """RetrievalEvaluator 输出"""

    relevance: int = Field(ge=0, le=100, description="相关性分数")
    evidence_accuracy: int = Field(ge=0, le=100, description="证据准确分数")
    coverage: int = Field(ge=0, le=100, description="覆盖度分数")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")
    hallucination_detected: bool = Field(default=False, description="是否检测到幻觉")
    missing_info: Optional[str] = Field(default=None, description="缺失信息描述")


# ── Schema 注册表 ──────────────────────────────────────

EVALUATOR_OUTPUT_SCHEMAS = {
    "tool_use": ToolUseEvaluationResult,
    "planning": PlanningEvaluationResult,
    "tactical": TacticalEvaluationResult,
    "memory": MemoryEvaluationResult,
    "replan": ReplanEvaluationResult,
    "retrieval": RetrievalEvaluationResult,
}
