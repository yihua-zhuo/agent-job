"""merge_heads_auth_ai

Revision ID: 8b65fe079d37
Revises: 9d8e7f6a5b3c, c94d682d4b03
Create Date: 2026-05-20 23:50:47.139682

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b65fe079d37'
down_revision: Union[str, None] = ('9d8e7f6a5b3c', 'c94d682d4b03')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass