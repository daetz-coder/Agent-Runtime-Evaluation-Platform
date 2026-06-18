"""
Database ORM models for Agent Evaluation Platform.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Text, Float, Integer, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.database import Base


def _utcnow() -> datetime:
    """返回带 UTC 时区信息的时间戳，确保 JSON 序列化后含 '+00:00' 后缀。"""
    return datetime.now(timezone.utc)


class TaskStatus(str, enum.Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class EvaluationStatus(str, enum.Enum):
    """Evaluation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTask(Base):
    """Agent task model."""
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    trajectory: Mapped[List["AgentTrajectory"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    evaluations: Mapped[List["Evaluation"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class AgentTrajectory(Base):
    """Agent execution trajectory (steps)."""
    __tablename__ = "agent_trajectories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_tasks.id"))
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "plan", "tool_call", "think", "replan"
    action_detail: Mapped[dict] = mapped_column(JSON, nullable=False)
    observation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    task: Mapped["AgentTask"] = relationship(back_populates="trajectory")


class Evaluation(Base):
    """Evaluation results for a task."""
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_tasks.id"))
    status: Mapped[EvaluationStatus] = mapped_column(SQLEnum(EvaluationStatus), default=EvaluationStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scores
    planning_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tactical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tool_use_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    replan_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Detailed feedback
    planning_feedback: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tactical_feedback: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tool_use_feedback: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    memory_feedback: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    replan_feedback: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    task: Mapped["AgentTask"] = relationship(back_populates="evaluations")
