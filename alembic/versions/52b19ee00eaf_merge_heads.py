"""Merge nine parallel heads into one.

Revision ID: 52b19ee00eaf
Revises: 7b1a2c3d4e5f
Create Date: 2026-05-30 11:03:03.754025

Converges all nine branches that descend from merge_heads_63274_addcp001
into a single linear head.  All structural DDL from the nine branches is
replicated here so that any single-head upgrade path produces the complete
schema.

The nine branches are:
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

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "52b19ee00eaf"
down_revision: str | Sequence[str] | None = "7b1a2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── a52e1317da90: import_jobs + export_jobs ─────────────────────────────
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_import_jobs_tenant_id"), "import_jobs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_import_jobs_entity_type"), "import_jobs", ["entity_type"], unique=False)
    # tenant_id FK for import_jobs — catches DBs that arrived via a path that
    # skipped this migration; uses IF NOT EXISTS so existing constraints are
    # not broken.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE import_jobs ADD CONSTRAINT fk_import_jobs_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_export_jobs_tenant_id"), "export_jobs", ["tenant_id"], unique=False)
    # tenant_id FK for export_jobs — catches DBs that arrived via a path that
    # skipped this migration; uses IF NOT EXISTS so existing constraints are
    # not broken.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE export_jobs ADD CONSTRAINT fk_export_jobs_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
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
    op.create_index(op.f("ix_automation_rules_created_by"), "automation_rules", ["created_by"], unique=False)
    # tenant_id FK for automation_rules — catches DBs that arrived via a path
    # that skipped this migration; uses IF NOT EXISTS so existing constraints
    # (added by an earlier repair migration) are not broken.
    # Only duplicate_object (constraint already exists) and undefined_object
    # (table not present — should not occur in normal upgrade) are caught.
    # syntax_error and other SQL failures indicate a real problem and must not
    # be silently suppressed.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE automation_rules ADD CONSTRAINT fk_automation_rules_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )

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
    # tenant_id FK for automation_logs — catches DBs that arrived via a path
    # that skipped this migration; uses IF NOT EXISTS so existing constraints
    # (added by an earlier repair migration) are not broken.
    # Only duplicate_object (constraint already exists) and undefined_object
    # (table not present — should not occur in normal upgrade) are caught.
    # syntax_error and other SQL failures indicate a real problem and must not
    # be silently suppressed.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE automation_logs ADD CONSTRAINT fk_automation_logs_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )

    # ── add_agent_tasks_001: agent_tasks ─────────────────────────────────────
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("subtasks", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tasks_tenant_id", "agent_tasks", ["tenant_id"], unique=False)
    # Composite (task_id, tenant_id) unique is redundant — task_id alone is unique.
    op.create_index(op.f("ix_agent_tasks_task_id"), "agent_tasks", ["task_id"], unique=True)
    # Convert anonymous unique index to a named constraint (rule 125 / migration encapsulation).
    op.drop_index(op.f("ix_agent_tasks_task_id"), table_name="agent_tasks")
    op.create_unique_constraint("uq_agent_tasks_task_id", "agent_tasks", ["task_id"])
    # tenant_id FK for agent_tasks — catches DBs that arrived via a path that
    # skipped this migration; uses IF NOT EXISTS so existing constraints are
    # not broken.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE agent_tasks ADD CONSTRAINT fk_agent_tasks_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )

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
        sa.Column("owner_tenant_id", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_report_definitions_tenant_id"), "report_definitions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_report_definitions_report_type"), "report_definitions", ["report_type"], unique=False)
    op.create_index(op.f("ix_report_definitions_owner_tenant_id"), "report_definitions", ["owner_tenant_id"], unique=False)
    # tenant_id FK for report_definitions — catches DBs that arrived via a path
    # that skipped this migration; uses IF NOT EXISTS so existing constraints are
    # not broken.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE report_definitions ADD CONSTRAINT fk_report_definitions_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )

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
    # tenant_id FK for conversations — catches DBs that arrived via a path that
    # skipped this migration; uses IF NOT EXISTS so existing constraints are
    # not broken.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE conversations ADD CONSTRAINT fk_conversations_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )

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
    op.create_index("ix_conversation_messages_tenant_id", "conversation_messages", ["tenant_id"], unique=False)
    # tenant_id FK for conversation_messages — catches DBs that arrived via a path
    # that skipped this migration; uses IF NOT EXISTS so existing constraints are
    # not broken.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE conversation_messages ADD CONSTRAINT fk_conversation_messages_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )

    # ── e1f2a3b4c5d6: opportunity_activities ──────────────────────────────────
    # Assumes `opportunities` table already exists (stamped by a prior head).
    op.create_table(
        "opportunity_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opportunity_activities_tenant_id"), "opportunity_activities", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_opportunity_activities_opportunity_id"), "opportunity_activities", ["opportunity_id"], unique=False)
    # tenant_id FK for opportunity_activities — catches DBs that arrived via a path
    # that skipped this migration.
    # Only duplicate_object (constraint already exists) and undefined_object
    # (table not present) are caught; syntax_error indicates a real problem.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE opportunity_activities ADD CONSTRAINT fk_opportunity_activities_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )

    # ── f18b406b982a: customer_enrichments ────────────────────────────────────
    op.create_table(
        "customer_enrichments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
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
    # tenant_id FK uses a DO block so DBs that already have the constraint
    # (arriving via a path that added it already) are not broken.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE customer_enrichments ADD CONSTRAINT fk_customer_enrichments_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object OR undefined_object THEN NULL; "
            "END $$"
        )
    )
    op.create_index(op.f("ix_customer_enrichments_tenant_id"), "customer_enrichments", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_customer_enrichments_customer_id"), "customer_enrichments", ["customer_id"], unique=False)
    op.create_index(op.f("ix_customer_enrichments_next_refresh_at"), "customer_enrichments", ["next_refresh_at"], unique=False)


def downgrade() -> None:
    # Tables are dropped by merge_heads_63274_addcp001.downgrade(), which is this
    # migration's single parent — nothing to drop here.
    pass
