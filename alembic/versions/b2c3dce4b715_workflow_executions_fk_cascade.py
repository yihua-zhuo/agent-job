"""workflow_executions: recreate tenant_id FK with ondelete='CASCADE'

Revision ID: b2c3dce4b715
Revises: a1c2d3e4f5g6
Create Date: 2026-06-08 12:00:00.000000

Aligns the workflow_executions.tenant_id foreign key with WorkflowExecutionModel
by recreating it with ondelete='CASCADE'. Migration 9e805b1493a6 created the
FK without CASCADE; the model declares ondelete='CASCADE'.

Split from a1c2d3e4f5g6 so the two drift concerns (workflows index/nullability
and workflow_executions FK) can be tested and rolled back independently.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b2c3dce4b715"
down_revision: Union[str, None] = "a1c2d3e4f5g6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
