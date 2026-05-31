"""add_notification_templates

Revision ID: 5d575a161b5d
Revises: e7f6a5b3c12d
Create Date: 2026-05-31

Creates the notification_templates table for the notification system
(parent issue #646). Stores reusable notification content by channel.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "5d575a161b5d"
down_revision: str = "e7f6a5b3c12d"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_notification_templates_tenant_id"),
        "notification_templates",
        ["tenant_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notification_templates_tenant_id"), table_name="notification_templates"
    )
    op.drop_table("notification_templates")
