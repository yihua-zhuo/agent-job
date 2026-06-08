"""workflows: add ix_workflows_tenant_id_status composite index

Revision ID: a1c2d3e4f5a7
Revises: 045507a9a536
Create Date: 2026-06-07 12:00:00.000000

Adds the composite index declared in WorkflowModel.__table_args__. The
DB was missing the index after migration b2c3dce4b714, so the model
was ahead of the schema for this single field.

CREATE INDEX CONCURRENTLY is required: PostgreSQL refuses it inside a
transaction block, and a non-CONCURRENTLY index on a populated table
takes an ACCESS EXCLUSIVE lock that blocks reads. CONCURRENTLY is
non-transactional by design, so this migration sets
``transaction_per_migration = False`` to keep Alembic from wrapping the
DDL in BEGIN/COMMIT.

The companion migration a1c2d3e4f5a8_workflow_created_by_nullable.py
runs after this one and uses the default transactional wrapping for
its alter_column step, so the two drift concerns are independently
testable and roll back independently.
"""

from typing import Sequence, Union

from sqlalchemy import text

from alembic import op


revision: str = "a1c2d3e4f5a7"
down_revision: Union[str, None] = "045507a9a536"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# CONCURRENTLY cannot run inside a transaction block, so this migration
# must skip Alembic's per-migration transaction wrapping.
transaction_per_migration = False


def upgrade() -> None:
    """Add the composite index. Guarded for re-runs / partial application."""
    bind = op.get_bind()
    exists = bind.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": "ix_workflows_tenant_id_status"},
    ).first()
    if exists is None:
        op.create_index(
            op.f("ix_workflows_tenant_id_status"),
            "workflows",
            ["tenant_id", "status"],
            unique=False,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Drop the composite index (CONCURRENTLY to avoid an ACCESS
    EXCLUSIVE lock on a populated table during rollback). Guarded for
    partial-application scenarios where the index is already absent."""
    bind = op.get_bind()
    exists = bind.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": "ix_workflows_tenant_id_status"},
    ).first()
    if exists is not None:
        op.drop_index(
            op.f("ix_workflows_tenant_id_status"),
            table_name="workflows",
            postgresql_concurrently=True,
        )
