"""add_churn_predictions

Revision ID: add_churn_predictions
Revises: c94d682d4b03
Create Date: 2026-05-22

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'add_churn_predictions'
down_revision: str | None = 'c94d682d4b03'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "churn_predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "tier",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("factors", sa.JSON, nullable=False),
        sa.Column("recommended_actions", sa.JSON, nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_churn_predictions_tenant_id",
        "churn_predictions",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_churn_predictions_tenant_customer",
        "churn_predictions",
        ["tenant_id", "customer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_churn_predictions_tenant_customer", table_name="churn_predictions")
    op.drop_index("ix_churn_predictions_tenant_id", table_name="churn_predictions")
    op.drop_table("churn_predictions")
