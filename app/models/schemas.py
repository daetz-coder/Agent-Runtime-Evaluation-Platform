"""
Pydantic schemas for API request/response validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============== Task Schemas ==============


class TaskCreate(BaseModel):
    """Schema for creating a new agent task."""

    id: Optional[str] = Field(None, description="Optional client-provided task ID (idempotent create)")
    goal: str = Field(..., description="The goal/objective for the agent to achieve")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the task")


class TaskUpdate(BaseModel):
    """Schema for updating an existing task."""

    goal: Optional[str] = Field(None, description="Updated goal/objective")
    context: Optional[Dict[str, Any]] = Field(None, description="Updated context")
    status: Optional[str] = Field(None, description="New status: pending/running/completed/failed/timeout")


class TaskResponse(BaseModel):
    """Schema for task response."""

    id: str
    goal: str
    context: Optional[Dict[str, Any]] = None
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============== Trajectory Schemas ==============


class TrajectoryStep(BaseModel):
    """Schema for a single trajectory step.

    Supported action_type values (defined in app.models.action_types.ActionType):
    - plan              — 初始规划（milestones / steps）
    - plan_update       — 动态规划更新（milestone 完成、下一步调整）
    - tool_call         — 工具调用（含工具名、输入参数）
    - tool_result       — 工具返回（独立记录工具输出）
    - memory_write      — 记忆写入（存入新信息）
    - memory_read       — 记忆读取（检索已有信息）
    - state_change      — 状态变化（含 before/after diff）
    - think             — 思考过程（推理、分析）
    - replan            — 重规划（修改原有计划）
    - failure           — 失败/异常事件
    - node_execute      — 节点执行（LangGraph 节点）
    - tool_decision     — 工具选择决策（LLM 决定调用哪个工具）
    """

    step_number: int
    action_type: str = Field(
        ...,
        description=(
            "Type of action. Supported: plan, plan_update, tool_call, tool_result, "
            "memory_write, memory_read, state_change, think, replan, failure, "
            "node_execute, tool_decision, retrieval, evidence"
        ),
    )
    action_detail: Dict[str, Any]
    observation: Optional[Any] = None
    timestamp: Optional[datetime] = None


class TrajectoryCreate(BaseModel):
    """Schema for creating trajectory steps."""

    steps: List[TrajectoryStep]


# ============== Evaluation Schemas ==============


class EvaluationRequest(BaseModel):
    """Schema for evaluation request."""

    task_id: str
    use_stream: bool = Field(
        False,
        description="When true, skip background task; client drives POST /evaluations/stream",
    )


class StreamEvaluationRequest(BaseModel):
    """Schema for SSE streaming evaluation."""

    task_id: str
    evaluation_id: Optional[str] = Field(None, description="Existing IN_PROGRESS evaluation to persist into")


class PlanningScore(BaseModel):
    """Planning evaluation score."""

    coverage: float = Field(..., ge=0, le=100, description="Coverage of key milestones")
    ordering: float = Field(..., ge=0, le=100, description="Logical ordering of steps")
    granularity: float = Field(..., ge=0, le=100, description="Appropriate level of detail")
    completeness: float = Field(..., ge=0, le=100, description="Completeness of plan")
    overall: float = Field(..., ge=0, le=100, description="Overall planning score")
    feedback: str = Field(..., description="Detailed feedback")
    llm_suggestions: List[str] = Field(default_factory=list, description="LLM-generated improvement suggestions")


class TacticalScore(BaseModel):
    """Tactical evaluation score (next action quality)."""

    relevance: float = Field(..., ge=0, le=100, description="Relevance of next action")
    efficiency: float = Field(..., ge=0, le=100, description="Efficiency of action choice")
    correctness: float = Field(..., ge=0, le=100, description="Correctness of action")
    overall: float = Field(..., ge=0, le=100, description="Overall tactical score")
    feedback: str = Field(..., description="Detailed feedback")
    llm_suggestions: List[str] = Field(default_factory=list, description="LLM-generated improvement suggestions")


class ToolUseScore(BaseModel):
    """Tool use evaluation score."""

    applicable: bool = Field(True, description="Whether tool use is applicable to this trajectory")
    not_applicable_reason: Optional[str] = Field(None, description="Reason this dimension is excluded")
    selection_quality: float = Field(..., ge=0, le=100, description="Quality of tool selection")
    parameter_accuracy: float = Field(..., ge=0, le=100, description="Accuracy of tool parameters")
    result_utilization: float = Field(..., ge=0, le=100, description="How well results are used")
    overall: float = Field(..., ge=0, le=100, description="Overall tool use score")
    feedback: str = Field(..., description="Detailed feedback")
    llm_suggestions: List[str] = Field(default_factory=list, description="LLM-generated improvement suggestions")


class MemoryScore(BaseModel):
    """Memory evaluation score."""

    retention: float = Field(..., ge=0, le=100, description="Key fact retention")
    relevance: float = Field(..., ge=0, le=100, description="Relevance of recalled information")
    consistency: float = Field(..., ge=0, le=100, description="Consistency with previous context")
    overall: float = Field(..., ge=0, le=100, description="Overall memory score")
    feedback: str = Field(..., description="Detailed feedback")
    llm_suggestions: List[str] = Field(default_factory=list, description="LLM-generated improvement suggestions")


class ReplanScore(BaseModel):
    """Replan evaluation score."""

    applicable: bool = Field(True, description="Whether replanning is applicable to this trajectory")
    not_applicable_reason: Optional[str] = Field(None, description="Reason this dimension is excluded")
    trigger_appropriateness: float = Field(..., ge=0, le=100, description="Was replan triggered appropriately?")
    adaptation_quality: float = Field(..., ge=0, le=100, description="Quality of plan adaptation")
    learning_from_failure: float = Field(..., ge=0, le=100, description="Did agent learn from failures?")
    overall: float = Field(..., ge=0, le=100, description="Overall replan score")
    feedback: str = Field(..., description="Detailed feedback")
    llm_suggestions: List[str] = Field(default_factory=list, description="LLM-generated improvement suggestions")


class RetrievalScore(BaseModel):
    """Retrieval quality evaluation (RAG Eval)."""

    applicable: bool = Field(True, description="Whether retrieval is applicable to this trajectory")
    not_applicable_reason: Optional[str] = Field(None, description="Reason this dimension is excluded")
    relevance: float = Field(0, ge=0, le=100)
    evidence_accuracy: float = Field(0, ge=0, le=100)
    coverage: float = Field(0, ge=0, le=100)
    overall: float = Field(0, ge=0, le=100)
    feedback: str = Field("")
    hallucination_detected: bool = Field(False)
    missing_info: List[str] = Field(default_factory=list)
    llm_suggestions: List[str] = Field(default_factory=list, description="LLM-generated improvement suggestions")


class OverallEvaluation(BaseModel):
    """Overall evaluation combining all dimensions."""

    planning: PlanningScore
    tactical: TacticalScore
    tool_use: ToolUseScore
    memory: MemoryScore
    replan: ReplanScore
    retrieval: Optional[RetrievalScore] = None
    overall_score: float = Field(..., ge=0, le=100, description="Weighted overall score")
    summary: str = Field(..., description="Overall evaluation summary")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")


class EvaluationResponse(BaseModel):
    """Schema for evaluation response."""

    id: str
    task_id: str
    status: str
    stream_mode: bool = False
    created_at: datetime
    completed_at: Optional[datetime] = None
    evaluation: Optional[OverallEvaluation] = None
    prompt_version: Optional[str] = Field(None, description="Agent prompt version used")
    model_name: Optional[str] = Field(None, description="LLM model used")
    model_provider: Optional[str] = Field(None, description="LLM provider used")

    model_config = ConfigDict(from_attributes=True)


class EvaluationListItem(BaseModel):
    """Lightweight evaluation item for list views."""

    id: str
    task_id: str
    task_goal: Optional[str] = None
    status: str
    stream_mode: bool = False
    created_at: datetime
    completed_at: Optional[datetime] = None
    overall_score: Optional[float] = None
    planning_score: Optional[float] = None
    tactical_score: Optional[float] = None
    tool_use_score: Optional[float] = None
    memory_score: Optional[float] = None
    replan_score: Optional[float] = None
    retrieval_score: Optional[float] = None
    prompt_version: Optional[str] = Field(None, description="Agent prompt version used")
    model_name: Optional[str] = Field(None, description="LLM model used")
    model_provider: Optional[str] = Field(None, description="LLM provider used")

    model_config = ConfigDict(from_attributes=True)


# ============== Report Schemas ==============


class EvaluationSummary(BaseModel):
    """Summary of multiple evaluations."""

    total_evaluations: int
    average_scores: Dict[str, float]
    score_distribution: Dict[str, List[float]]
    top_issues: List[str]
    recommendations: List[str]


# ============== Replay Debugger Schemas ==============


class LLMTraceInfo(BaseModel):
    """LLM trace data for a single trajectory step."""

    step_number: int
    action_type: str
    llm_prompt: str = Field(default="", description="Full prompt sent to the LLM before this action")
    llm_response: str = Field(default="", description="Raw response from the LLM")
    llm_model: str = Field(default="unknown", description="Model that generated the response")
    latency_ms: float = Field(default=0, description="LLM call latency in milliseconds")


class ReplayResponse(BaseModel):
    """Replay debug data for an evaluation."""

    task_id: str
    evaluation_id: str
    goal: str
    step_count: int
    steps: List[LLMTraceInfo]


# ============== Judge Transparency Schemas ==============


DIMENSION_NAMES = ["planning", "tactical", "tool_use", "memory", "replan", "retrieval"]


class JudgeRawData(BaseModel):
    """Raw judge LLM prompt and response for a single evaluation dimension."""

    dimension: str
    judge_prompt: str = Field(default="", description="Complete prompt sent to the judge LLM")
    judge_response: str = Field(default="", description="Raw JSON response from the judge LLM")
    judge_model: str = Field(default="unknown", description="Judge model name")
    score: Optional[float] = Field(None, description="The final score for this dimension")
    score_breakdown: Dict[str, float] = Field(default_factory=dict, description="Sub-dimension scores")


# ============== Diff Schemas ==============


class StepDiff(BaseModel):
    """A diff between two trajectory steps."""

    step_number: int
    change_type: str = Field(
        ...,
        description="One of: added, removed, changed, unchanged",
    )
    before: Optional[Dict[str, Any]] = Field(None, description="The step detail in the base trajectory")
    after: Optional[Dict[str, Any]] = Field(None, description="The step detail in the head trajectory")
    field_changes: List[str] = Field(default_factory=list, description="Which fields changed")


class TrajectoryDiffResponse(BaseModel):
    """Complete diff between two evaluation trajectories."""

    base_evaluation_id: str
    head_evaluation_id: str
    base_task_goal: str
    head_task_goal: str
    total_changes: int = 0
    steps_added: int = 0
    steps_removed: int = 0
    steps_modified: int = 0
    steps: List[StepDiff]


# ============== Incremental Evaluation Schemas ==============


class IncrementalEvalRequest(BaseModel):
    """Request an incremental evaluation — only re-evaluate changed dimensions."""

    base_evaluation_id: str = Field(..., description="Previous evaluation to compare against")
    head_task_id: str = Field(..., description="New task/trajectory to evaluate")
    force_dimensions: Optional[List[str]] = Field(
        None,
        description="Override: force re-evaluate these dimensions regardless of detected changes",
    )


class IncrementalEvalResponse(BaseModel):
    """Response from incremental evaluation."""

    evaluation_id: str
    task_id: str
    status: str
    overall_score: float
    reused_dimensions: List[str]
    re_evaluated_dimensions: List[str]
    changes_detected: List[str]
    diff_summary: TrajectoryDiffResponse
