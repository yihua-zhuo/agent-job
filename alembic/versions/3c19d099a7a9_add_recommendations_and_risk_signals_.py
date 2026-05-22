"""add_recommendations_and_risk_signals_tables

Revision ID: 3c19d099a7a9
Revises: 6e3746e84cc8
Create Date: 2026-05-22 20:56:51.841713

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c19d099a7a9"
down_revision: str | None = "6e3746e84cc8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- recommendations table ---
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("next_action", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("similar_deals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recommendations_tenant_id"), "recommendations", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_recommendations_opportunity_id"), "recommendations", ["opportunity_id"], unique=False)
    op.create_index(
        "ix_recommendations_tenant_opportunity", "recommendations", ["tenant_id", "opportunity_id"], unique=True
    )
    op.execute(
        "ALTER TABLE recommendations ADD CONSTRAINT chk_recommendations_unique "
        "UNIQUE (tenant_id, opportunity_id)"
    )
    op.execute(
        "ALTER TABLE recommendations ADD CONSTRAINT chk_next_action "
        "CHECK (next_action IN ('call','email','meeting','demo','proposal'))"
    )
    op.execute(
        "ALTER TABLE recommendations ADD CONSTRAINT chk_confidence CHECK (confidence >= 0.0 AND confidence <= 1.0)"
    )

    # --- risk_signals table ---
    op.create_table(
        "risk_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("risk_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_risk_signals_tenant_id"), "risk_signals", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_risk_signals_opportunity_id"), "risk_signals", ["opportunity_id"], unique=False)
    op.create_index("ix_risk_signals_tenant_opportunity", "risk_signals", ["tenant_id", "opportunity_id"], unique=True)
    op.execute(
        "ALTER TABLE risk_signals ADD CONSTRAINT chk_risk_signals_unique "
        "UNIQUE (tenant_id, opportunity_id)"
    )
    op.execute("ALTER TABLE risk_signals ADD CONSTRAINT chk_risk_level CHECK (risk_level IN ('low','medium','high'))")


def downgrade() -> None:
    op.execute("ALTER TABLE recommendations DROP CONSTRAINT IF EXISTS chk_next_action")
    op.execute("ALTER TABLE recommendations DROP CONSTRAINT IF EXISTS chk_confidence")
    op.execute("ALTER TABLE recommendations DROP CONSTRAINT IF EXISTS chk_recommendations_unique")
    op.execute("ALTER TABLE risk_signals DROP CONSTRAINT IF EXISTS chk_risk_level")
    op.execute("ALTER TABLE risk_signals DROP CONSTRAINT IF EXISTS chk_risk_signals_unique")
    op.drop_table("risk_signals")
    op.drop_table("recommendations")
