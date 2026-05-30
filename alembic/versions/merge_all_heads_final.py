"""merge all 11 remaining heads into single linear chain

Revision ID: merge_all_heads_final
Revises: 9aad50c58f54, a52e1317da90, add_agent_tasks_001, 63274a8b98b3c, afa7c3f333bd, c94d682d4b04, db63fcd03ab9, e1f2a3b4c5d6, e646948c549a, f18b406b982a, fcf9ff098f62447a
Create Date: 2026-05-30 14:00:00.000000

Converges all 11 open migration heads into a single linear chain so that
`alembic upgrade head` resolves to one unambiguous revision.  All11
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
    'fcf9ff098f62447a',
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
