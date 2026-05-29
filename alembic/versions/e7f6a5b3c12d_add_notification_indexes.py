"""add_notification_indexes

Revision ID: e7f6a5b3c12d
Revises: 9d8e7f6a5b3c
Create Date: 2026-05-23

Transforms the notifications table from the old schema (type, title, content,
is_read, related_type, related_id) to the new schema (channel, template,
params_, status, priority, delivered_at, read_at) then adds:
- composite index on (user_id, tenant_id, status)
- partial index for unread in-app notifications
"""

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "e7f6a5b3c12d"
down_revision = "9d8e7f6a5b3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1: add new columns (nullable, default null)
    op.add_column("notifications", sa.Column("channel", sa.String(length=50), nullable=True))
    op.add_column("notifications", sa.Column("template", sa.String(length=255), nullable=True))
    op.add_column("notifications", sa.Column("params_", sa.JSON, nullable=True))
    op.add_column("notifications", sa.Column("status", sa.String(length=50), nullable=True))
    op.add_column("notifications", sa.Column("priority", sa.String(length=20), nullable=True))
    op.add_column("notifications", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))

    # Phase 2: backfill new columns from old ones
    # Note: jsonb_build_object drops null values, so a row where only 'content' was set
    # will produce {"content": "..."} with no 'related_type'/'related_id' keys (rather than
    # {"content": "...", "related_type": null, "related_id": null}). This is a minor
    # data-shape precision trade-off for the one-way migration.
    op.execute(text("UPDATE notifications SET channel = type WHERE type IS NOT NULL"))
    op.execute(text("UPDATE notifications SET template = title WHERE title IS NOT NULL"))
    op.execute(
        text(
            "UPDATE notifications SET params_ = jsonb_build_object("
            "'content', content,"
            "'related_type', related_type,"
            "'related_id', related_id"
            ") WHERE content IS NOT NULL OR related_type IS NOT NULL OR related_id IS NOT NULL"
        )
    )
    op.execute(text("UPDATE notifications SET status = CASE WHEN is_read THEN 'read' ELSE 'pending' END"))
    op.execute(text("UPDATE notifications SET read_at = created_at WHERE is_read = true"))

    # Phase 3: drop old columns
    op.drop_column("notifications", "related_id")
    op.drop_column("notifications", "related_type")
    op.drop_column("notifications", "is_read")
    op.drop_column("notifications", "content")
    op.drop_column("notifications", "title")
    op.drop_column("notifications", "type")

    # Phase 4: add indexes
    op.create_index(
        "ix_notifications_user_tenant_status",
        "notifications",
        ["user_id", "tenant_id", "status"],
        unique=False,
    )
    # Partial index for efficient lookup of unread in-app notifications
    op.create_index(
        "ix_notifications_in_app_unread",
        "notifications",
        ["user_id", "tenant_id"],
        unique=False,
        postgresql_where=sa.and_(
            sa.column("channel") == "in_app",
            sa.column("read_at").is_(None),
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_in_app_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_tenant_status", table_name="notifications")

    # Phase 4 (reversed): add back old columns first (needed before restore data step)
    # is_read is added as nullable first to avoid constraint violations from Phase 3
    # backfill — the NOT NULL constraint is applied after the UPDATE runs.
    op.add_column("notifications", sa.Column("type", sa.String(length=50), nullable=True))
    op.add_column("notifications", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("notifications", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("notifications", sa.Column("is_read", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("notifications", sa.Column("related_type", sa.String(length=50), nullable=True))
    op.add_column("notifications", sa.Column("related_id", sa.Integer(), nullable=True))

    # Phase 3 (reversed): restore old data (must run after old columns exist)
    op.execute(text("UPDATE notifications SET type = channel WHERE channel IS NOT NULL"))
    op.execute(text("UPDATE notifications SET title = template WHERE template IS NOT NULL"))
    op.execute(text("UPDATE notifications SET content = params_->>'content' WHERE params_ IS NOT NULL"))
    op.execute(
        text(
            "UPDATE notifications SET related_type = params_->>'related_type' "
            "WHERE params_ IS NOT NULL AND params_->>'related_type' IS NOT NULL"
        )
    )
    op.execute(
        text(
            "UPDATE notifications SET related_id = (params_->>'related_id')::integer "
            "WHERE params_ IS NOT NULL AND params_->>'related_id' IS NOT NULL"
        )
    )
    op.execute(text("UPDATE notifications SET is_read = (status = 'read') WHERE status IS NOT NULL"))

    # Apply NOT NULL constraint after backfill — rows with NULL status become False
    op.alter_column("is_read", nullable=False)

    # Phase 2 (reversed): drop new columns
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "delivered_at")
    op.drop_column("notifications", "priority")
    op.drop_column("notifications", "status")
    op.drop_column("notifications", "params_")
    op.drop_column("notifications", "template")
    op.drop_column("notifications", "channel")
