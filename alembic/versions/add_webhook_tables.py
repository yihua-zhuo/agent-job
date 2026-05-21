"""add webhook tables

Revision ID: add_webhook_tables
Revises: 9d8e7f6a5b3c
Create Date: 2026-05-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'add_webhook_tables'
down_revision: str | None = '9d8e7f6a5b3c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'webhooks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(length=2000), nullable=False),
        sa.Column('events', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_webhooks_tenant_id'), 'webhooks', ['tenant_id'], unique=False)
    op.create_index('ix_webhooks_tenant_active', 'webhooks', ['tenant_id', 'is_active'], unique=False)

    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('webhook_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('response', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_webhook_deliveries_tenant_id'), 'webhook_deliveries', ['tenant_id'], unique=False)
    op.create_index('ix_webhook_deliveries_webhook_id', 'webhook_deliveries', ['webhook_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_webhook_deliveries_webhook_id', table_name='webhook_deliveries')
    op.drop_index(op.f('ix_webhook_deliveries_tenant_id'), table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
    op.drop_index('ix_webhooks_tenant_active', table_name='webhooks')
    op.drop_index(op.f('ix_webhooks_tenant_id'), table_name='webhooks')
    op.drop_table('webhooks')

