"""Unit tests for identity ORM models."""
import sys
from pathlib import Path

# Ensure src/ is on sys.path
_project_root = Path(__file__).resolve().parents[2]
_src_root = _project_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest
from datetime import datetime

from internal.db.models.identity import (
    TenantModel,
    OrganizationModel,
    DepartmentModel,
    UserModel,
    RoleModel,
    PermissionModel,
    RolePermissionModel,
    UserRoleModel,
)


class TestTenantModel:
    """Tests for TenantModel."""

    def test_instantiation(self):
        tenant = TenantModel(id=1, name="Acme Corp", plan="pro", status="active")
        assert tenant.id == 1
        assert tenant.name == "Acme Corp"
        assert tenant.plan == "pro"
        assert tenant.status == "active"

    def test_defaults(self):
        tenant = TenantModel(name="Beta Inc")
        # SQLAlchemy default= is applied at INSERT, not on Python instantiation.
        # Verify field is defined with default=False.
        col = TenantModel.__table__.columns["is_deleted"]
        assert col.default.arg is False

    def test_settings_default(self):
        tenant = TenantModel(name="Gamma")
        # settings uses JSON default=dict - applied at INSERT.
        col = TenantModel.__table__.columns["settings"]
        assert callable(col.default.arg)

    def test_to_dict(self):
        now = datetime.now()
        tenant = TenantModel(
            id=5,
            name="Delta",
            plan="enterprise",
            status="active",
            settings={"sso": True},
            created_by=1,
            updated_by=2,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            deleted_at=None,
        )
        d = tenant.to_dict()
        assert d["id"] == 5
        assert d["name"] == "Delta"
        assert d["plan"] == "enterprise"
        assert d["status"] == "active"
        assert d["settings"] == {"sso": True}
        assert d["created_by"] == 1
        assert d["updated_by"] == 2
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert isinstance(d["created_at"], str)
        assert isinstance(d["updated_at"], str)

    def test_no_tenant_id(self):
        """TenantModel must not have a tenant_id column."""
        assert not hasattr(TenantModel, "__table__") or "tenant_id" not in [
            c.name for c in TenantModel.__table__.columns
        ]


