"""Merge four parallel heads into one.

Revision ID: merge_heads_63274_addcp001
Revises: 185055a0d4f0, db67d696b6ab, 63274a8b98b3c, addcp001
Create Date: 2026-05-30 12:30:00.000000

The four heads are:
- 185055a0d4f0 (workflow_nodes, parented to 82ecf4a34e34)
- db67d696b6ab (identity subsystem + schema drift, parented to 7b1a2c3d4e5f)
- 63274a8b98b3c (webhook tables, parented to 9d8e7f6a5b3c)
- addcp001 (churn_predictions, parented to 9d8e7f6a5b3c)

DDL for all four branches is captured in their respective upgrade() bodies;
this merge point has no additional structural changes.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "merge_heads_63274_addcp001"
down_revision: str | None = ("185055a0d4f0", "db67d696b6ab", "63274a8b98b3c", "addcp001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # All structural DDL is in the merged branch migrations:
    # - 185055a0d4f0: creates workflow_nodes table
    # - db67d696b6ab: creates identity_* subsystem, automation FKs, tenant indexes
    # - 63274a8b98b3c: creates webhooks + webhook_deliveries tables
    # - addcp001: creates churn_predictions table
    pass


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
