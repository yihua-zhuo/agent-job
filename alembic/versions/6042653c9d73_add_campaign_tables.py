"""add_campaign_tables

Revision ID: 6042653c9d73
Revises: ad83ab21d36d
Create Date: 2026-05-20 20:17:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6042653c9d73'
down_revision: Union[str, None] = 'ad83ab21d36d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'campaign_triggers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_campaign_triggers_tenant_id'), 'campaign_triggers', ['tenant_id'], unique=False)
    op.create_index('ix_campaign_triggers_tenant_campaign', 'campaign_triggers', ['tenant_id', 'campaign_id'], unique=False)

    op.create_index('ix_campaign_events_tenant_campaign', 'campaign_events', ['tenant_id', 'campaign_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_campaign_events_tenant_campaign', table_name='campaign_events')
    op.drop_index('ix_campaign_triggers_tenant_campaign', table_name='campaign_triggers')
    op.drop_index(op.f('ix_campaign_triggers_tenant_id'), table_name='campaign_triggers')
    op.drop_table('campaign_triggers')