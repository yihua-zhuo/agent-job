"""create_customer_enrichments

Revision ID: f18b406b982a
Revises: c94d682d4b03
Create Date: 2026-05-21 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f18b406b982a'
down_revision: str | None = 'c94d682d4b03'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'customer_enrichments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('raw_data_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('enriched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_refresh_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sqlite_autoincrement=True,
    )
    op.create_index(op.f('ix_customer_enrichments_customer_id'), 'customer_enrichments', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customer_enrichments_next_refresh_at'), 'customer_enrichments', ['next_refresh_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_customer_enrichments_next_refresh_at'), table_name='customer_enrichments')
    op.drop_index(op.f('ix_customer_enrichments_customer_id'), table_name='customer_enrichments')
    op.drop_table('customer_enrichments')
