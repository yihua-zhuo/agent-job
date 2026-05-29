"""add_rbac_schema

Revision ID: 195a79d95b41
Revises: c94d682d4b03
Create Date: 2026-05-23 12:00:00.000000

Creates the RBAC schema:
- roles: system and custom tenant roles with priority ordering
- permissions: named permissions organized by category
- user_roles: role assignments per user per tenant
- role_permissions: many-to-many role ↔ permission mapping

Includes full seeding of the 5 system roles and 15 permissions defined in
services/rbac_service.py.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "195a79d95b41"
down_revision: str | None = "c94d682d4b03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

ROLE_INSERT = """
INSERT INTO roles (tenant_id, name, display_name, description, is_system, priority, created_at)
VALUES
    (0, 'admin',  'Administrator',          'Full system access',                            true,   100, now()),
    (0, 'manager','Manager',                'Manage team',                                   true,    80, now()),
    (0, 'sales', 'Sales Representative',   'Manage customers and opportunities',           true,    60, now()),
    (0, 'support','Support Agent',          'View customers and tickets, manage support',    true,    50, now()),
    (0, 'viewer', 'Viewer',                 'Read-only access',                              true,    10, now())
ON CONFLICT DO NOTHING
"""

PERMISSION_INSERT = """
INSERT INTO permissions (name, display_name, category, description)
VALUES
    ('customer:create', 'Create Customer',   'customer', ''),
    ('customer:read',   'Read Customer',    'customer', ''),
    ('customer:update', 'Update Customer',  'customer', ''),
    ('customer:delete', 'Delete Customer',  'customer', ''),
    ('opportunity:create', 'Create Opportunity', 'opportunity', ''),
    ('opportunity:read',   'Read Opportunity',   'opportunity', ''),
    ('opportunity:update', 'Update Opportunity', 'opportunity', ''),
    ('opportunity:delete', 'Delete Opportunity', 'opportunity', ''),
    ('ticket:create', 'Create Ticket',      'ticket', ''),
    ('ticket:read',   'Read Ticket',        'ticket', ''),
    ('ticket:update', 'Update Ticket',      'ticket', ''),
    ('ticket:delete', 'Delete Ticket',      'ticket', ''),
    ('user:manage',   'Manage Users',       'user', ''),
    ('user:read',     'Read User',          'user', ''),
    ('admin:all',      'Full Admin Access',  'admin', '')
ON CONFLICT DO NOTHING
"""

ROLE_PERMISSION_INSERT = """
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE (r.name, p.name) IN (
    -- admin: all permissions
    ('admin', 'customer:create'), ('admin', 'customer:read'), ('admin', 'customer:update'), ('admin', 'customer:delete'),
    ('admin', 'opportunity:create'), ('admin', 'opportunity:read'), ('admin', 'opportunity:update'), ('admin', 'opportunity:delete'),
    ('admin', 'ticket:create'), ('admin', 'ticket:read'), ('admin', 'ticket:update'), ('admin', 'ticket:delete'),
    ('admin', 'user:manage'), ('admin', 'user:read'), ('admin', 'admin:all'),
    -- manager: read + limited write + user:read
    ('manager', 'customer:read'), ('manager', 'customer:update'),
    ('manager', 'opportunity:read'), ('manager', 'opportunity:create'), ('manager', 'opportunity:update'),
    ('manager', 'ticket:read'), ('manager', 'ticket:create'), ('manager', 'ticket:update'),
    ('manager', 'user:read'),
    -- sales: customer + opportunity
    ('sales', 'customer:read'), ('sales', 'customer:create'), ('sales', 'customer:update'),
    ('sales', 'opportunity:read'), ('sales', 'opportunity:create'), ('sales', 'opportunity:update'),
    -- support: read + ticket write
    ('support', 'customer:read'),
    ('support', 'opportunity:read'),
    ('support', 'ticket:read'), ('support', 'ticket:create'), ('support', 'ticket:update'),
    -- viewer: read only
    ('viewer', 'customer:read'),
    ('viewer', 'opportunity:read'),
    ('viewer', 'ticket:read')
)
ON CONFLICT DO NOTHING
"""



def upgrade() -> None:
    # --- permissions (no FK dependencies) ------------------------------------
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=sa.text("''")),
        sa.Column("category", sa.String(length=50), nullable=False, server_default=sa.text("''")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_permissions_name"),
    )
    op.create_index("ix_permissions_name", "permissions", ["name"], unique=True)

    # --- roles ----------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"], unique=False)
    op.create_index("ix_roles_tenant_name", "roles", ["tenant_id", "name"], unique=True)

    # --- role_permissions -------------------------------------------------------
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"], unique=False)
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"], unique=False)

    # --- user_roles ------------------------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"], unique=False)
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"], unique=False)
    op.create_index("ix_user_roles_tenant_id", "user_roles", ["tenant_id"], unique=False)
    op.create_index(
        "ix_user_roles_user_tenant_role", "user_roles", ["user_id", "tenant_id", "role_id"], unique=True
    )

    # --- Seed data -------------------------------------------------------------
    op.execute(PERMISSION_INSERT)
    op.execute(ROLE_INSERT)
    op.execute(ROLE_PERMISSION_INSERT)


def downgrade() -> None:
    op.drop_index("ix_user_roles_user_tenant_role", table_name="user_roles")
    op.drop_index("ix_user_roles_tenant_id", table_name="user_roles")
    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")

    op.drop_index("ix_role_permissions_permission_id", table_name="role_permissions")
    op.drop_index("ix_role_permissions_role_id", table_name="role_permissions")
    op.drop_table("role_permissions")

    op.drop_index("ix_roles_tenant_name", table_name="roles")
    op.drop_index("ix_roles_tenant_id", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_permissions_name", table_name="permissions")
    op.drop_table("permissions")
