"""add_agent_tasks

Revision ID: add_agent_tasks_001
Revises: 9d8e7f6a5b3c, c94d682d4b03
Create Date: 2026-05-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_agent_tasks_001"
down_revision: str | Sequence[str] | None = ("9d8e7f6a5b3c", "c94d682d4b03")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column(
            "subtasks",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tasks_tenant_id", "agent_tasks", ["tenant_id"], unique=False)
    op.create_index(
        "ix_agent_tasks_task_id_tenant_id",
        "agent_tasks",
        ["task_id", "tenant_id"],
        unique=True,
    )
    op.create_index(op.f("ix_agent_tasks_task_id"), "agent_tasks", ["task_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_tasks_task_id"), table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_task_id_tenant_id", table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_tenant_id", table_name="agent_tasks")
    op.drop_table("agent_tasks")
