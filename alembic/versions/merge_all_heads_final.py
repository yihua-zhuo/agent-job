"""merge all 11 remaining heads into single linear chain

Revision ID: merge_all_heads_final
Revises: 9aad50c58f54, a52e1317da90, add_agent_tasks_001, 63274a8b98b3c, afa7c3f333bd, c94d682d4b04, db63fcd03ab9, e1f2a3b4c5d6, e646948c549a, f18b406b982a, a940f167ad16
Create Date: 2026-05-30 14:00:00.000000

Converges all 12 open migration heads into a single linear chain so that
`alembic upgrade head` resolves to one unambiguous revision.  All 12
revisions touch independent tables; the merge is a no-op that records the
historical convergence.

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'merge_all_heads_final'
down_revision: str | Sequence[str] | None = (
    '9aad50c58f54',
    'a52e1317da90',
    'add_agent_tasks_001',
    '63274a8b98b3c',
    'afa7c3f333bd',
    'c94d682d4b04',
    'db63fcd03ab9',
    'e1f2a3b4c5d6',
    'e646948c549a',
    'f18b406b982a',
    'a940f167ad16',
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No-op convergence marker. All 12 constituent migrations' upgrade()
    # methods ran independently before this merge was created, so no
    # constraint or index is omitted from this file. This merge is
    # append-only and has no subsequent migrations depending on it.


def downgrade() -> None:
    # Downgrade path: merge was append-only; re-converge the 12 heads by
    # letting each constituent migration's own downgrade() run independently.
    # This migrates the DB back to the pre-merge multi-head state, not a
    # single linear revision, matching the intent of the original merge.
    pass
