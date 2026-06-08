"""workflows: align created_by nullability with WorkflowModel

Revision ID: a1c2d3e4f5a8
Revises: a1c2d3e4f5a7
Create Date: 2026-06-07 12:00:00.000000

Migration b2c3dce4b714 created the workflows.created_by column with
nullable=False; WorkflowModel declares nullable=True. This migration
closes the gap.

Split from a1c2d3e4f5a7 so the two drift concerns (workflows composite
index and created_by nullability) can be tested and rolled back
independently. The index migration requires
transaction_per_migration = False (for CONCURRENTLY); this migration
uses the default transactional wrapping.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op


revision: str = "a1c2d3e4f5a8"
down_revision: Union[str, None] = "a1c2d3e4f5a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make workflows.created_by NULLable to match WorkflowModel.

    No data backfill needed: we are making a NOT NULL column NULLable,
    which is always safe (no constraint violation can occur).
    """
    op.alter_column(
        "workflows",
        "created_by",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    """Revert created_by to NOT NULL.

    After the upgrade, existing rows may have NULL created_by. The
    downgrade backfills NULLs to the smallest existing user id in the
    same tenant when possible; if no users exist for a tenant, the
    backfill uses NULL (which causes the alter_column to fail and
    surface the issue to the operator rather than silently inserting
    a fake sentinel value).

    The original migration (b2c3dce4b714) used nullable=False with no
    DB default, so any pre-existing NULL row would already block the
    constraint. We use a per-tenant min(user_id) backfill so the
    inserted id is always a real, referentially-valid user row.
    """
    bind = op.get_bind()
    # Backfill NULL created_by with the smallest user id in the same
    # tenant. Falls back to NULL (which will fail the NOT NULL
    # constraint) for orphan tenants with no users.
    bind.execute(
        text(
            """
            UPDATE workflows w
            SET created_by = COALESCE(
                (SELECT MIN(u.id) FROM users u WHERE u.tenant_id = w.tenant_id),
                w.created_by
            )
            WHERE w.created_by IS NULL
            """
        )
    )
    op.alter_column(
        "workflows",
        "created_by",
        existing_type=sa.Integer(),
        nullable=False,
    )
