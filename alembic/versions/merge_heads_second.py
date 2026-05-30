"""merge heads after customers_schema_drift

Revision ID: merge_heads_second
Revises: db67d696b6ab, 7b1a2c3d4e5f
Create Date: 2026-05-30 12:00:00.000000

4001ca3d5d6f_customers_schema_drift was added after 52b19ee00eaf_merge_heads,
creating a second head alongside 7b1a2c3d4e5f. This revision merges both heads.

After subsequent schema work (routing_rules, identity subsystem) the true
migration head is now db67d696b6ab.  This revision is a no-op that records the
historical merge for completeness.  downgrade() raises NotImplementedError
since reversing a merge revision is not supported and the underlying schema
changes (from 4001ca3d5d6f_customers_schema_drift) are now part of the
linearised migration chain under db67d696b6ab.

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'merge_heads_second'
down_revision: str | Sequence[str] | None = ('db67d696b6ab', '7b1a2c3d4e5f')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
