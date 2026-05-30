"""Merge 10 heads produced by parallel migration work.

Merges the following revisions (all non-no-op, with real schema operations):
  a52e1317da90  — add import_export_jobs
  63274a8b98b3c — add webhook tables
  e646948c549a  — create automation_rules and automation_logs
  add_agent_tasks_001 — add_agent_tasks
  afa7c3f333bd  — add_sent_at_to_campaigns
  c94d682d4b04  — add_report_definitions
  db63fcd03ab9  — add_conversations_and_messages
  e1f2a3b4c5d6  — create_opportunity_activities
  f18b406b982a  — create_customer_enrichments

Each merged revision contains its own upgrade/downgrade operations; this
merge revision is a head-marker only and does not re-state those ops.
The down_revision tuple lists all merged heads; downgrade is a no-op
because there is no single linear revision to step back to — each
constituent migration must be downgraded individually.

Revision ID: 52b19ee00eaf
down_revision: Union[str, None] = ('a52e1317da90', '63274a8b98b3c', 'e646948c549a', 'add_agent_tasks_001', 'afa7c3f333bd', 'c94d682d4b04', 'db63fcd03ab9', 'e1f2a3b4c5d6', 'f18b406b982a')
Create Date: 2026-05-30 11:03:03.754025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52b19ee00eaf'
down_revision: Union[str, None] = ('a52e1317da90', '63274a8b98b3c', 'e646948c549a', 'add_agent_tasks_001', 'afa7c3f333bd', 'c94d682d4b04', 'db63fcd03ab9', 'e1f2a3b4c5d6', 'f18b406b982a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass