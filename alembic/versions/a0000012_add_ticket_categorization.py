"""add_ticket_categorization

Revision ID: a0000012
Revises: 9d8e7f6a5b3c
Create Date: 2026-05-22 22:06:03.055715

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a0000012'
down_revision: Union[str, None] = '9d8e7f6a5b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ticket_categorizations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.Column('category_type', sa.String(length=50), nullable=False),
    sa.Column('priority', sa.String(length=50), nullable=True),
    sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=True),
    sa.Column('reasons', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('suggested_assignee_id', sa.Integer(), nullable=True),
    sa.Column('suggested_team', sa.String(length=100), nullable=True),
    sa.Column('human_override', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('categorized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticket_categorizations_tenant_id'), 'ticket_categorizations', ['tenant_id'], unique=False)
    op.create_index('ix_ticket_categorizations_tenant_ticket', 'ticket_categorizations', ['tenant_id', 'ticket_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ticket_categorizations_tenant_ticket', table_name='ticket_categorizations')
    op.drop_index(op.f('ix_ticket_categorizations_tenant_id'), table_name='ticket_categorizations')
    op.drop_table('ticket_categorizations')
