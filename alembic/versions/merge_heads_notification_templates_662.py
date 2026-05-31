"""Merge notification_templates into the main timeline

Revision ID: merge_heads_notification_templates_662
Revises: 52b19ee00eaf, 5d575a161b5d
Create Date: 2026-05-31

Two heads are present:
  - 52b19ee00eaf  (merge_heads — linear head from prior merges, descends from 7b1a2c3d4e5f)
  - 5d575a161b5d  (add_notification_templates — stands alone, descends from e7f6a5b3c12d)

This revision merges both into a single head so that `alembic upgrade head`
succeeds without ambiguity on a fresh database.

Note: 5d575a161b5d's parent (e7f6a5b3c12d) is not a descendant of 52b19ee00eaf,
so this is a true branch-point merge.  The notification_templates table and
index created by 5d575a161b5d are intentionally NOT replicated here — they
already exist in that branch's timeline.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "merge_heads_notification_templates_662"
down_revision: str | Sequence[str] | None = ("52b19ee00eaf", "5d575a161b5d")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass  # Merge-only marker — no schema changes; all DDL is in sub-revisions.


def downgrade() -> None:
    pass  # Alembic downgrade rolls back both sub-revisions via their own downgrade() functions.
