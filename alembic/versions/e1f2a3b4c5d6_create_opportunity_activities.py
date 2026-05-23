"""create_opportunity_activities

Revision ID: e1f2a3b4c5d6
Revises: c94d682d4b03
Create Date: 2026-05-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "c94d682d4b03"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opportunity_activities_tenant_id"), "opportunity_activities", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_opportunity_activities_opportunity_id"), "opportunity_activities", ["opportunity_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_opportunity_activities_opportunity_id"), table_name="opportunity_activities")
    op.drop_index(op.f("ix_opportunity_activities_tenant_id"), table_name="opportunity_activities")
    op.drop_table("opportunity_activities")
