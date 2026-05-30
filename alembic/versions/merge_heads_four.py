"""merge 9aad50c58f54, addcp001, and 9e805b1493a6 heads

Revision ID: merge_heads_four
Revises: 9aad50c58f54, addcp001, 9e805b1493a6
Create Date: 2026-05-30 14:50:00.000000

Three migration heads are present:
  - 9aad50c58f54 (add tenant slug and usage_limits) descends from 9d8e7f6a5b3c
  - addcp001 (add_churn_predictions) descends from 9d8e7f6a5b3c
  - 9e805b1493a6 (add tenant_id to workflow_executions) descends from merge_heads_third

This revision merges all three into a single head so that 'alembic upgrade head'
succeeds without ambiguity on a fresh database.

NOTE: This is a merge-only revision — no schema changes are made by this file
itself; all tables/indexes/FKs are created in the sub-revisions it depends on.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "merge_heads_four"
down_revision: str | Sequence[str] | None = ("9aad50c58f54", "addcp001", "9e805b1493a6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
