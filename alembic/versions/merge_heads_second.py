"""merge heads after customers_schema_drift

Revision ID: merge_heads_second
Revises: db67d696b6ab
Create Date: 2026-05-30 12:00:00.000000

4001ca3d5d6f_customers_schema_drift was added after 52b19ee00eaf_merge_heads,
creating a second head. This merge unifies the two heads.

After subsequent schema work (routing_rules, identity subsystem) the true
migration head is now db67d696b6ab.  This revision is a no-op that records the
historical merge for completeness.  downgrade() is also a no-op since the
underlying schema changes (from 4001ca3d5d6f_customers_schema_drift) are now
embedded in the linearised migration chain and cannot be individually reversed.

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'merge_heads_second'
down_revision: str | Sequence[str] | None = 'db67d696b6ab'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise NotImplementedError("Reversing this merge revision is not supported — "
                              "the customers_schema_drift changes are now part "
                              "of the linearised migration chain under db67d696b6ab.")
