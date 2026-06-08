"""workflow schema fixes

Revision ID: a1c2d3e4f5g6
Revises: 045507a9a536
Create Date: 2026-06-07 12:00:00.000000

Captures drift between WorkflowModel and the DB:

1. workflows: create the ix_workflows_tenant_id_status composite index
   declared in WorkflowModel.__table_args__ (model has it, DB does not).
2. workflows: alter created_by to nullable=True (model has nullable=True,
   original migration b2c3dce4b714 created it as nullable=False).
3. workflow_executions: recreate the tenant_id FK with ondelete='CASCADE'
   to match the model (migration 9e805b1493a6 created the FK without
   CASCADE).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1c2d3e4f5g6"
down_revision: Union[str, None] = "045507a9a536"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add the composite index declared in WorkflowModel.__table_args__
    op.create_index(
        op.f("ix_workflows_tenant_id_status"),
        "workflows",
        ["tenant_id", "status"],
        unique=False,
    )

    # 2. Align created_by nullability with the model (nullable=True)
    op.alter_column(
        "workflows",
        "created_by",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 3. Recreate workflow_executions.tenant_id FK with ondelete='CASCADE'
    op.drop_constraint(
        "fk_workflow_executions_tenant_id",
        "workflow_executions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_workflow_executions_tenant_id",
        "workflow_executions",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 3. Revert FK to no CASCADE
    op.drop_constraint(
        "fk_workflow_executions_tenant_id",
        "workflow_executions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_workflow_executions_tenant_id",
        "workflow_executions",
        "tenants",
        ["tenant_id"],
        ["id"],
    )

    # 2. Revert created_by nullability
    op.alter_column(
        "workflows",
        "created_by",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 1. Drop the composite index
    op.drop_index(
        op.f("ix_workflows_tenant_id_status"),
        table_name="workflows",
    )
