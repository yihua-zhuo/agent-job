"""create routing_rules

Revision ID: 7b1a2c3d4e5f
Revises: 4001ca3d5d6f
Create Date: 2026-05-30 11:58:00.000000

CustomerService.create_customer calls LeadRoutingService.auto_assign_lead,
which selects from routing_rules. The model existed in the ORM with no
migration, so POST /customers 500'd with UndefinedTableError.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '7b1a2c3d4e5f'
down_revision: Union[str, None] = '4001ca3d5d6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'routing_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('conditions_json', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column('assignee_type', sa.String(length=50), nullable=False, server_default='round_robin'),
        sa.Column('assignee_id', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_routing_rules_tenant_id'), 'routing_rules', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_routing_rules_tenant_id'), table_name='routing_rules')
    op.drop_table('routing_rules')
