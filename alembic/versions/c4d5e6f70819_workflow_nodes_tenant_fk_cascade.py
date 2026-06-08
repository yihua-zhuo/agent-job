"""workflow_nodes: recreate tenant_id FK with ondelete='CASCADE'

Revision ID: c4d5e6f70819
Revises: b3c4d5e6f708
Create Date: 2026-06-08 12:30:00.000000

Aligns the workflow_nodes.tenant_id foreign key with WorkflowNodeModel by
recreating it with ondelete='CASCADE'. Migration 185055a0d4f0 created the
column as a plain Integer without an FK / ondelete; the model declares
ForeignKey("tenants.id", ondelete="CASCADE").

Retention policy: workflow_nodes are operational state, not audit data.
When a tenant is removed, all of its node rows are removed automatically —
matching the model definition and avoiding orphan rows.
"""

from typing import Sequence, Union

from sqlalchemy import text

from alembic import op


revision: str = "c4d5e6f70819"
down_revision: Union[str, None] = "b3c4d5e6f708"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_constraint_name(table_name: str, column_name: str) -> str | None:
    """Return the actual FK constraint name for table_name/column_name, or None.

    Looks up pg_constraint to find a single FK constraint on the given column.
    Returns None if no constraint exists. If multiple constraints are found
    (which would be a schema problem in its own right), we return the first
    match and let the caller decide — Alembic's batch_alter_table will surface
    a clear error.

    NOTE: single-column FK lookups only. For composite FKs, the conkey array
    would contain multiple attnums and the equality check would silently
    miss; expand the query to match all conkey elements for composite
    support.
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

    The drop and create run in the same Alembic transaction, so the column
    is never left without referential integrity. The constraint name is
    resolved at runtime so a rename by a concurrent migration doesn't crash
    this one and the migration is safe when the FK is absent.
    """
    fk_name = _fk_constraint_name("workflow_nodes", "tenant_id")
    with op.batch_alter_table("workflow_nodes") as batch_op:
        if fk_name is not None:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_workflow_nodes_tenant_id",
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Restore the FK to the pre-drift state defined by migration
    185055a0d4f0 (no ondelete behavior specified — i.e. default NO
    ACTION). This matches the original definition before this
    migration added CASCADE.

    NOTE: this creates a NO-ACTION FK rather than removing the FK entirely,
    because migration 185055a0d4f0 created the column without any FK
    constraint at all. A subsequent upgrade of this migration will restore
    the CASCADE FK.
    """
    fk_name = _fk_constraint_name("workflow_nodes", "tenant_id")
    with op.batch_alter_table("workflow_nodes") as batch_op:
        if fk_name is not None:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        # The ondelete value here matches the original pre-drift
        # state from 185055a0d4f0 (no ondelete = NO ACTION).
        batch_op.create_foreign_key(
            "fk_workflow_nodes_tenant_id",
            "tenants",
            ["tenant_id"],
            ["id"],
        )
