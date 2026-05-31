"""add import export jobs

Revision ID: a52e1317da90
Revises: 9d8e7f6a5b3c
Create Date: 2026-05-23T17:01:58.306241844

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a52e1317da90'
down_revision: str | None = '9d8e7f6a5b3c'
branch_labels: Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # import_jobs
    op.create_table(
        'import_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False, index=True),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('total_rows', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('processed_rows', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('error_rows', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # export_jobs
    op.create_table(
        'export_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False, index=True),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('fields', JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('filters', JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('export_jobs')
    op.drop_table('import_jobs')
