"""merge heads after customers_schema_drift

Revision ID: merge_heads_second
Revises: 4001ca3d5d6f
Create Date: 2026-05-30 12:00:00.000000

4001ca3d5d6f_customers_schema_drift was added after 52b19ee00eaf_merge_heads,
creating a second head. This merge unifies the two heads.

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'merge_heads_second'
down_revision: str | Sequence[str] | None = '4001ca3d5d6f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No schema operations required.
    # Parent revisions:
    #   52b19ee00eaf (merge_heads):    empty pass (both parents were stubs)
    #   4001ca3d5d6f (customers_schema_drift): adds 3 columns to customers
    # 4001ca3d5d6f already depends on 52b19ee00eaf, so this merge revision
    # simply brings the two branch heads under a single revision node so that
    # `alembic upgrade head` resolves unambiguously.
    pass


def downgrade() -> None:
    # Reversal is handled by downgrading to 4001ca3d5d6f, which undoes the
    # customers_schema_drift changes (drops the 3 added columns) and is itself
    # reachable from 52b19ee00eaf via the parent chain.
    pass
