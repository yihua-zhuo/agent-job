"""merge three heads into single linear chain

Revision ID: merge_heads_third
Revises: 185055a0d4f0, addcp001, db67d696b6ab
Create Date: 2026-05-30 13:00:00.000000

Merges the three divergent migration heads into a single linear chain.
All three heads apply cleanly to a fresh database — they touch completely
independent tables.  The merge is a no-op that records the historical
convergence for completeness.

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'merge_heads_third'
down_revision: str | Sequence[str] | None = ('185055a0d4f0', 'addcp001', 'db67d696b6ab')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Pure merge-head marker — no schema changes from any of the three parent
    # migrations (185055a0d4f0, addcp001, db67d696b6ab).  All three touch
    # independent tables and apply cleanly in any order.  Rollback is a no-op
    # because the parents already contain the full schema.
    pass


def downgrade() -> None:
    # No-op: the three parent migrations are self-contained and must be
    # downgraded individually if needed.
    pass