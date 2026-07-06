"""remove workspace tables and columns

Revision ID: a1b2c3d4e5f6
Revises: 29537dc804f8
Create Date: 2026-07-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '29537dc804f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """移除多租户相关表和列。

    - 删除 agent_tasks.workspace_id 外键、索引、列
    - 删除 audit_logs 表及其索引
    - 删除 workspace_members 表
    - 删除 workspaces 表
    """
    # 1. 删除 agent_tasks 上的 workspace_id 关联
    with op.batch_alter_table("agent_tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_agent_tasks_workspace_id", type_="foreignkey")
        batch_op.drop_index("ix_agent_tasks_workspace_id")
        batch_op.drop_column("workspace_id")

    # 2. 删除 audit_logs 表（先删索引）
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_workspace_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    # 3. 删除 workspace_members 表
    op.drop_table("workspace_members")

    # 4. 删除 workspaces 表
    op.drop_table("workspaces")


def downgrade() -> None:
    """回滚：重建多租户表和列。"""
    # 重建 workspaces 表
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("api_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sandbox_quota", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_steps_per_eval", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("eval_count_limit_monthly", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("storage_limit_mb", sa.Integer(), nullable=False, server_default="1024"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key"),
    )

    # 重建 workspace_members 表
    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="evaluator"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 重建 audit_logs 表
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # 重建 agent_tasks.workspace_id
    with op.batch_alter_table("agent_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_agent_tasks_workspace_id", ["workspace_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_agent_tasks_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
        )
