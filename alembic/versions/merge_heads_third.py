"""merge 185055a0d4f0, addcp001, db67d696b6ab heads

Revision ID: merge_heads_third
Revises: 185055a0d4f0, addcp001, db67d696b6ab
Create Date: 2026-05-30 12:00:00.000000

Three migration heads are present:
  - 185055a0d4f0 (add_workflow_nodes) descends from 82ecf4a34e34
  - addcp001 (add_churn_predictions) descends from 9d8e7f6a5b3c
  - db67d696b6ab (add identity subsystem) descends from 7b1a2c3d4e5f

This revision merges all three into a single head so that
'alembic upgrade head' succeeds without ambiguity.

All schema DDL lives in the sub-revisions above; this merge revision
carries no table/index/constraint operations.

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "merge_heads_third"
down_revision: str | Sequence[str] | None = ("185055a0d4f0", "addcp001", "db67d696b6ab")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass