"""add_code_reviews

Revision ID: a21c7fe41199
Revises: f932c1fe1f13
Create Date: 2026-05-22 23:08:37.369727

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a21c7fe41199'
down_revision: Union[str, None] = 'f932c1fe1f13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_code_reviews_tenant_user', 'code_reviews', ['tenant_id', 'user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_code_reviews_tenant_user', table_name='code_reviews')
    op.drop_table('code_reviews')
