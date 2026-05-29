"""add_report_definitions

Revision ID: c94d682d4b04
Revises: c94d682d4b03
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c94d682d4b04'
down_revision: Union[str, None] = 'c94d682d4b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'report_definitions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('report_type', sa.String(length=100), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('owner_tenant_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('is_favorite', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_report_definitions_tenant_id'), 'report_definitions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_report_definitions_report_type'), 'report_definitions', ['report_type'], unique=False)
    op.create_index(op.f('ix_report_definitions_owner_tenant_id'), 'report_definitions', ['owner_tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_report_definitions_owner_tenant_id'), table_name='report_definitions')
    op.drop_index(op.f('ix_report_definitions_report_type'), table_name='report_definitions')
    op.drop_index(op.f('ix_report_definitions_tenant_id'), table_name='report_definitions')
    op.drop_table('report_definitions')
