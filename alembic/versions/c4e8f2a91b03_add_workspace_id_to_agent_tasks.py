"""add workspace_id to agent_tasks

Revision ID: c4e8f2a91b03
Revises: 03ffaa8a77bf
Create Date: 2026-06-26 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8f2a91b03"
down_revision: Union[str, Sequence[str], None] = "03ffaa8a77bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add workspace_id FK to agent_tasks."""
    with op.batch_alter_table("agent_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_agent_tasks_workspace_id", ["workspace_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_agent_tasks_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
        )


def downgrade() -> None:
    """Remove workspace_id from agent_tasks."""
    with op.batch_alter_table("agent_tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_agent_tasks_workspace_id", type_="foreignkey")
        batch_op.drop_index("ix_agent_tasks_workspace_id")
        batch_op.drop_column("workspace_id")
