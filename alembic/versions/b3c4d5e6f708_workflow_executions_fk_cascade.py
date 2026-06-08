"""workflow_executions: recreate tenant_id FK with ondelete='CASCADE'

Revision ID: b3c4d5e6f708
Revises: a1c2d3e4f5a8
Create Date: 2026-06-08 12:00:00.000000

Aligns the workflow_executions.tenant_id foreign key with
WorkflowExecutionModel by recreating it with ondelete='CASCADE'.
Migration 9e805b1493a6 created the FK without CASCADE; the model
declares ondelete='CASCADE'.

Retention policy: workflow_executions are operational state, not
audit data. When a tenant is removed, all of its execution rows are
removed automatically — matching the model definition and avoiding
orphan rows. No audit/retention policy applies here; this is a
deliberate design decision. See WorkflowExecutionModel docstring for
context.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b3c4d5e6f708"
down_revision: Union[str, None] = "a1c2d3e4f5a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Original FK name created by migration 9e805b1493a6. The drop+create
# pair in upgrade()/downgrade() both reference the same name (PostgreSQL
# renames the constraint to whatever create_foreign_key supplies).
_FK_NAME = "fk_workflow_executions_tenant_id"


def upgrade() -> None:
    """Drop and recreate the FK with ondelete='CASCADE'.

    The drop and create run in the same Alembic transaction, so the
    column is never left without referential integrity.
    """
    with op.batch_alter_table("workflow_executions") as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(
            _FK_NAME,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Restore the FK to the pre-drift state defined by migration
    9e805b1493a6 (no ondelete behavior specified — i.e. default NO
    ACTION). This matches the original definition before this
    migration added CASCADE.
    """
    with op.batch_alter_table("workflow_executions") as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
        # The ondelete value here matches the original pre-drift
        # state from 9e805b1493a6 (no ondelete = NO ACTION).
        batch_op.create_foreign_key(
            _FK_NAME,
            "tenants",
            ["tenant_id"],
            ["id"],
        )
