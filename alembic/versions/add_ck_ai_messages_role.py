"""add_check_constraint_ai_messages_role

Revision ID: add_ck_ai_messages_role
Revises: merge_all_heads_final
Create Date: 2026-06-01 07:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_ck_ai_messages_role"
down_revision: str | Sequence[str] | None = "merge_all_heads_final"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The ORM model AIMessageModel defines CheckConstraint("role IN ('user', 'assistant')")
    # but this was omitted from the initial migration c94d682d4b03.  Add it now so the
    # database enforces the role constraint at the DB level.
    op.create_check_constraint(
        "ck_ai_messages_role",
        "ai_messages",
        "role IN ('user', 'assistant')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ai_messages_role", "ai_messages", "check")