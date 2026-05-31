"""add_notification_templates

Revision ID: 5d575a161b5d
Revises: e7f6a5b3c12d
Create Date: 2026-05-31

Creates the notification_templates table for the notification system
(parent issue #646). Stores reusable notification content by channel.
Supports channels: email, sms, push, in_app.  A CHECK constraint enforces
the channel allow-list at the DB layer.  NOT NULL + server-default on
created_at ensures every row has a timestamp even if the client omits it.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "5d575a161b5d"
down_revision: str = "e7f6a5b3c12d"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        # Channel is intentionally restricted to known values; enforcement is
        # shared between the ORM (via service layer) and this constraint.
        sa.CheckConstraint(
            column("channel").in_(["email", "sms", "push", "in_app"]),
            name="ck_notification_templates_channel",
        ),
    )
    op.create_index(
        op.f("ix_notification_templates_tenant_id"),
        "notification_templates",
        ["tenant_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    # Best-effort FK constraint removal.  PostgreSQL may assign the FK a
    # auto-generated name that differs from this hardcoded value; IF EXISTS
    # prevents a hard failure in that case.  The index and table drops are
    # idempotent and safe regardless of whether the constraint was found.
    op.execute(
        sa.text(
            "ALTER TABLE notification_templates DROP CONSTRAINT IF EXISTS notification_templates_tenant_id_fkey"
        )
    )
    op.drop_index(
        op.f("ix_notification_templates_tenant_id"),
        table_name="notification_templates",
        if_exists=True,
    )
    op.drop_table("notification_templates", if_exists=True)
