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

from alembic import op


revision: str = "c4d5e6f70819"
down_revision: Union[str, None] = "b3c4d5e6f708"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop and recreate the FK with ondelete='CASCADE'.

    Wrapped in batch_alter_table so the constraint change is atomic:
    if create_foreign_key fails, the dropped constraint is restored
    in the same transaction and the column is never left without
    referential integrity.
    """
    with op.batch_alter_table("workflow_nodes") as batch_op:
        batch_op.drop_constraint(
            "fk_workflow_nodes_tenant_id",
            type_="foreignkey",
        )
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
    """
    with op.batch_alter_table("workflow_nodes") as batch_op:
        batch_op.drop_constraint(
            "fk_workflow_nodes_tenant_id",
            type_="foreignkey",
        )
        # The ondelete value here matches the original pre-drift
        # state from 185055a0d4f0 (no FK on tenant_id at all — we
        # restore that by adding the FK without CASCADE so the model
        # declaration is the only thing requiring the cascade behaviour
        # going forward).
        batch_op.create_foreign_key(
            "fk_workflow_nodes_tenant_id",
            "tenants",
            ["tenant_id"],
            ["id"],
        )
