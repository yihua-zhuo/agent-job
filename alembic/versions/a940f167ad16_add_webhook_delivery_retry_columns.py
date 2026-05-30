"""add webhook delivery retry columns

Revision ID: a940f167ad16
Revises: fcf9ff098f62447a
Create Date: 2026-05-30 13:08:44.051704

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import column

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a940f167ad16'
down_revision: str | None = 'fcf9ff098f62447a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('webhook_deliveries', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('webhook_deliveries', sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('webhook_deliveries', sa.Column('error_message', sa.Text(), nullable=True))
    op.create_index(
        "ix_delivery_next_retry", "webhook_deliveries", ["next_retry_at"],
        postgresql_where=column("next_retry_at").isnot(None),
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_next_retry", table_name="webhook_deliveries")
    op.drop_column('webhook_deliveries', 'error_message')
    op.drop_column('webhook_deliveries', 'last_attempt_at')
    op.drop_column('webhook_deliveries', 'next_retry_at')
