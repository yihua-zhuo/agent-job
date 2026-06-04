"""add_churn_predictions

Revision ID: addcp001
Revises: 9d8e7f6a5b3c
Create Date: 2026-05-23 16:03:58.871260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "addcp001"
down_revision: Union[str, None] = "9d8e7f6a5b3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the churn_predictions table, enum, indexes, and constraints."""
    churntier = sa.Enum("high", "medium", "low", name="churntier")
    churntier.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "churn_predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("tier", churntier, nullable=False),
        sa.Column(
            "factors",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "recommended_actions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column(
            "predicted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_churn_predictions_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_churn_predictions_tenant_id"),
        "churn_predictions",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_churn_predictions_customer_id"),
        "churn_predictions",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_churn_predictions_tenant_id_customer_id",
        "churn_predictions",
        ["tenant_id", "customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_churn_predictions_tier"),
        "churn_predictions",
        ["tier"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the churn_predictions table, indexes, and enum type."""
    op.drop_index(
        op.f("ix_churn_predictions_tier"),
        table_name="churn_predictions",
    )
    op.drop_index(
        "ix_churn_predictions_tenant_id_customer_id",
        table_name="churn_predictions",
    )
    op.drop_index(
        op.f("ix_churn_predictions_customer_id"),
        table_name="churn_predictions",
    )
    op.drop_index(
        op.f("ix_churn_predictions_tenant_id"),
        table_name="churn_predictions",
    )
    op.drop_table("churn_predictions")
    sa.Enum(name="churntier").drop(op.get_bind(), checkfirst=True)
