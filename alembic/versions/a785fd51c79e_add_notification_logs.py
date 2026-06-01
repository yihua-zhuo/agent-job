"""add_notification_logs

Revision ID: a785fd51c79e
Revises: c94d682d4b04
Create Date: 2026-06-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a785fd51c79e"
down_revision: str | None = "c94d682d4b04"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notification_logs_tenant_id"), "notification_logs", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_notification_logs_notification_id"), "notification_logs", ["notification_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_notification_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_tenant_id"), table_name="notification_logs")
    op.drop_table("notification_logs")
