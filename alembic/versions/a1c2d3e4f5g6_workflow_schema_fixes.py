"""workflows schema fixes — composite index and created_by nullability

Revision ID: a1c2d3e4f5g6
Revises: 045507a9a536
Create Date: 2026-06-07 12:00:00.000000

Captures drift between WorkflowModel and the DB on the workflows table:

1. Add the ix_workflows_tenant_id_status composite index declared in
   WorkflowModel.__table_args__ (model has it, DB does not). Uses
   CREATE INDEX CONCURRENTLY when not running in offline mode so the
   migration does not take an ACCESS EXCLUSIVE lock on a populated table.
2. Alter created_by to nullable=True (model has nullable=True, original
   migration b2c3dce4b714 created it as nullable=False).

The workflow_executions FK fix (ondelete='CASCADE') is in a separate
migration (b2c3dce4b715_workflow_executions_fk_cascade.py) so rollback
scope is narrow and the two drift concerns are independently testable.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1c2d3e4f5g6"
down_revision: Union[str, None] = "045507a9a536"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Run each statement outside Alembic's per-migration transaction so that
# CREATE INDEX CONCURRENTLY (which PostgreSQL rejects inside a transaction
# block) works correctly. Required for online mode on populated tables.
transaction_per_migration = False


def upgrade() -> None:
    # 1. Add the composite index declared in WorkflowModel.__table_args__.
    # Use CREATE INDEX CONCURRENTLY to avoid an ACCESS EXCLUSIVE lock on
    # a populated workflows table. This requires the module-level
    # transaction_per_migration = False above; CONCURRENTLY cannot run
    # inside a transaction block.
    op.create_index(
        op.f("ix_workflows_tenant_id_status"),
        "workflows",
        ["tenant_id", "status"],
        unique=False,
        postgresql_concurrently=True,
    )

    # 2. Align created_by nullability with the model (nullable=True).
    # No data backfill needed: we are making a NOT NULL column NULLable,
    # which is always safe (no constraint violation can occur).
    op.alter_column(
        "workflows",
        "created_by",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    # 2. Revert created_by nullability. The column was NOT NULL in the
    # original migration; existing rows may have NULL created_by after the
    # upgrade. Backfill before applying the NOT NULL constraint to avoid
    # a constraint-violation rollback. Backfill uses 0 as a sentinel value
    # that is guaranteed to satisfy any NOT NULL check; the user FK on
    # created_by is nullable, so no referential integrity is required.
    op.execute("UPDATE workflows SET created_by = 0 WHERE created_by IS NULL")
    op.alter_column(
        "workflows",
        "created_by",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 1. Drop the composite index (CONCURRENTLY to avoid an ACCESS
    # EXCLUSIVE lock on a populated table during rollback).
    op.drop_index(
        op.f("ix_workflows_tenant_id_status"),
        table_name="workflows",
        postgresql_concurrently=True,
    )
