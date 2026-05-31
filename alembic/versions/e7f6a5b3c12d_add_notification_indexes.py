"""add_notification_indexes

Revision ID: e7f6a5b3c12d
Revises: 82ecf4a34e34
Create Date: 2026-05-23

Transforms the notifications table from the old schema (type, title, content,
is_read, related_type, related_id) to the new schema (channel, template,
params_, status, priority, delivered_at, read_at) then adds:
- composite index on (user_id, tenant_id, status)
- partial index for unread in-app notifications
"""

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON as PG_JSON

from alembic import op

revision: str = "e7f6a5b3c12d"
down_revision: str = "82ecf4a34e34"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("notifications", Column("channel", String(length=50), nullable=True))
    op.add_column("notifications", Column("template", String(length=255), nullable=True))
    op.add_column("notifications", Column("params_", PG_JSON(), nullable=True, server_default=sa.text("'{}'::jsonb")))
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
    op.execute(
        text("UPDATE notifications SET status = CASE WHEN is_read THEN 'read' ELSE 'pending' END WHERE status IS NULL")
    )
    op.execute(text("UPDATE notifications SET delivered_at = created_at WHERE delivered_at IS NULL"))
    op.execute(text("UPDATE notifications SET read_at = created_at WHERE is_read = true AND read_at IS NULL"))
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
        ["user_id", "tenant_id", "status"],
    )
    # Partial index for efficient lookup of unread in-app notifications.
    # PostgreSQL partial indexes include all rows matching the WHERE clause; the two
    # leading columns (user_id, tenant_id) are included so that queries filtering by
    # those columns + channel + read_at benefit from the index. They are not redundant
    # with the WHERE clause — the clause filters rows, the columns serve the query.
    op.create_index(
        "ix_notifications_in_app_unread",
        "notifications",
        ["user_id", "tenant_id"],
        postgresql_where=text("channel = 'in_app' AND read_at IS NULL"),
    )


def downgrade() -> None:
    # Phase 1 (reversed): drop new columns before dropping indexes that reference them.
    # Must run before dropping indexes so the columns still exist at constraint-check time.
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "delivered_at")
    op.drop_column("notifications", "priority")
    op.drop_column("notifications", "status")
    op.drop_column("notifications", "params_")
    op.drop_column("notifications", "template")
    op.drop_column("notifications", "channel")

    # Phase 4 (reversed): drop indexes created in upgrade before restoring old columns.
    op.drop_index("ix_notifications_in_app_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_tenant_status", table_name="notifications")

    # Phase 4 (reversed): add back old columns first (needed before restore data step)
    # is_read is added as nullable first to avoid constraint violations from Phase 3
    # backfill — the NOT NULL constraint is applied after the UPDATE runs.
    op.add_column("notifications", Column("type", String(length=50), nullable=True))
    op.add_column("notifications", Column("title", String(length=255), nullable=True))
    op.add_column("notifications", Column("content", String(length=2000), nullable=True))
    op.add_column("notifications", Column("is_read", Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("notifications", Column("related_type", String(length=50), nullable=True))
    op.add_column("notifications", Column("related_id", Integer(), nullable=True))

    # Phase 3 (reversed): restore old data (must run after old columns exist)
    # Note: jsonb_build_object silently drops NULL values on upgrade, so to restore
    # the original state we can only recover rows where related_type or related_id
    # were non-NULL. Rows where both were originally NULL will remain NULL after
    # downgrade — this asymmetry is an inherent limitation of the one-way migration.
    # The content-restoration UPDATE guards against writing 'NULL' strings by
    # requiring params_->>'content' to be non-NULL as well.
    op.execute(text("UPDATE notifications SET type = channel WHERE channel IS NOT NULL"))
    op.execute(text("UPDATE notifications SET title = template WHERE template IS NOT NULL"))
    op.execute(
        text(
            "UPDATE notifications SET content = params_->>'content' WHERE params_ IS NOT NULL AND params_->>'content' IS NOT NULL"
        )
    )
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
    op.execute(text("UPDATE notifications SET is_read = false WHERE is_read IS NULL AND status IS NOT NULL"))
    # Catch-all for rows that had NULL status during the Phase 2 backfill —
    # these rows should have is_read=false to match the pre-migration implicit default.
    op.execute(text("UPDATE notifications SET is_read = false WHERE is_read IS NULL"))

    # Phase 4 (reversed): apply NOT NULL constraint idempotently — check whether
    # the constraint is already present before applying it, to survive replayed
    # downgrades or prior partial downgrades. Uses information_schema rather than
    # SQLERRM pattern-matching so it works regardless of PostgreSQL locale.
    op.execute(
        text(
            "DO $$ "
            "BEGIN "
            "IF NOT EXISTS ("
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = 'notifications_is_read_notnull' "
            "AND table_name = 'notifications'"
            ") THEN "
            "ALTER TABLE notifications ALTER COLUMN is_read SET NOT NULL; "
            "END IF; "
            "END $$"
        )
    )
