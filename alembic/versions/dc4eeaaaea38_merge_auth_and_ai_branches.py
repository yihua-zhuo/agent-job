"""merge_auth_and_ai_branches

Revision ID: dc4eeaaaea38
Revises: 9d8e7f6a5b3c, c94d682d4b03
Create Date: 2026-05-23 15:00:38.837216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc4eeaaaea38'
down_revision: Union[str, None] = ('9d8e7f6a5b3c', 'c94d682d4b03')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass