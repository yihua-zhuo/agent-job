"""merge_heads

Revision ID: 6e3746e84cc8
Revises: c94d682d4b03, 9d8e7f6a5b3c
Create Date: 2026-05-22 20:56:40.197647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e3746e84cc8'
down_revision: Union[str, None] = ('c94d682d4b03', '9d8e7f6a5b3c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass