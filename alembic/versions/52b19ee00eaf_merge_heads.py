"""Merge six parallel heads into one.

Revision ID: 52b19ee00eaf
Revises: merge_heads_63274_addcp001
Create Date: 2026-05-30 11:03:03.754025

Converges all six branches that descend from merge_heads_63274_addcp001
into a single linear head.  All structural DDL from the six branches is
replicated here so that any single-head upgrade path produces the complete
schema.

The six branches are:
- a52e1317da90: import_jobs + export_jobs
- 82ecf4a34e34: pass-through merge (auth + ai heads)
- e646948c549a: automation_rules + automation_logs
- add_agent_tasks_001: agent_tasks
- afa7c3f333bd: add sent_at to campaigns
- c94d682d4b04: report_definitions
- db63fcd03ab9: conversations + conversation_messages
- e1f2a3b4c5d6: opportunity_activities
- f18b406b982a: customer_enrichments

downgrade() is intentionally empty: the tables created by these branches
are dropped by the downgrade() of merge_heads_63274_addcp001, which is
this migration's single parent.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "52b19ee00eaf"
down_revision: Union[str, None] = "merge_heads_63274_addcp001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── a52e1317da90: import_jobs + export_jobs ─────────────────────────────
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── e646948c549a: automation_rules + automation_logs ─────────────────────
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("trigger_event", sa.String(length=100), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_automation_rules_tenant_id"), "automation_rules", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_automation_rules_trigger_event"), "automation_rules", ["trigger_event"], unique=False)

    op.create_table(
        "automation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("trigger_event", sa.String(length=100), nullable=False),
        sa.Column("trigger_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("actions_executed", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'success'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_by", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_automation_logs_tenant_id"), "automation_logs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_automation_logs_rule_id"), "automation_logs", ["rule_id"], unique=False)

    # ── add_agent_tasks_001: agent_tasks ─────────────────────────────────────
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("subtasks", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tasks_tenant_id", "agent_tasks", ["tenant_id"], unique=False)
    op.create_index("ix_agent_tasks_task_id_tenant_id", "agent_tasks", ["task_id", "tenant_id"], unique=True)
    op.create_index(op.f("ix_agent_tasks_task_id"), "agent_tasks", ["task_id"], unique=True)

    # ── afa7c3f333bd: add sent_at to campaigns ────────────────────────────────
    op.add_column("campaigns", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))

    # ── c94d682d4b04: report_definitions ────────────────────────────────────
    op.create_table(
        "report_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("report_type", sa.String(length=100), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("owner_tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_report_definitions_tenant_id"), "report_definitions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_report_definitions_report_type"), "report_definitions", ["report_type"], unique=False)
    op.create_index(op.f("ix_report_definitions_owner_tenant_id"), "report_definitions", ["owner_tenant_id"], unique=False)

    # ── db63fcd03ab9: conversations + conversation_messages ──────────────────
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_tenant_id"), "conversations", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_index("ix_conversations_tenant_user", "conversations", ["tenant_id", "user_id"], unique=False)

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversation_messages_conversation_id"), "conversation_messages", ["conversation_id"], unique=False)
    op.create_index("ix_conversation_messages_tenant_conv", "conversation_messages", ["tenant_id", "conversation_id"], unique=False)

    # ── e1f2a3b4c5d6: opportunity_activities ──────────────────────────────────
    op.create_table(
        "opportunity_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opportunity_activities_tenant_id"), "opportunity_activities", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_opportunity_activities_opportunity_id"), "opportunity_activities", ["opportunity_id"], unique=False)

    # ── f18b406b982a: customer_enrichments ────────────────────────────────────
    op.create_table(
        "customer_enrichments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("raw_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customer_enrichments_customer_id"), "customer_enrichments", ["customer_id"], unique=False)
    op.create_index(op.f("ix_customer_enrichments_next_refresh_at"), "customer_enrichments", ["next_refresh_at"], unique=False)


def downgrade() -> None:
    # Tables created by the six branches (a52e1317da90, e646948c549a,
    # add_agent_tasks_001, c94d682d4b04, db63fcd03ab9, e1f2a3b4c5d6,
    # f18b406b982a) are dropped by the downgrade() of merge_heads_63274_addcp001,
    # which is this migration's single parent.  Dropping them again here
    # would cause a cascade error; therefore this body is intentionally empty.
    pass