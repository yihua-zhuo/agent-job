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

from sqlalchemy import text

from alembic import op


revision: str = "b3c4d5e6f708"
down_revision: Union[str, None] = "a1c2d3e4f5a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_constraint_name(table_name: str, column_name: str) -> str | None:
    """Return the actual FK constraint name for table_name/column_name, or None.

    Looks up pg_constraint to find a single FK constraint on the given column.
    Returns None if no constraint exists. If multiple constraints are found
    (which would be a schema problem in its own right), we return the first
    match and let the caller decide — Alembic's batch_alter_table will surface
    a clear error.
    """
    bind = op.get_bind()
    row = bind.execute(
        text(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = :table::regclass
              AND contype = 'f'
              AND conkey = ARRAY[(SELECT attnum FROM pg_attribute
                                   WHERE attrelid = :table::regclass
                                     AND attname = :column)]::smallint[]
            LIMIT 1
            """
        ),
        {"table": table_name, "column": column_name},
    ).first()
    return row[0] if row is not None else None


def upgrade() -> None:
    """Drop and recreate the FK with ondelete='CASCADE'.

    Wrapped in batch_alter_table so the constraint change is atomic:
    if create_foreign_key fails, the dropped constraint is restored
    in the same transaction and the column is never left without
    referential integrity. The constraint name is resolved at runtime
    so a rename by a concurrent migration doesn't crash this one.
    """
    fk_name = _fk_constraint_name("workflow_executions", "tenant_id")
    with op.batch_alter_table("workflow_executions") as batch_op:
        if fk_name is not None:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_workflow_executions_tenant_id",
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
    fk_name = _fk_constraint_name("workflow_executions", "tenant_id")
    with op.batch_alter_table("workflow_executions") as batch_op:
        if fk_name is not None:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        # The ondelete value here matches the original pre-drift
        # state from 9e805b1493a6 (no ondelete = NO ACTION).
        batch_op.create_foreign_key(
            "fk_workflow_executions_tenant_id",
            "tenants",
            ["tenant_id"],
            ["id"],
        )
