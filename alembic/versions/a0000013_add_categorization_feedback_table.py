"""add_categorization_feedback_table

Revision ID: a0000013
Revises: add_ck_ai_messages_role
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a0000013"
down_revision: Union[str, None] = "add_ck_ai_messages_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categorization_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("original_category", sa.String(length=100), nullable=True),
        sa.Column("original_priority", sa.String(length=50), nullable=True),
        sa.Column("corrected_category", sa.String(length=100), nullable=True),
        sa.Column("corrected_priority", sa.String(length=50), nullable=True),
        sa.Column("corrected_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_categorization_feedback_tenant_id"),
        "categorization_feedback",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_categorization_feedback_ticket_id"),
        "categorization_feedback",
        ["ticket_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_categorization_feedback_ticket_id"), table_name="categorization_feedback")
    op.drop_index(op.f("ix_categorization_feedback_tenant_id"), table_name="categorization_feedback")
    op.drop_table("categorization_feedback")
