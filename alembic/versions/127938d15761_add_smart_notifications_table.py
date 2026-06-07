"""add_smart_notifications_table

Revision ID: 127938d15761
Revises: 9d8e7f6a5b3c
Create Date: 2026-05-22 19:29:33.787889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '127938d15761'
down_revision: Union[str, None] = '9d8e7f6a5b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('smart_notifications',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('summarized_content', sa.String(length=1024), nullable=False),
    sa.Column('priority', sa.Enum('urgent', 'normal', 'low', name='smart_notification_priority'), nullable=False),
    sa.Column('channel', sa.Enum('email', 'sms', 'push', 'in_app', name='smart_notification_channel'), nullable=False),
    sa.Column('timing', sa.Enum('immediate', 'batch', name='smart_notification_timing'), nullable=False),
    sa.Column('recipient_filter', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_smart_notifications_tenant_id'), 'smart_notifications', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_smart_notifications_tenant_id'), table_name='smart_notifications')
    op.drop_table('smart_notifications')