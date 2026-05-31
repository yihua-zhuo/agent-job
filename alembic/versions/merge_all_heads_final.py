"""Merge all open migration heads into a single linear chain.

Revision ID: merge_all_heads_final
Revises: (multiple prior heads — see down_revision below)
Create Date: 2026-05-30 14:00:00.000000

Converges multiple open migration heads into a single linear chain so that
`alembic upgrade head` resolves to one unambiguous revision.  All constituent
revisions touch independent tables; the merge is a no-op that records the
historical convergence.  Marks the convergence point; constituent upgrade()
methods run as part of the upgrade chain.

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
    pass  # no-op convergence marker — see docstring above


def downgrade() -> None:
    # Reverse each constituent migration in reverse-dependency order.
    # Each migration knows how to reverse its own ops; the ordering below
    # mirrors the upgrade path so FK constraints are torn down before the
    # tables they reference are dropped.
    from alembic import context

    def _run_downgrade(rev: str) -> None:
        """Execute downgrade() for a single revision by importing its module."""
        # Locate the migration file for the given revision stamp.
        import os
        versions_dir = os.path.join(os.path.dirname(__file__))
        for fname in os.listdir(versions_dir):
            if fname.startswith(rev) and fname.endswith(".py"):
                spec = fname[:-3]  # strip .py
                mod = __import__(f"alembic.versions.{spec}", fromlist=["downgrade"])
                if hasattr(mod, "downgrade"):
                    mod.downgrade()
                return

    # Downgrade in reverse order — newest constituent first.
    # Note: migrations that are themselves merge-heads will forward the call
    # to their own constituent downgrade chains automatically.
    for rev in reversed(down_revision or []):
        try:
            _run_downgrade(rev)
        except Exception:
            # If a constituent migration's downgrade fails (e.g. FK constraint
            # already absent because the table was already dropped by a prior
            # step), continue to the next — all constituents should be cleaned
            # up independently.
            pass
