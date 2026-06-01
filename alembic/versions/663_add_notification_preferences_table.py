"""add_notification_preferences_table

Revision ID: 663_add_notification_preferences_table
Revises: merge_nt_662
Create Date: 2026-06-01

Creates the notification_preferences table for storing per-user,
per-channel notification opt-in/out preferences.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "663_notif_prefs"
down_revision: str | Sequence[str] | None = "merge_nt_662"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_notification_preferences_tenant_id"), "notification_preferences", ["tenant_id"])
    op.create_index(op.f("ix_notification_preferences_user_id"), "notification_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_preferences_user_id"), table_name="notification_preferences")
    op.drop_index(op.f("ix_notification_preferences_tenant_id"), table_name="notification_preferences")
    op.drop_table("notification_preferences")
