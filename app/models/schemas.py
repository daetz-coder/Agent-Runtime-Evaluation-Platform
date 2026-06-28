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
    workspace_id: Optional[str] = None
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
    include_details: bool = Field(True, description="Include detailed feedback")
    use_stream: bool = Field(
        False,
        description="When true, skip background task; client drives POST /evaluations/stream",
    )


class StreamEvaluationRequest(BaseModel):
    """Schema for SSE streaming evaluation."""

    task_id: str
    evaluation_id: Optional[str] = Field(None, description="Existing IN_PROGRESS evaluation to persist into")


# ============== Agent Runtime (Sandbox) Schemas ==============


class SandboxEvalRequest(BaseModel):
    """Request schema for sandbox-based agent evaluation (Agent in Sandbox)."""

    goal: str = Field(..., description="The goal/objective for the agent to achieve")
    model: Optional[str] = Field(None, description="LLM model name (default: from config)")
    provider: Optional[str] = Field(None, description="LLM provider: deepseek/openai/anthropic/zhipuai/qwen")
    workspace_files: Optional[Dict[str, str]] = Field(
        None,
        description="Initial files for /workspace {relative_path: content}",
    )
    tools: Optional[List[str]] = Field(
        None,
        description="Allowed tools: python_execute, bash_execute, file_read, file_write, file_list",
    )
    max_steps: Optional[int] = Field(None, ge=1, le=100, description="Max agent steps (default: 20)")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the agent")
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="LLM sampling temperature")


class AgentRunInfo(BaseModel):
    """Agent run metadata included in the sandbox evaluation response."""

    success: bool
    steps_taken: int
    duration_ms: float
    final_answer: str
    workspace_state: Dict[str, Any] = Field(default_factory=dict)
    workspace_files: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None


class SandboxEvalResponse(BaseModel):
    """Response schema for sandbox-based agent evaluation."""

    task_id: str
    evaluation_id: str
    status: str
    agent_run: AgentRunInfo
    evaluation: Optional[OverallEvaluation] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class PlanningScore(BaseModel):
    """Planning evaluation score."""

    coverage: float = Field(..., ge=0, le=100, description="Coverage of key milestones")
    ordering: float = Field(..., ge=0, le=100, description="Logical ordering of steps")
    granularity: float = Field(..., ge=0, le=100, description="Appropriate level of detail")
    completeness: float = Field(..., ge=0, le=100, description="Completeness of plan")
    overall: float = Field(..., ge=0, le=100, description="Overall planning score")
    feedback: str = Field(..., description="Detailed feedback")


class TacticalScore(BaseModel):
    """Tactical evaluation score (next action quality)."""

    relevance: float = Field(..., ge=0, le=100, description="Relevance of next action")
    efficiency: float = Field(..., ge=0, le=100, description="Efficiency of action choice")
    correctness: float = Field(..., ge=0, le=100, description="Correctness of action")
    overall: float = Field(..., ge=0, le=100, description="Overall tactical score")
    feedback: str = Field(..., description="Detailed feedback")


class ToolUseScore(BaseModel):
    """Tool use evaluation score."""

    selection_quality: float = Field(..., ge=0, le=100, description="Quality of tool selection")
    parameter_accuracy: float = Field(..., ge=0, le=100, description="Accuracy of tool parameters")
    result_utilization: float = Field(..., ge=0, le=100, description="How well results are used")
    overall: float = Field(..., ge=0, le=100, description="Overall tool use score")
    feedback: str = Field(..., description="Detailed feedback")
    sandbox_results: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Sandbox execution results (None = sandbox disabled or no code detected)",
    )


class MemoryScore(BaseModel):
    """Memory evaluation score."""

    retention: float = Field(..., ge=0, le=100, description="Key fact retention")
    relevance: float = Field(..., ge=0, le=100, description="Relevance of recalled information")
    consistency: float = Field(..., ge=0, le=100, description="Consistency with previous context")
    overall: float = Field(..., ge=0, le=100, description="Overall memory score")
    feedback: str = Field(..., description="Detailed feedback")


class ReplanScore(BaseModel):
    """Replan evaluation score."""

    trigger_appropriateness: float = Field(..., ge=0, le=100, description="Was replan triggered appropriately?")
    adaptation_quality: float = Field(..., ge=0, le=100, description="Quality of plan adaptation")
    learning_from_failure: float = Field(..., ge=0, le=100, description="Did agent learn from failures?")
    overall: float = Field(..., ge=0, le=100, description="Overall replan score")
    feedback: str = Field(..., description="Detailed feedback")


class RetrievalScore(BaseModel):
    """Retrieval quality evaluation (RAG Eval)."""

    relevance: float = Field(0, ge=0, le=100)
    evidence_accuracy: float = Field(0, ge=0, le=100)
    coverage: float = Field(0, ge=0, le=100)
    overall: float = Field(0, ge=0, le=100)
    feedback: str = Field("")
    hallucination_detected: bool = Field(False)
    missing_info: List[str] = Field(default_factory=list)


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

    model_config = ConfigDict(from_attributes=True)


# ============== Report Schemas ==============


class EvaluationSummary(BaseModel):
    """Summary of multiple evaluations."""

    total_evaluations: int
    average_scores: Dict[str, float]
    score_distribution: Dict[str, List[float]]
    top_issues: List[str]
    recommendations: List[str]
