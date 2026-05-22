"""add_lead_score_columns

Revision ID: e8ad92ca62b3
Revises: eea413253aa1
Create Date: 2026-05-22 17:50:36.122022

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e8ad92ca62b3'
down_revision: str | None = 'eea413253aa1'
branch_labels: list[str] | None = None
depends_on: list[str] | None = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('score', sa.Integer(), nullable=True))
    op.add_column('customers', sa.Column('tier', sa.String(length=50), nullable=True))
    op.add_column('customers', sa.Column('score_factors', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('customers', sa.Column('top_factors', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('customers', sa.Column('recommendations', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'recommendations')
    op.drop_column('customers', 'top_factors')
    op.drop_column('customers', 'score_factors')
    op.drop_column('customers', 'tier')
    op.drop_column('customers', 'score')
