"""add_engagement_events_table

Revision ID: add_engagement_events
Revises: e8ad92ca62b3
Create Date: 2026-06-06 10:00:00.000000

Create the engagement_events table used by the POST /events/engagement webhook
to record email_open and website_visit events. The webhook handler reads back
the row and uses it to trigger ScoreService.calculate_score for the customer.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_engagement_events"
down_revision: str | None = "e8ad92ca62b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_engagement_events_tenant_id"),
        "engagement_events",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engagement_events_customer_id"),
        "engagement_events",
        ["customer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_engagement_events_customer_id"), table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_tenant_id"), table_name="engagement_events")
    op.drop_table("engagement_events")
