"""add_workflow_nodes

Revision ID: 185055a0d4f0
Revises: 82ecf4a34e34
Create Date: 2026-05-21 18:59:47.314208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '185055a0d4f0'
down_revision: Union[str, None] = '82ecf4a34e34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('workflow_nodes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('workflow_id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('node_type', sa.String(length=50), nullable=False),
    sa.Column('definition_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('execution_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflow_nodes_tenant_id'), 'workflow_nodes', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_workflow_nodes_workflow_id'), 'workflow_nodes', ['workflow_id'], unique=False)
    op.create_index(op.f('ix_workflow_nodes_tenant_id_workflow_id'), 'workflow_nodes', ['tenant_id', 'workflow_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workflow_nodes_tenant_id_workflow_id'), table_name='workflow_nodes')
    op.drop_index(op.f('ix_workflow_nodes_workflow_id'), table_name='workflow_nodes')
    op.drop_index(op.f('ix_workflow_nodes_tenant_id'), table_name='workflow_nodes')
    op.drop_table('workflow_nodes')