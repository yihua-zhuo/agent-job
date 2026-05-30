"""merge heads

Revision ID: 52b19ee00eaf
Revises: a52e1317da90, 63274a8b98b3c, e646948c549a, add_agent_tasks_001, afa7c3f333bd, c94d682d4b04, db63fcd03ab9, e1f2a3b4c5d6, f18b406b982a
Create Date: 2026-05-30 11:03:03.754025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52b19ee00eaf'
down_revision: Union[str, None] = ('a52e1317da90', '63274a8b98b3c', 'e646948c549a', 'add_agent_tasks_001', 'afa7c3f333bd', 'c94d682d4b04', 'db63fcd03ab9', 'e1f2a3b4c5d6', 'f18b406b982a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass