"""create automation_rules and automation_logs

Revision ID: e646948c549a
Revises: 9d8e7f6a5b3c
Create Date: 2026-05-23 19:18:51.914803

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e646948c549a'
down_revision: Union[str, None] = '9d8e7f6a5b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("trigger_event", sa.String(length=100), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_automation_rules_tenant_id"), "automation_rules", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_automation_rules_trigger_event"),
        "automation_rules",
        ["trigger_event"],
        unique=False,
    )
    op.create_table(
        "automation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "rule_id",
            sa.Integer(),
            sa.ForeignKey("automation_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("trigger_event", sa.String(length=100), nullable=False),
        sa.Column(
            "trigger_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "actions_executed",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_by", sa.Integer(), nullable=False),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_automation_logs_rule_id"), "automation_logs", ["rule_id"], unique=False
    )
    op.create_index(
        op.f("ix_automation_logs_tenant_id"), "automation_logs", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_logs_tenant_id"), table_name="automation_logs")
    op.drop_index(op.f("ix_automation_logs_rule_id"), table_name="automation_logs")
    op.drop_table("automation_logs")
    op.drop_index(op.f("ix_automation_rules_trigger_event"), table_name="automation_rules")
    op.drop_index(op.f("ix_automation_rules_tenant_id"), table_name="automation_rules")
    op.drop_table("automation_rules")