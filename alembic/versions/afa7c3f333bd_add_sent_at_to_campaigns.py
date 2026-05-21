"""add_sent_at_to_campaigns

Revision ID: afa7c3f333bd
Revises: c94d682d4b03
Create Date: 2026-05-21 22:17:33.550648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'afa7c3f333bd'
down_revision: Union[str, None] = 'c94d682d4b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaigns', sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('campaigns', 'sent_at')