"""initial schema

Revision ID: 68b1d0ea2480
Revises: 
Create Date: 2026-06-23 12:05:26.319270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68b1d0ea2480'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create core evaluation tables."""
    op.create_table(
        'agent_tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'agent_trajectories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('action_detail', sa.JSON(), nullable=False),
        sa.Column('observation', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'evaluations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('stream_mode', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('planning_score', sa.Float(), nullable=True),
        sa.Column('tactical_score', sa.Float(), nullable=True),
        sa.Column('tool_use_score', sa.Float(), nullable=True),
        sa.Column('memory_score', sa.Float(), nullable=True),
        sa.Column('replan_score', sa.Float(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('planning_feedback', sa.JSON(), nullable=True),
        sa.Column('tactical_feedback', sa.JSON(), nullable=True),
        sa.Column('tool_use_feedback', sa.JSON(), nullable=True),
        sa.Column('memory_feedback', sa.JSON(), nullable=True),
        sa.Column('replan_feedback', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Drop core evaluation tables."""
    op.drop_table('evaluations')
    op.drop_table('agent_trajectories')
    op.drop_table('agent_tasks')
