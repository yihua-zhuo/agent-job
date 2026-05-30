"""add tenant_id to workflow_executions, declare composite index on workflow_nodes

Revision ID: 9e805b1493a6
Revises: merge_heads_third
Create Date: 2026-05-30 12:12:00.000000

Drift captured:
1. workflow_executions.tenant_id — the ORM model added this column
   (default=0, nullable=False, index=True).  Existing rows get server_default=0.
2. ix_workflow_nodes_tenant_id_workflow_id — the migration created this composite
   index in 185055a0d4f0 but the ORM never declared it in __table_args__, so alembic
   sees it as unexpected and would try to drop it.  Declaring the index in the ORM
   __table_args__ stops the false-positive drift signal; no migration op needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9e805b1493a6"
down_revision: str | None = "merge_heads_third"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # workflow_executions: add tenant_id column and its index
    op.add_column(
        "workflow_executions",
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        op.f("ix_workflow_executions_tenant_id"),
        "workflow_executions",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_executions_tenant_id"), table_name="workflow_executions")
    op.drop_column("workflow_executions", "tenant_id")
