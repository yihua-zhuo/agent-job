"""add_channel_to_notifications

Revision ID: 06456391eff1
Revises: c297b2158a69
Create Date: 2026-05-21 20:50:27.067114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '06456391eff1'
down_revision: Union[str, None] = 'c297b2158a69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("channel", sa.String(length=20), nullable=False, server_default=sa.text("'email'")),
    )


def downgrade() -> None:
    op.drop_column("notifications", "channel")