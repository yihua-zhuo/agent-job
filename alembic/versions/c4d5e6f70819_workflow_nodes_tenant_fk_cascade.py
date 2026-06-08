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


# FK name used for both the CASCADE form (upgrade) and the NO-ACTION
# form (downgrade). 185055a0d4f0 did not create a named constraint for
# this column, so a concurrent/adjacent migration that already added a
# constraint under a different name will be the one being dropped.
_FK_NAME = "fk_workflow_nodes_tenant_id"


def _find_existing_fk_name(table_name: str) -> str | None:
    """Return the first FK constraint name on *table_name*'s tenant_id, or None.

    Looks up pg_constraint to find a single FK constraint on the tenant_id
    column. Returns None if no constraint exists. The downgrade path uses
    this to drop an FK that may have been added by a different migration
    under a different name (the original 185055a0d4f0 created no FK at all).
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
                                     AND attname = 'tenant_id')]::smallint[]
            LIMIT 1
            """
        ),
        {"table": table_name},
    ).first()
    return row[0] if row is not None else None


def upgrade() -> None:
    """Add the missing tenant_id FK with ondelete='CASCADE'.

    Pre-flight: bail out with a clear error if any workflow_nodes row
    references a tenant_id that no longer exists in the tenants table —
    PostgreSQL would otherwise reject the constraint creation with a
    less actionable error.

    The drop and create run in the same Alembic transaction, so the
    column is never left without referential integrity. The constraint
    name is resolved at runtime so a rename by a concurrent migration
    doesn't crash this one and the migration is safe when the FK is
    absent.
    """
    bind = op.get_bind()
    orphan = bind.execute(
        text(
            """
            SELECT 1 FROM workflow_nodes wn
            LEFT JOIN tenants t ON t.id = wn.tenant_id
            WHERE t.id IS NULL
            LIMIT 1
            """
        )
    ).first()
    if orphan is not None:
        raise RuntimeError(
            "Cannot create workflow_nodes.tenant_id FK: orphan rows reference "
            "non-existent tenants. Clean up workflow_nodes with missing "
            "tenant_ids before running this migration."
        )

    fk_name = _find_existing_fk_name("workflow_nodes")
    with op.batch_alter_table("workflow_nodes") as batch_op:
        if fk_name is not None:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            _FK_NAME,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Restore the FK to the pre-drift state defined by migration
    185055a0d4f0.

    NOTE on downgrade truthfulness: 185055a0d4f0 created the column with
    no FK constraint at all. A true revert would therefore *remove* the
    FK (not recreate it with NO ACTION). We choose to recreate a NO-ACTION
    FK here because the column is part of the broader tenant-id pattern
    and removing the FK entirely would be a regression for any subsequent
    migration that assumes FK enforcement is in place. A subsequent upgrade
    of this migration will restore the CASCADE FK.
    """
    fk_name = _find_existing_fk_name("workflow_nodes")
    with op.batch_alter_table("workflow_nodes") as batch_op:
        if fk_name is not None:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            _FK_NAME,
            "tenants",
            ["tenant_id"],
            ["id"],
        )
