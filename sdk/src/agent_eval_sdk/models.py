"""
SDK Data Models - Compatible with backend API.

These models are aligned with:
- app/models/schemas.py (TrajectoryStep, TaskCreate, etc.)
- app/db/models.py (AgentTrajectory)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Trajectory step action types."""
    PLAN = "plan"
    TOOL_CALL = "tool_call"
    THINK = "think"
    REPLAN = "replan"


class TrajectoryStep(BaseModel):
    """
    Single trajectory step.

    Aligned with backend: app/models/schemas.py::TrajectoryStep
    """
    step_number: int
    action_type: str  # "plan" | "tool_call" | "think" | "replan"
    action_detail: Dict[str, Any]
    observation: Optional[str] = None
    timestamp: Optional[datetime] = None

    def model_dump_for_api(self) -> Dict[str, Any]:
        """Serialize for API transmission."""
        data = self.model_dump()
        if data.get("timestamp") and isinstance(data["timestamp"], datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data


class TaskCreate(BaseModel):
    """
    Create task request body.

    Aligned with backend: app/models/schemas.py::TaskCreate
    """
    goal: str
    context: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    """Task creation response."""
    id: str
    goal: str
    context: Optional[Dict[str, Any]] = None
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class EvaluationRequest(BaseModel):
    """Evaluation request body."""
    task_id: str
    include_details: bool = True


class EvaluationResponse(BaseModel):
    """Evaluation response."""
    id: str
    task_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    evaluation: Optional[Dict[str, Any]] = None


class SDKConfig(BaseModel):
    """SDK runtime configuration."""
    # Backend connection
    api_base_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    api_timeout: float = 30.0

    # Batch reporting
    batch_size: int = 20
    flush_interval: float = 5.0
    max_queue_size: int = 10000

    # Retry
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0

    # Behavior
    auto_start_task: bool = True
    auto_run_evaluation: bool = False
    collect_llm_calls: bool = True
    collect_tool_calls: bool = True

    # Logging
    log_level: str = "WARNING"
