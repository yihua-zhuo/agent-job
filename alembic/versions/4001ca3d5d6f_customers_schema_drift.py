"""customers_schema_drift

Revision ID: 4001ca3d5d6f
Revises: 52b19ee00eaf
Create Date: 2026-05-30 11:34:57.309144

Add columns that exist on CustomerModel but were never migrated:
assigned_at, recycle_count, recycle_history.

The two non-nullable columns get server defaults so this applies cleanly
to populated tables. ORM-side `default=` covers new rows; the server default
just backfills existing ones.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '4001ca3d5d6f'
down_revision: Union[str, None] = '82ecf4a34e34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'customers',
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'customers',
        sa.Column('recycle_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'customers',
        sa.Column(
            'recycle_history',
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column('customers', 'recycle_history')
    op.drop_column('customers', 'recycle_count')
    op.drop_column('customers', 'assigned_at')
