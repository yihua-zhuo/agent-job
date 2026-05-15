"""add tenant slug and usage_limits

Revision ID: 9aad50c58f54
Revises: 9d8e7f6a5b3c
Create Date: 2026-05-15 21:04:06.652694

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9aad50c58f54'
down_revision: Union[str, None] = '9d8e7f6a5b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('slug', sa.String(length=100), server_default='', nullable=False))
    op.add_column('tenants', sa.Column('usage_limits', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    op.drop_column('tenants', 'usage_limits')
    op.drop_column('tenants', 'slug')