"""add_code_reviews

Revision ID: a21c7fe41199
Revises: f932c1fe1f13
Create Date: 2026-05-22 23:08:37.369727

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'a21c7fe41199'
down_revision: str | None = 'f932c1fe1f13'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('code_reviews',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('language', sa.String(length=50), nullable=True),
    sa.Column('review_type', sa.String(length=50), nullable=True),
    sa.Column('code_snippet', sa.Text(), nullable=True),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_code_reviews_tenant', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_code_reviews_user', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_code_reviews_tenant_id', 'code_reviews', ['tenant_id'], unique=False)
    op.create_index('ix_code_reviews_tenant_user', 'code_reviews', ['tenant_id', 'user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_code_reviews_tenant_id', table_name='code_reviews')
    op.drop_index('ix_code_reviews_tenant_user', table_name='code_reviews')
    op.drop_table('code_reviews')
