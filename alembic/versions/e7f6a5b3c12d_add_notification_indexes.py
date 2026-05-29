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

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, and_, column, text
from sqlalchemy.dialects.postgresql import JSON as PgJSON

from alembic import op

revision = "e7f6a5b3c12d"
down_revision = "9d8e7f6a5b3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", Column("channel", String(length=50), nullable=True))
    op.add_column("notifications", Column("template", String(length=255), nullable=True))
    op.add_column("notifications", Column("params_", JSON().with_variant(PgJSON(), "postgresql"), nullable=True))
    op.add_column("notifications", Column("status", String(length=50), nullable=True))
    op.add_column("notifications", Column("priority", String(length=20), nullable=True))
    op.add_column("notifications", Column("delivered_at", DateTime(timezone=True), nullable=True))
    op.add_column("notifications", Column("read_at", DateTime(timezone=True), nullable=True))

    # Phase 2: backfill new columns from old ones
    # Note: jsonb_build_object drops null values, so a row where only 'content' was set
    # will produce {"content": "..."} with no 'related_type'/'related_id' keys (rather than
    # {"content": "...", "related_type": null, "related_id": null}). This is a minor
    # data-shape precision trade-off for the one-way migration.
    op.execute(text("UPDATE notifications SET channel = type WHERE type IS NOT NULL AND channel IS NULL"))
    op.execute(text("UPDATE notifications SET template = title WHERE title IS NOT NULL AND template IS NULL"))
    op.execute(
        text(
            "UPDATE notifications SET params_ = jsonb_build_object("
            "'content', content,"
            "'related_type', related_type,"
            "'related_id', related_id"
            ") WHERE (content IS NOT NULL OR related_type IS NOT NULL OR related_id IS NOT NULL) AND params_ IS NULL"
        )
    )
    op.execute(text("UPDATE notifications SET status = CASE WHEN is_read THEN 'read' ELSE 'pending' END WHERE status IS NULL"))
    op.execute(text("UPDATE notifications SET read_at = created_at WHERE is_read = true AND read_at IS NULL"))
    op.execute(text("UPDATE notifications SET delivered_at = created_at WHERE delivered_at IS NULL"))
    op.execute(text("UPDATE notifications SET priority = 'normal' WHERE priority IS NULL"))

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
        column_names=["user_id", "tenant_id", "status"],
    )
    # Partial index for efficient lookup of unread in-app notifications
    op.create_index(
        "ix_notifications_in_app_unread",
        "notifications",
        ["user_id", "tenant_id"],
        postgresql_where=and_(
            column("channel").in_(["in_app"]),
            column("read_at").is_(None),
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_in_app_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_tenant_status", table_name="notifications")

    # Phase 4 (reversed): add back old columns first (needed before restore data step)
    # is_read is added as nullable first to avoid constraint violations from Phase 3
    # backfill — the NOT NULL constraint is applied after the UPDATE runs.
    op.add_column("notifications", Column("type", String(length=50), nullable=True))
    op.add_column("notifications", Column("title", String(length=255), nullable=True))
    op.add_column("notifications", Column("content", Text(), nullable=True))
    op.add_column("notifications", Column("is_read", Boolean(), nullable=True, server_default=text("false")))
    op.add_column("notifications", Column("related_type", String(length=50), nullable=True))
    op.add_column("notifications", Column("related_id", Integer(), nullable=True))

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
            "UPDATE notifications SET related_id = (params_->>'related_id')::bigint "
            "WHERE params_ IS NOT NULL AND params_->>'related_id' IS NOT NULL"
        )
    )
    op.execute(text("UPDATE notifications SET is_read = (status = 'read') WHERE status IS NOT NULL"))
    op.execute(text("UPDATE notifications SET is_read = false WHERE is_read IS NULL"))

    # Apply NOT NULL constraint after backfill — rows with NULL status become False
    op.alter_column("notifications", "is_read", nullable=False)

    # Phase 2 (reversed): drop new columns — done last so the downgrade remains
    # individually reversible without relying on ordering of other migrations
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "delivered_at")
    op.drop_column("notifications", "priority")
    op.drop_column("notifications", "status")
    op.drop_column("notifications", "params_")
    op.drop_column("notifications", "template")
    op.drop_column("notifications", "channel")
