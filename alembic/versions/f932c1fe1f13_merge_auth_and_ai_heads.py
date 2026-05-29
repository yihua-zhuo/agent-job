"""merge_auth_and_ai_heads

Revision ID: f932c1fe1f13
Revises: 9d8e7f6a5b3c, c94d682d4b03
Create Date: 2026-05-22 23:08:24.069716

This revision merges two divergent migration heads (9d8e7f6a5b3c and c94d682d4b03)
into a single linear chain. No schema operations are required — the upgrade() and
downgrade() are both pass because the merge is purely a revision-graph correction.
The linear down_revision chain is 3ea69d66514e (the shared ancestor of both branch
roots). depends_on lists only the two branch root revisions (9d8e7f6a5b3c and
c94d682d4b03), not their common ancestor.

Run ``alembic history --verbose`` after this migration to confirm no divergent heads remain.
"""

from collections.abc import Sequence

revision: str = 'f932c1fe1f13'
down_revision: str | None = '3ea69d66514e'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = ('9d8e7f6a5b3c', 'c94d682d4b03')


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
