"""create_notification_analytics

Revision ID: 0596add_notification_analytics_tracking
Revises: db67d696b6ab
Create Date: 2026-05-31 18:00:00.000000

Adds the notification_analytics table to track open/click events
on a per-notification, per-tenant basis.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0596add_notification_analytics_tracking"
down_revision: str | Sequence[str] | None = "db67d696b6ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_analytics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("notification_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False, server_default="email"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_notification_analytics_notification_tenant"), "notification_analytics", ["notification_id", "tenant_id"], unique=False)
    op.create_index(op.f("ix_notification_analytics_tenant_id"), "notification_analytics", ["tenant_id"])
    # notification_id FK — intentionally guarded with IF NOT EXISTS for existing-row safety;
    # notifications are hard-deleted via API so analytics may outlast their parent row.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE notification_analytics ADD CONSTRAINT fk_notification_analytics_notification_id "
            "FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE; "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )
    # tenant_id FK — catches DBs that arrived via a path that skipped this migration.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE notification_analytics ADD CONSTRAINT fk_notification_analytics_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE notification_analytics DROP CONSTRAINT IF EXISTS fk_notification_analytics_notification_id; "
            "EXCEPTION WHEN undefined_object THEN NULL; "
            "END $$"
        )
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE notification_analytics DROP CONSTRAINT IF EXISTS fk_notification_analytics_tenant_id; "
            "EXCEPTION WHEN undefined_object THEN NULL; "
            "END $$"
        )
    )
    op.drop_index(op.f("ix_notification_analytics_notification_tenant"), table_name="notification_analytics")
    op.drop_index(op.f("ix_notification_analytics_tenant_id"), table_name="notification_analytics")
    op.drop_table("notification_analytics")