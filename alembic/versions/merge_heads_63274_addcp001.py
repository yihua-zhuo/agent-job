"""merge webhook and churn heads

Revision ID: merge_heads_63274_addcp001
Revises: 52b19ee00eaf, 63274a8b98b3c, addcp001
Create Date: 2026-05-30 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_heads_63274_addcp001'
down_revision: Union[str, None] = ('52b19ee00eaf', '63274a8b98b3c', 'addcp001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
