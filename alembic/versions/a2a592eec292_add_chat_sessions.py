"""add_chat_sessions

Revision ID: a2a592eec292
Revises: c94d682d4b03
Create Date: 2026-05-23

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a2a592eec292'
down_revision: str | None = 'c94d682d4b03'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_chat_sessions_tenant_id'), 'chat_sessions', ['tenant_id'], unique=False
    )
    op.create_index(
        'ix_chat_sessions_tenant_user',
        'chat_sessions',
        ['tenant_id', 'user_id'],
        unique=False,
    )
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(length=100), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['session_id'], ['chat_sessions.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_chat_messages_session_id'),
        'chat_messages',
        ['session_id'],
        unique=False,
    )
    op.create_index(
        'ix_chat_messages_tenant_session',
        'chat_messages',
        ['tenant_id', 'session_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_chat_messages_tenant_session', table_name='chat_messages'
    )
    op.drop_index(
        op.f('ix_chat_messages_session_id'), table_name='chat_messages'
    )
    op.drop_table('chat_messages')
    op.drop_index(
        'ix_chat_sessions_tenant_user', table_name='chat_sessions'
    )
    op.drop_index(
        op.f('ix_chat_sessions_tenant_id'), table_name='chat_sessions'
    )
    op.drop_table('chat_sessions')
