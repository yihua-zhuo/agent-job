"""merge_auth_and_ai_heads

Revision ID: f932c1fe1f13
Revises: 9d8e7f6a5b3c, c94d682d4b03
Create Date: 2026-05-22 23:08:24.069716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f932c1fe1f13'
down_revision: Union[str, None] = ('9d8e7f6a5b3c', 'c94d682d4b03')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass