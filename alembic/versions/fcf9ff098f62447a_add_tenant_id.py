"""add_tenant_id_to_workflow_executions

Revision ID: fcf9ff098f62447a
Revises: merge_heads_third
Create Date: 2026-05-30 14:00:00.000000

Adds tenant_id column to workflow_executions table (ORM model change
from PR #735) and removes the composite index on workflow_nodes that
the ORM no longer declares (index is replaced by per-column indexes).

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "fcf9ff098f62447a"
down_revision: Union[str, None] = "merge_heads_third"
branch_labels: Union[str | Sequence[str], None] = None
depends_on: Union[str | Sequence[str], None] = None


def upgrade() -> None:
    # Add tenant_id column with a server default so existing rows are not
    # orphaned by the NOT NULL constraint.  All existing executions are
    # assigned to tenant_id=0 (a sentinel — real multi-tenant routing is
    # introduced in the same PR that adds this column).
    op.add_column(
        "workflow_executions",
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("workflow_executions", "tenant_id", server_default=None)
    op.create_index(
        "ix_workflow_executions_tenant_id",
        "workflow_executions",
        ["tenant_id"],
        unique=False,
    )
    # The ORM no longer declares the composite (tenant_id, workflow_id) index
    # on workflow_nodes — the individual ix_workflow_nodes_tenant_id index
    # is sufficient.  Drop it to eliminate the drift.
    op.drop_index(
        "ix_workflow_nodes_tenant_id_workflow_id",
        table_name="workflow_nodes",
    )


def downgrade() -> None:
    op.create_index(
        op.f("ix_workflow_nodes_tenant_id_workflow_id"),
        "workflow_nodes",
        ["tenant_id", "workflow_id"],
        unique=False,
    )
    op.drop_index("ix_workflow_executions_tenant_id", table_name="workflow_executions")
    op.drop_column("workflow_executions", "tenant_id")