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

NOTE: This is a merge-only revision — no schema changes are made by this file
itself; all tables/indexes/FKs are created in the sub-revisions it depends on.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "merge_heads_third"
down_revision: str | Sequence[str] | None = ("185055a0d4f0", "addcp001", "db67d696b6ab")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── db67d696b6ab: identity subsystem ──────────────────────────────────
    op.create_table(
        'identity_permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_identity_permissions_name'), 'identity_permissions', ['name'], unique=True)

    op.create_table(
        'identity_tenants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('settings', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'identity_organizations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['identity_tenants.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_identity_org_tenant_slug'),
    )
    op.create_index(op.f('ix_identity_organizations_tenant_id'), 'identity_organizations', ['tenant_id'], unique=False)

    op.create_table(
        'identity_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['identity_tenants.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_identity_role_tenant_name'),
    )
    op.create_index(op.f('ix_identity_roles_tenant_id'), 'identity_roles', ['tenant_id'], unique=False)

    op.create_table(
        'identity_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['identity_tenants.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_identity_user_tenant_email'),
        sa.UniqueConstraint('tenant_id', 'username', name='uq_identity_user_tenant_username'),
    )
    op.create_index(op.f('ix_identity_users_tenant_id'), 'identity_users', ['tenant_id'], unique=False)

    op.create_table(
        'identity_departments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['identity_organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['identity_departments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['identity_tenants.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_identity_departments_organization_id'), 'identity_departments', ['organization_id'], unique=False)
    op.create_index(op.f('ix_identity_departments_parent_id'), 'identity_departments', ['parent_id'], unique=False)
    op.create_index(op.f('ix_identity_departments_tenant_id'), 'identity_departments', ['tenant_id'], unique=False)

    op.create_table(
        'identity_role_permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['identity_permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['identity_roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_identity_role_permission'),
    )
    op.create_index(op.f('ix_identity_role_permissions_permission_id'), 'identity_role_permissions', ['permission_id'], unique=False)
    op.create_index(op.f('ix_identity_role_permissions_role_id'), 'identity_role_permissions', ['role_id'], unique=False)

    op.create_table(
        'identity_user_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('granted_by', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['identity_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['identity_tenants.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['identity_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tenant_id', 'role_id', name='uq_identity_user_role_tenant'),
    )
    op.create_index(op.f('ix_identity_user_roles_role_id'), 'identity_user_roles', ['role_id'], unique=False)
    op.create_index(op.f('ix_identity_user_roles_tenant_id'), 'identity_user_roles', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_identity_user_roles_user_id'), 'identity_user_roles', ['user_id'], unique=False)

    # ── db67d696b6ab: agent_tasks unique index → constraint ───────────────
    op.drop_index(op.f('ix_agent_tasks_task_id'), table_name='agent_tasks')
    op.create_unique_constraint('uq_agent_tasks_task_id', 'agent_tasks', ['task_id'])

    # ── db67d696b6ab: automation FKs ─────────────────────────────────────
    op.create_foreign_key('fk_automation_logs_tenant_id', 'automation_logs', 'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key('fk_automation_rules_tenant_id', 'automation_rules', 'tenants', ['tenant_id'], ['id'])

    # ── db67d696b6ab: missing tenant_id indexes on auth tables ────────────
    op.create_index(op.f('ix_device_trust_tenant_id'), 'device_trust', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_tenant_id'), 'refresh_tokens', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_user_credentials_tenant_id'), 'user_credentials', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_webauthn_challenges_tenant_id'), 'webauthn_challenges', ['tenant_id'], unique=False)

    # ── db67d696b6ab: routing_rules table ────────────────────────────────
    op.create_table(
        'routing_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('conditions_json', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column('assignee_type', sa.String(length=50), nullable=False, server_default='round_robin'),
        sa.Column('assignee_id', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_routing_rules_tenant_id'), 'routing_rules', ['tenant_id'], unique=False)

    # ── 185055a0d4f0: workflow_nodes ───────────────────────────────────────
    op.create_table(
        'workflow_nodes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('node_type', sa.String(length=50), nullable=False),
        sa.Column('definition_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('execution_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workflow_nodes_tenant_id'), 'workflow_nodes', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_workflow_nodes_workflow_id'), 'workflow_nodes', ['workflow_id'], unique=False)
    op.create_index(op.f('ix_workflow_nodes_tenant_id_workflow_id'), 'workflow_nodes', ['tenant_id', 'workflow_id'], unique=False)

    # ── addcp001: churn_predictions ────────────────────────────────────────
    op.create_table(
        'churn_predictions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('tier', sa.String(length=50), nullable=True),
        sa.Column('factors', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('predicted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_churn_predictions_tenant_id'), 'churn_predictions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_churn_predictions_customer_id'), 'churn_predictions', ['customer_id'], unique=False)
    op.create_index('ix_churn_predictions_tenant_customer', 'churn_predictions', ['tenant_id', 'customer_id'], unique=False)


def downgrade() -> None:
    # ── reverse addcp001 ──────────────────────────────────────────────────
    op.drop_index('ix_churn_predictions_tenant_customer', table_name='churn_predictions')
    op.drop_index(op.f('ix_churn_predictions_customer_id'), table_name='churn_predictions')
    op.drop_index(op.f('ix_churn_predictions_tenant_id'), table_name='churn_predictions')
    op.drop_table('churn_predictions')

    # ── reverse 185055a0d4f0 ──────────────────────────────────────────────
    op.drop_index(op.f('ix_workflow_nodes_tenant_id_workflow_id'), table_name='workflow_nodes')
    op.drop_index(op.f('ix_workflow_nodes_workflow_id'), table_name='workflow_nodes')
    op.drop_index(op.f('ix_workflow_nodes_tenant_id'), table_name='workflow_nodes')
    op.drop_table('workflow_nodes')

    # ── reverse db67d696b6ab: routing_rules ───────────────────────────────
    op.drop_index(op.f('ix_routing_rules_tenant_id'), table_name='routing_rules')
    op.drop_table('routing_rules')

    # ── reverse db67d696b6ab: auth table indexes ─────────────────────────
    op.drop_index(op.f('ix_webauthn_challenges_tenant_id'), table_name='webauthn_challenges')
    op.drop_index(op.f('ix_user_credentials_tenant_id'), table_name='user_credentials')
    op.drop_index(op.f('ix_refresh_tokens_tenant_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_device_trust_tenant_id'), table_name='device_trust')

    # ── reverse db67d696b6ab: automation FKs ─────────────────────────────
    op.drop_constraint('fk_automation_rules_tenant_id', 'automation_rules', type_='foreignkey')
    op.drop_constraint('fk_automation_logs_tenant_id', 'automation_logs', type_='foreignkey')

    # ── reverse db67d696b6ab: agent_tasks constraint → index ──────────────
    op.drop_constraint('uq_agent_tasks_task_id', 'agent_tasks', type_='unique')
    op.create_index(op.f('ix_agent_tasks_task_id'), 'agent_tasks', ['task_id'], unique=True)

    # ── reverse db67d696b6ab: identity subsystem ─────────────────────────
    op.drop_index(op.f('ix_identity_user_roles_user_id'), table_name='identity_user_roles')
    op.drop_index(op.f('ix_identity_user_roles_tenant_id'), table_name='identity_user_roles')
    op.drop_index(op.f('ix_identity_user_roles_role_id'), table_name='identity_user_roles')
    op.drop_table('identity_user_roles')

    op.drop_index(op.f('ix_identity_role_permissions_role_id'), table_name='identity_role_permissions')
    op.drop_index(op.f('ix_identity_role_permissions_permission_id'), table_name='identity_role_permissions')
    op.drop_table('identity_role_permissions')

    op.drop_index(op.f('ix_identity_departments_tenant_id'), table_name='identity_departments')
    op.drop_index(op.f('ix_identity_departments_parent_id'), table_name='identity_departments')
    op.drop_index(op.f('ix_identity_departments_organization_id'), table_name='identity_departments')
    op.drop_table('identity_departments')

    op.drop_index(op.f('ix_identity_users_tenant_id'), table_name='identity_users')
    op.drop_table('identity_users')

    op.drop_index(op.f('ix_identity_roles_tenant_id'), table_name='identity_roles')
    op.drop_table('identity_roles')

    op.drop_index(op.f('ix_identity_organizations_tenant_id'), table_name='identity_organizations')
    op.drop_table('identity_organizations')

    op.drop_table('identity_tenants')

    op.drop_index(op.f('ix_identity_permissions_name'), table_name='identity_permissions')
    op.drop_table('identity_permissions')