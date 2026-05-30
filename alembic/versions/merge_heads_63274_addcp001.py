"""Merge four parallel heads into one.

Revision ID: merge_heads_63274_addcp001
Revises: 185055a0d4f0, db67d696b6ab, 63274a8b98b3c, addcp001
Create Date: 2026-05-30 12:30:00.000000

The four heads are:
- 185055a0d4f0 (workflow_nodes, parented to 82ecf4a34e34)
- db67d696b6ab (identity subsystem + schema drift, parented to 7b1a2c3d4e5f)
- 63274a8b98b3c (webhook tables, parented to 9d8e7f6a5b3c)
- addcp001 (churn_predictions, parented to 9d8e7f6a5b3c)

All structural DDL from the four branches is replicated here so that any
single-head upgrade path produces the complete schema.  downgrade() drops
everything in reverse dependency order (parent-child before parent).
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "merge_heads_63274_addcp001"
down_revision: str | Sequence[str] | None = ("185055a0d4f0", "db67d696b6ab", "63274a8b98b3c", "addcp001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 185055a0d4f0: workflow_nodes ───────────────────────────────────────
    op.create_table(
        "workflow_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("node_type", sa.String(length=50), nullable=False),
        sa.Column("definition_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("execution_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_nodes_tenant_id"), "workflow_nodes", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_workflow_nodes_workflow_id"), "workflow_nodes", ["workflow_id"], unique=False)
    op.create_index(op.f("ix_workflow_nodes_tenant_id_workflow_id"), "workflow_nodes", ["tenant_id", "workflow_id"], unique=False)

    # ── 63274a8b98b3c: webhooks + webhook_deliveries ─────────────────────────
    op.create_table(
        "webhooks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("events", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("secret", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhooks_tenant_id"), "webhooks", ["tenant_id"], unique=False)
    op.create_index("ix_webhooks_tenant_active", "webhooks", ["tenant_id", "is_active"], unique=False)

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("webhook_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("response", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhook_deliveries_tenant_id"), "webhook_deliveries", ["tenant_id"], unique=False)
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"], unique=False)

    # ── addcp001: churn_predictions ─────────────────────────────────────────
    op.create_table(
        "churn_predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("tier", sa.String(length=50), nullable=True),
        sa.Column("factors", postgresql.JSON(astext_type=sa.Text()), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_churn_predictions_tenant_id"), "churn_predictions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_churn_predictions_customer_id"), "churn_predictions", ["customer_id"], unique=False)
    op.create_index("ix_churn_predictions_tenant_customer", "churn_predictions", ["tenant_id", "customer_id"], unique=False)

    # ── db67d696b6ab: identity subsystem + schema drift ─────────────────────
    # identity_permissions
    op.create_table(
        "identity_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_identity_permissions_name"), "identity_permissions", ["name"], unique=True)

    # identity_tenants
    op.create_table(
        "identity_tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("settings", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # identity_organizations
    op.create_table(
        "identity_organizations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["identity_tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_identity_org_tenant_slug"),
    )
    op.create_index(op.f("ix_identity_organizations_tenant_id"), "identity_organizations", ["tenant_id"], unique=False)

    # identity_roles
    op.create_table(
        "identity_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["identity_tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_identity_role_tenant_name"),
    )
    op.create_index(op.f("ix_identity_roles_tenant_id"), "identity_roles", ["tenant_id"], unique=False)

    # identity_users
    op.create_table(
        "identity_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["identity_tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_identity_user_tenant_email"),
        sa.UniqueConstraint("tenant_id", "username", name="uq_identity_user_tenant_username"),
    )
    op.create_index(op.f("ix_identity_users_tenant_id"), "identity_users", ["tenant_id"], unique=False)

    # identity_departments
    op.create_table(
        "identity_departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["identity_organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["identity_departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["identity_tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_identity_departments_organization_id"), "identity_departments", ["organization_id"], unique=False)
    op.create_index(op.f("ix_identity_departments_parent_id"), "identity_departments", ["parent_id"], unique=False)
    op.create_index(op.f("ix_identity_departments_tenant_id"), "identity_departments", ["tenant_id"], unique=False)

    # identity_role_permissions
    op.create_table(
        "identity_role_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["identity_permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["identity_roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_identity_role_permission"),
    )
    op.create_index(op.f("ix_identity_role_permissions_permission_id"), "identity_role_permissions", ["permission_id"], unique=False)
    op.create_index(op.f("ix_identity_role_permissions_role_id"), "identity_role_permissions", ["role_id"], unique=False)

    # identity_user_roles
    op.create_table(
        "identity_user_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["identity_roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["identity_tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", "role_id", name="uq_identity_user_role_tenant"),
    )
    op.create_index(op.f("ix_identity_user_roles_role_id"), "identity_user_roles", ["role_id"], unique=False)
    op.create_index(op.f("ix_identity_user_roles_tenant_id"), "identity_user_roles", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_identity_user_roles_user_id"), "identity_user_roles", ["user_id"], unique=False)

    # agent_tasks: unique index → named unique constraint
    op.drop_index(op.f("ix_agent_tasks_task_id"), table_name="agent_tasks")
    op.create_unique_constraint("uq_agent_tasks_task_id", "agent_tasks", ["task_id"])

    # automation FKs to tenants
    op.create_foreign_key(
        "fk_automation_logs_tenant_id", "automation_logs", "tenants", ["tenant_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_automation_rules_tenant_id", "automation_rules", "tenants", ["tenant_id"], ["id"]
    )

    # missing tenant_id indexes on auth tables
    op.create_index(op.f("ix_device_trust_tenant_id"), "device_trust", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_tenant_id"), "refresh_tokens", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_user_credentials_tenant_id"), "user_credentials", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_webauthn_challenges_tenant_id"), "webauthn_challenges", ["tenant_id"], unique=False)


def downgrade() -> None:
    # Reverse each branch's DDL in reverse dependency order.
    # churn_predictions (addcp001):
    op.drop_index("ix_churn_predictions_tenant_customer", table_name="churn_predictions")
    op.drop_index(op.f("ix_churn_predictions_customer_id"), table_name="churn_predictions")
    op.drop_index(op.f("ix_churn_predictions_tenant_id"), table_name="churn_predictions")
    op.drop_table("churn_predictions")
    # webhook tables (63274a8b98b3c):
    op.drop_index("ix_webhook_deliveries_webhook_id", table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_tenant_id"), table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhooks_tenant_active", table_name="webhooks")
    op.drop_index(op.f("ix_webhooks_tenant_id"), table_name="webhooks")
    op.drop_table("webhooks")
    # identity subsystem + schema drift (db67d696b6ab):
    op.drop_index(op.f("ix_webauthn_challenges_tenant_id"), table_name="webauthn_challenges")
    op.drop_index(op.f("ix_user_credentials_tenant_id"), table_name="user_credentials")
    op.drop_index(op.f("ix_refresh_tokens_tenant_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_device_trust_tenant_id"), table_name="device_trust")
    op.drop_constraint("fk_automation_rules_tenant_id", "automation_rules", type_="foreignkey")
    op.drop_constraint("fk_automation_logs_tenant_id", "automation_logs", type_="foreignkey")
    op.drop_constraint("uq_agent_tasks_task_id", "agent_tasks", type_="unique")
    op.create_index(op.f("ix_agent_tasks_task_id"), "agent_tasks", ["task_id"], unique=True)
    op.drop_index(op.f("ix_identity_user_roles_user_id"), table_name="identity_user_roles")
    op.drop_index(op.f("ix_identity_user_roles_tenant_id"), table_name="identity_user_roles")
    op.drop_index(op.f("ix_identity_user_roles_role_id"), table_name="identity_user_roles")
    op.drop_table("identity_user_roles")
    op.drop_index(op.f("ix_identity_role_permissions_role_id"), table_name="identity_role_permissions")
    op.drop_index(op.f("ix_identity_role_permissions_permission_id"), table_name="identity_role_permissions")
    op.drop_table("identity_role_permissions")
    op.drop_index(op.f("ix_identity_departments_tenant_id"), table_name="identity_departments")
    op.drop_index(op.f("ix_identity_departments_parent_id"), table_name="identity_departments")
    op.drop_index(op.f("ix_identity_departments_organization_id"), table_name="identity_departments")
    op.drop_table("identity_departments")
    op.drop_index(op.f("ix_identity_users_tenant_id"), table_name="identity_users")
    op.drop_table("identity_users")
    op.drop_index(op.f("ix_identity_roles_tenant_id"), table_name="identity_roles")
    op.drop_table("identity_roles")
    op.drop_index(op.f("ix_identity_organizations_tenant_id"), table_name="identity_organizations")
    op.drop_table("identity_organizations")
    op.drop_table("identity_tenants")
    op.drop_index(op.f("ix_identity_permissions_name"), table_name="identity_permissions")
    op.drop_table("identity_permissions")
    # workflow_nodes (185055a0d4f0):
    op.drop_index(op.f("ix_workflow_nodes_tenant_id_workflow_id"), table_name="workflow_nodes")
    op.drop_index(op.f("ix_workflow_nodes_workflow_id"), table_name="workflow_nodes")
    op.drop_index(op.f("ix_workflow_nodes_tenant_id"), table_name="workflow_nodes")
    op.drop_table("workflow_nodes")