class TestOrganizationModel:
    """Tests for OrganizationModel."""

    def test_instantiation(self):
        org = OrganizationModel(id=1, tenant_id=10, name="Org One", slug="org-one")
        assert org.id == 1
        assert org.tenant_id == 10
        assert org.name == "Org One"
        assert org.slug == "org-one"
        # is_active default is applied at INSERT; verify column default is True
        assert org.__table__.columns["is_active"].default.arg is True

    def test_defaults(self):
        org = OrganizationModel(tenant_id=1, name="Org Two", slug="org-two")
        # SQLAlchemy default= is applied at INSERT, not on Python instantiation.
        # Verify fields are defined with the correct defaults.
        assert org.__table__.columns["is_deleted"].default.arg is False
        assert org.__table__.columns["is_active"].default.arg is True
        assert org.__table__.columns["created_by"].default.arg == 0
        assert org.__table__.columns["updated_by"].default.arg == 0

    def test_to_dict(self):
        now = datetime.now()
        org = OrganizationModel(
            id=2,
            tenant_id=5,
            name="Acme Org",
            slug="acme-org",
            description="A test org",
            is_active=True,
            created_by=3,
            updated_by=4,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            deleted_at=None,
        )
        d = org.to_dict()
        assert d["id"] == 2
        assert d["tenant_id"] == 5
        assert d["name"] == "Acme Org"
        assert d["slug"] == "acme-org"
        assert d["description"] == "A test org"
        assert d["is_active"] is True
        assert d["created_by"] == 3
        assert d["updated_by"] == 4
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert isinstance(d["created_at"], str)

    def test_has_tenant_id(self):
        col_names = [c.name for c in OrganizationModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_unique_constraint(self):
        constraints = [c.name for c in OrganizationModel.__table__.constraints]
        constraint_names = [getattr(c, "name", None) for c in OrganizationModel.__table__.constraints]
        assert "uq_org_tenant_slug" in constraint_names


class TestDepartmentModel:
    """Tests for DepartmentModel."""

    def test_instantiation(self):
        dept = DepartmentModel(
            id=1, tenant_id=1, organization_id=10, name="Engineering"
        )
        assert dept.id == 1
        assert dept.tenant_id == 1
        assert dept.organization_id == 10
        assert dept.name == "Engineering"

    def test_defaults(self):
        dept = DepartmentModel(tenant_id=1, organization_id=1, name="Sales")
        # SQLAlchemy default= is applied at INSERT, not on Python instantiation.
        # Verify field is defined with default=False.
        assert dept.__table__.columns["is_deleted"].default.arg is False

    def test_parent_hierarchy(self):
        dept = DepartmentModel(
            id=1, tenant_id=1, organization_id=1, name="Engineering", parent_id=None
        )
        # parent_id is nullable (self-referential FK with SET NULL)
        parent_col = DepartmentModel.__table__.columns["parent_id"]
        assert parent_col.nullable is True

    def test_to_dict(self):
        now = datetime.now()
        dept = DepartmentModel(
            id=3,
            tenant_id=7,
            organization_id=1,
            name="QA",
            description="Quality assurance",
            parent_id=None,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            deleted_at=None,
        )
        d = dept.to_dict()
        assert d["id"] == 3
        assert d["tenant_id"] == 7
        assert d["organization_id"] == 1
        assert d["name"] == "QA"
        assert d["description"] == "Quality assurance"
        assert d["parent_id"] is None
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert isinstance(d["created_at"], str)

    def test_has_tenant_id(self):
        col_names = [c.name for c in DepartmentModel.__table__.columns]
        assert "tenant_id" in col_names


class TestUserModel:
    """Tests for UserModel."""

    def test_instantiation(self):
        user = UserModel(
            id=1,
            tenant_id=5,
            username="alice",
            email="alice@example.com",
            full_name="Alice Smith",
        )
        assert user.id == 1
        assert user.tenant_id == 5
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.full_name == "Alice Smith"

    def test_defaults(self):
        user = UserModel(tenant_id=1, username="bob", email="bob@example.com")
        # SQLAlchemy default= is applied at INSERT, not on Python instantiation.
        # Verify fields are defined with the correct defaults.
        assert user.__table__.columns["is_deleted"].default.arg is False
        assert user.__table__.columns["status"].default.arg == "active"

    def test_to_dict(self):
        now = datetime.now()
        user = UserModel(
            id=2,
            tenant_id=10,
            username="carol",
            email="carol@example.com",
            password_hash="hash123",
            full_name="Carol Jones",
            bio="Bio here",
            status="active",
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            created_at=now,
            updated_at=now,
        )
        d = user.to_dict()
        assert d["id"] == 2
        assert d["tenant_id"] == 10
        assert d["username"] == "carol"
        assert d["email"] == "carol@example.com"
        assert d["password_hash"] == "hash123"
        assert d["full_name"] == "Carol Jones"
        assert d["bio"] == "Bio here"
        assert d["status"] == "active"
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert d["deleted_by"] is None
        assert isinstance(d["created_at"], str)

    def test_has_tenant_id(self):
        col_names = [c.name for c in UserModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_unique_constraints(self):
        constraint_names = [getattr(c, "name", None) for c in UserModel.__table__.constraints]
        assert "uq_user_tenant_username" in constraint_names
        assert "uq_user_tenant_email" in constraint_names


class TestRoleModel:
    """Tests for RoleModel."""

    def test_instantiation(self):
        role = RoleModel(
            id=1, tenant_id=3, name="admin", display_name="Administrator"
        )
        assert role.id == 1
        assert role.tenant_id == 3
        assert role.name == "admin"
        assert role.display_name == "Administrator"

    def test_defaults(self):
        role = RoleModel(tenant_id=1, name="viewer", display_name="Viewer")
        # SQLAlchemy default= is applied at INSERT, not on Python instantiation.
        # Verify fields are defined with the correct defaults.
        assert role.__table__.columns["is_deleted"].default.arg is False
        assert role.__table__.columns["is_system"].default.arg is False
        assert role.__table__.columns["priority"].default.arg == 0

    def test_to_dict(self):
        now = datetime.now()
        role = RoleModel(
            id=4,
            tenant_id=2,
            name="editor",
            display_name="Editor",
            description="Can edit content",
            is_system=False,
            priority=10,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            deleted_at=None,
        )
        d = role.to_dict()
        assert d["id"] == 4
        assert d["tenant_id"] == 2
        assert d["name"] == "editor"
        assert d["display_name"] == "Editor"
        assert d["description"] == "Can edit content"
        assert d["is_system"] is False
        assert d["priority"] == 10
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert isinstance(d["created_at"], str)

    def test_has_tenant_id(self):
        col_names = [c.name for c in RoleModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_unique_constraint(self):
        constraint_names = [getattr(c, "name", None) for c in RoleModel.__table__.constraints]
        assert "uq_role_tenant_name" in constraint_names


class TestPermissionModel:
    """Tests for PermissionModel."""

    def test_instantiation(self):
        perm = PermissionModel(
            id=1,
            name="users.read",
            display_name="Read Users",
            category="users",
        )
        assert perm.id == 1
        assert perm.name == "users.read"
        assert perm.display_name == "Read Users"
        assert perm.category == "users"

    def test_defaults(self):
        perm = PermissionModel(name="users.write", display_name="Write Users", category="users")
        # SQLAlchemy default= is applied at INSERT, not on Python instantiation.
        # Verify fields are defined with the correct defaults.
        assert perm.__table__.columns["is_deleted"].default.arg is False
        assert perm.__table__.columns["display_name"].default.arg == ""
        assert perm.__table__.columns["category"].default.arg == ""
        # description is nullable without a default
        desc_col = perm.__table__.columns["description"]
        assert desc_col.nullable is True
        assert desc_col.default is None

    def test_to_dict(self):
        now = datetime.now()
        perm = PermissionModel(
            id=5,
            name="reports.export",
            display_name="Export Reports",
            category="reports",
            description="Can export reports",
            created_at=now,
            updated_at=now,
            is_deleted=False,
            deleted_at=None,
        )
        d = perm.to_dict()
        assert d["id"] == 5
        assert d["name"] == "reports.export"
        assert d["display_name"] == "Export Reports"
        assert d["category"] == "reports"
        assert d["description"] == "Can export reports"
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert isinstance(d["created_at"], str)

    def test_no_tenant_id(self):
        col_names = [c.name for c in PermissionModel.__table__.columns]
        assert "tenant_id" not in col_names


class TestRolePermissionModel:
    """Tests for RolePermissionModel."""

    def test_instantiation(self):
        rp = RolePermissionModel(id=1, role_id=10, permission_id=5)
        assert rp.id == 1
        assert rp.role_id == 10
        assert rp.permission_id == 5

    def test_to_dict(self):
        rp = RolePermissionModel(id=2, role_id=20, permission_id=15)
        d = rp.to_dict()
        assert d["id"] == 2
        assert d["role_id"] == 20
        assert d["permission_id"] == 15
        # no soft-delete fields on junction table
        assert "is_deleted" not in d

    def test_unique_constraint(self):
        constraint_names = [getattr(c, "name", None) for c in RolePermissionModel.__table__.constraints]
        assert "uq_role_permission" in constraint_names

    def test_relationships(self):
        # Verify back-populates are defined (no error on access)
        assert hasattr(RolePermissionModel, "role")
        assert hasattr(RolePermissionModel, "permission")


class TestUserRoleModel:
    """Tests for UserRoleModel."""

    def test_instantiation(self):
        ur = UserRoleModel(
            id=1, user_id=5, role_id=10, tenant_id=3, granted_by=1
        )
        assert ur.id == 1
        assert ur.user_id == 5
        assert ur.role_id == 10
        assert ur.tenant_id == 3
        assert ur.granted_by == 1

    def test_defaults(self):
        ur = UserRoleModel(user_id=1, role_id=1, tenant_id=1, granted_by=1)
        # SQLAlchemy default= is applied at INSERT, not on Python instantiation.
        # Verify field is defined with default=False.
        assert ur.__table__.columns["is_deleted"].default.arg is False

    def test_to_dict(self):
        now = datetime.now()
        ur = UserRoleModel(
            id=7,
            user_id=100,
            role_id=20,
            tenant_id=50,
            granted_by=3,
            granted_at=now,
            is_deleted=False,
            deleted_at=None,
        )
        d = ur.to_dict()
        assert d["id"] == 7
        assert d["user_id"] == 100
        assert d["role_id"] == 20
        assert d["tenant_id"] == 50
        assert d["granted_by"] == 3
        assert isinstance(d["granted_at"], str)
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None

    def test_has_tenant_id(self):
        col_names = [c.name for c in UserRoleModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_unique_constraint(self):
        constraint_names = [getattr(c, "name", None) for c in UserRoleModel.__table__.constraints]
        assert "uq_user_role_tenant" in constraint_names


class TestRelationships:
    """Tests for cross-model relationship resolution."""

    def test_department_organization_relationship(self):
        # Department -> Organization (back_populates)
        cols = {c.name for c in DepartmentModel.__table__.columns}
        rels = {r.key: r for r in DepartmentModel.__mapper__.relationships}
        assert "organization" in rels
        assert "organization_id" in cols

    def test_department_self_referential(self):
        # Department parent/child self-referential FK
        rels = {r.key: r for r in DepartmentModel.__mapper__.relationships}
        assert "parent" in rels
        assert "children" in rels

    def test_role_permissions_relationship(self):
        rels = {r.key: r for r in RoleModel.__mapper__.relationships}
        assert "permissions" in rels
        assert "user_assignments" in rels

    def test_permission_roles_relationship(self):
        rels = {r.key: r for r in PermissionModel.__mapper__.relationships}
        assert "roles" in rels

    def test_role_permission_junction_back_populates(self):
        # RolePermission -> Role
        rels = {r.key: r for r in RolePermissionModel.__mapper__.relationships}
        assert "role" in rels
        assert "permission" in rels

    def test_user_role_relationships(self):
        ur_rels = {r.key: r for r in UserRoleModel.__mapper__.relationships}
        assert "role" in ur_rels
        # Note: UserModel.roles relationship and UserRoleModel.user relationship
        # are intentionally omitted to avoid conflicts with
        # src/db/models/user.py::UserModel (same __tablename__ = "users"
        # in the same Base registry)

    def test_userrole_role_back_populates(self):
        role_rels = {r.key: r for r in RoleModel.__mapper__.relationships}
        assert "user_assignments" in role_rels
        # Verify back-populates matches
        ur_rels = {r.key: r for r in UserRoleModel.__mapper__.relationships}
        assert ur_rels["role"].back_populates == "user_assignments"

    def test_userrole_no_back_populates_to_user(self):
        # UserRoleModel intentionally does not expose a `user` relationship
        # to avoid conflicts with src/db/models/user.py::UserModel
        # (same __tablename__ = "users" in same Base registry)
        ur_rels = {r.key: r for r in UserRoleModel.__mapper__.relationships}
        assert "user" not in ur_rels