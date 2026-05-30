"""merge heads after customers_schema_drift

Revision ID: merge_heads_second
Revises: 52b19ee00eaf, 4001ca3d5d6f
Create Date: 2026-05-30 12:00:00.000000

4001ca3d5d6f_customers_schema_drift was added after52b19ee00eaf_merge_heads,
creating a second head. This merge unifies the two heads.

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'merge_heads_second'
down_revision: Union[str, None] = ('52b19ee00eaf', '4001ca3d5d6f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
