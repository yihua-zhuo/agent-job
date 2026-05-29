"""Unit tests for identity ORM models."""

from datetime import datetime

from internal.db.models.identity import (
    IdentityDepartmentModel,
    IdentityOrganizationModel,
    IdentityPermissionModel,
    IdentityRoleModel,
    IdentityRolePermissionModel,
    IdentityTenantModel,
    IdentityUserModel,
    IdentityUserRoleModel,
)


class TestIdentityTenantModel:
    """Tests for IdentityTenantModel."""

    def test_instantiation(self):
        tenant = IdentityTenantModel(id=1, name="Acme Corp", plan="pro", status="active")
        assert tenant.id == 1
        assert tenant.name == "Acme Corp"
        assert tenant.plan == "pro"
        assert tenant.status == "active"

    def test_defaults(self):
        _ = IdentityTenantModel(name="Beta Inc")
        col = IdentityTenantModel.__table__.columns["is_deleted"]
        assert col.default.arg is False

    def test_settings_default(self):
        _ = IdentityTenantModel(name="Gamma")
        col = IdentityTenantModel.__table__.columns["settings"]
        assert callable(col.default.arg)

    def test_to_dict(self):
        now = datetime.now()
        tenant = IdentityTenantModel(
            id=5,
            name="Delta",
            plan="enterprise",
            status="active",
            settings={"sso": True},
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            created_by=1,
            updated_by=2,
            created_at=now,
            updated_at=now,
        )
        d = tenant.to_dict()
        assert d["id"] == 5
        assert d["name"] == "Delta"
        assert d["plan"] == "enterprise"
        assert d["status"] == "active"
        assert d["settings"] == {"sso": True}
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert d["deleted_by"] is None
        assert d["created_by"] == 1
        assert d["updated_by"] == 2
        assert isinstance(d["created_at"], str)
        assert isinstance(d["updated_at"], str)

    def test_no_tenant_id(self):
        """IdentityTenantModel must not have a tenant_id column."""
        assert "tenant_id" not in [c.name for c in IdentityTenantModel.__table__.columns]

    def test_soft_delete_fields(self):
        cols = {c.name for c in IdentityTenantModel.__table__.columns}
        assert "is_deleted" in cols
        assert "deleted_at" in cols
        assert "deleted_by" in cols

    def test_audit_fields(self):
        cols = {c.name for c in IdentityTenantModel.__table__.columns}
        assert "created_by" in cols
        assert "updated_by" in cols
        assert "created_at" in cols
        assert "updated_at" in cols


class TestIdentityOrganizationModel:
    """Tests for IdentityOrganizationModel."""

    def test_instantiation(self):
        org = IdentityOrganizationModel(id=1, tenant_id=10, name="Org One", slug="org-one")
        assert org.id == 1
        assert org.tenant_id == 10
        assert org.name == "Org One"
        assert org.slug == "org-one"
        assert org.__table__.columns["is_active"].default.arg is True

    def test_defaults(self):
        org = IdentityOrganizationModel(tenant_id=1, name="Org Two", slug="org-two")
        assert org.__table__.columns["is_deleted"].default.arg is False
        assert org.__table__.columns["is_active"].default.arg is True
        assert org.__table__.columns["created_by"].default.arg == 0
        assert org.__table__.columns["updated_by"].default.arg == 0

    def test_to_dict(self):
        now = datetime.now()
        org = IdentityOrganizationModel(
            id=2,
            tenant_id=5,
            name="Acme Org",
            slug="acme-org",
            description="A test org",
            is_active=True,
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            created_by=3,
            updated_by=4,
            created_at=now,
            updated_at=now,
        )
        d = org.to_dict()
        assert d["id"] == 2
        assert d["tenant_id"] == 5
        assert d["name"] == "Acme Org"
        assert d["slug"] == "acme-org"
        assert d["description"] == "A test org"
        assert d["is_active"] is True
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert d["deleted_by"] is None
        assert d["created_by"] == 3
        assert d["updated_by"] == 4
        assert isinstance(d["created_at"], str)

    def test_has_tenant_id(self):
        col_names = [c.name for c in IdentityOrganizationModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_unique_constraint(self):
        constraint_names = [getattr(c, "name", None) for c in IdentityOrganizationModel.__table__.constraints]
        assert "uq_identity_org_tenant_slug" in constraint_names

    def test_soft_delete_and_audit_fields(self):
        cols = {c.name for c in IdentityOrganizationModel.__table__.columns}
        for f in ("is_deleted", "deleted_at", "deleted_by", "created_by", "updated_by"):
            assert f in cols, f"{f} missing from IdentityOrganizationModel"


class TestIdentityDepartmentModel:
    """Tests for IdentityDepartmentModel."""

    def test_instantiation(self):
        dept = IdentityDepartmentModel(id=1, tenant_id=1, organization_id=10, name="Engineering")
        assert dept.id == 1
        assert dept.tenant_id == 1
        assert dept.organization_id == 10
        assert dept.name == "Engineering"

    def test_defaults(self):
        dept = IdentityDepartmentModel(tenant_id=1, organization_id=1, name="Sales")
        assert dept.__table__.columns["is_deleted"].default.arg is False

    def test_parent_hierarchy(self):
        _ = IdentityDepartmentModel(id=1, tenant_id=1, organization_id=1, name="Engineering", parent_id=None)
        parent_col = IdentityDepartmentModel.__table__.columns["parent_id"]
        assert parent_col.nullable is True
        # parent_id is a simple self-referential FK (not composite)
        assert len(parent_col.foreign_keys) == 1
        fk = next(iter(parent_col.foreign_keys))
        assert fk.target_fullname == "identity_departments.id"

    def test_to_dict(self):
        now = datetime.now()
        dept = IdentityDepartmentModel(
            id=3,
            tenant_id=7,
            organization_id=1,
            name="QA",
            description="Quality assurance",
            parent_id=None,
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            created_by=1,
            updated_by=2,
            created_at=now,
            updated_at=now,
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
        assert d["deleted_by"] is None
        assert d["created_by"] == 1
        assert d["updated_by"] == 2
        assert isinstance(d["created_at"], str)

    def test_has_tenant_id(self):
        col_names = [c.name for c in IdentityDepartmentModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_soft_delete_and_audit_fields(self):
        cols = {c.name for c in IdentityDepartmentModel.__table__.columns}
        for f in ("is_deleted", "deleted_at", "deleted_by", "created_by", "updated_by"):
            assert f in cols, f"{f} missing from IdentityDepartmentModel"


class TestIdentityUserModel:
    """Tests for IdentityUserModel."""

    def test_instantiation(self):
        user = IdentityUserModel(
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
        user = IdentityUserModel(tenant_id=1, username="bob", email="bob@example.com")
        assert user.__table__.columns["is_deleted"].default.arg is False
        assert user.__table__.columns["status"].default.arg == "active"

    def test_to_dict(self):
        now = datetime.now()
        user = IdentityUserModel(
            id=2,
            tenant_id=10,
            username="carol",
            email="carol@example.com",
            password_hash="secret_hash_value",
            full_name="Carol Jones",
            bio="Bio here",
            status="active",
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            created_by=1,
            updated_by=2,
            created_at=now,
            updated_at=now,
        )
        d = user.to_dict()
        assert d["id"] == 2
        assert d["tenant_id"] == 10
        assert d["username"] == "carol"
        assert d["email"] == "carol@example.com"
        assert d["full_name"] == "Carol Jones"
        assert d["bio"] == "Bio here"
        assert d["status"] == "active"
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert d["deleted_by"] is None
        assert d["created_by"] == 1
        assert d["updated_by"] == 2
        assert isinstance(d["created_at"], str)
        # password_hash must not appear in serialized output (credential field)
        assert "password_hash" not in d, "password_hash must not appear in to_dict() output"

    def test_password_hash_absent_when_set(self):
        """Verify password_hash is excluded from to_dict() even when the field has a value."""
        user = IdentityUserModel(
            id=99,
            tenant_id=1,
            username="secret_user",
            email="secret@example.com",
            password_hash="super_secret_hash",
        )
        d = user.to_dict()
        assert "password_hash" not in d
        assert d["username"] == "secret_user"

    def test_has_tenant_id(self):
        col_names = [c.name for c in IdentityUserModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_unique_constraints(self):
        constraint_names = [getattr(c, "name", None) for c in IdentityUserModel.__table__.constraints]
        assert "uq_identity_user_tenant_username" in constraint_names
        assert "uq_identity_user_tenant_email" in constraint_names

    def test_soft_delete_and_audit_fields(self):
        cols = {c.name for c in IdentityUserModel.__table__.columns}
        for f in ("is_deleted", "deleted_at", "deleted_by", "created_by", "updated_by"):
            assert f in cols, f"{f} missing from IdentityUserModel"


class TestIdentityRoleModel:
    """Tests for IdentityRoleModel."""

    def test_instantiation(self):
        role = IdentityRoleModel(id=1, tenant_id=3, name="admin", display_name="Administrator")
        assert role.id == 1
        assert role.tenant_id == 3
        assert role.name == "admin"
        assert role.display_name == "Administrator"

    def test_defaults(self):
        role = IdentityRoleModel(tenant_id=1, name="viewer", display_name="Viewer")
        assert role.__table__.columns["is_deleted"].default.arg is False
        assert role.__table__.columns["is_system"].default.arg is False
        assert role.__table__.columns["priority"].default.arg == 0

    def test_to_dict(self):
        now = datetime.now()
        role = IdentityRoleModel(
            id=4,
            tenant_id=2,
            name="editor",
            display_name="Editor",
            description="Can edit content",
            is_system=False,
            priority=10,
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            created_by=1,
            updated_by=2,
            created_at=now,
            updated_at=now,
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
        assert d["deleted_by"] is None
        assert d["created_by"] == 1
        assert d["updated_by"] == 2
        assert isinstance(d["created_at"], str)

    def test_has_tenant_id(self):
        col_names = [c.name for c in IdentityRoleModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_unique_constraint(self):
        constraint_names = [getattr(c, "name", None) for c in IdentityRoleModel.__table__.constraints]
        assert "uq_identity_role_tenant_name" in constraint_names

    def test_soft_delete_and_audit_fields(self):
        cols = {c.name for c in IdentityRoleModel.__table__.columns}
        for f in ("is_deleted", "deleted_at", "deleted_by", "created_by", "updated_by"):
            assert f in cols, f"{f} missing from IdentityRoleModel"


class TestIdentityPermissionModel:
    """Tests for IdentityPermissionModel."""

    def test_instantiation(self):
        perm = IdentityPermissionModel(
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
        perm = IdentityPermissionModel(name="users.write", display_name="Write Users", category="users")
        assert perm.__table__.columns["is_deleted"].default.arg is False
        assert perm.__table__.columns["display_name"].default.arg == ""
        assert perm.__table__.columns["category"].default.arg == ""
        desc_col = perm.__table__.columns["description"]
        assert desc_col.nullable is True
        assert desc_col.default is None

    def test_to_dict(self):
        now = datetime.now()
        perm = IdentityPermissionModel(
            id=5,
            name="reports.export",
            display_name="Export Reports",
            category="reports",
            description="Can export reports",
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            created_by=1,
            updated_by=2,
            created_at=now,
            updated_at=now,
        )
        d = perm.to_dict()
        assert d["id"] == 5
        assert d["name"] == "reports.export"
        assert d["display_name"] == "Export Reports"
        assert d["category"] == "reports"
        assert d["description"] == "Can export reports"
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert d["deleted_by"] is None
        assert d["created_by"] == 1
        assert d["updated_by"] == 2
        assert isinstance(d["created_at"], str)

    def test_no_tenant_id(self):
        col_names = [c.name for c in IdentityPermissionModel.__table__.columns]
        assert "tenant_id" not in col_names

    def test_soft_delete_and_audit_fields(self):
        cols = {c.name for c in IdentityPermissionModel.__table__.columns}
        for f in ("is_deleted", "deleted_at", "deleted_by", "created_by", "updated_by"):
            assert f in cols, f"{f} missing from IdentityPermissionModel"


class TestIdentityRolePermissionModel:
    """Tests for IdentityRolePermissionModel."""

    def test_instantiation(self):
        rp = IdentityRolePermissionModel(id=1, role_id=10, permission_id=5)
        assert rp.id == 1
        assert rp.role_id == 10
        assert rp.permission_id == 5

    def test_to_dict(self):
        now = datetime.now()
        rp = IdentityRolePermissionModel(
            id=2,
            role_id=20,
            permission_id=15,
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            created_by=1,
            updated_by=2,
            created_at=now,
            updated_at=now,
        )
        d = rp.to_dict()
        assert d["id"] == 2
        assert d["role_id"] == 20
        assert d["permission_id"] == 15
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert d["deleted_by"] is None
        assert d["created_by"] == 1
        assert d["updated_by"] == 2

    def test_unique_constraint(self):
        constraint_names = [getattr(c, "name", None) for c in IdentityRolePermissionModel.__table__.constraints]
        assert "uq_identity_role_permission" in constraint_names

    def test_relationships(self):
        assert hasattr(IdentityRolePermissionModel, "role")
        assert hasattr(IdentityRolePermissionModel, "permission")

    def test_soft_delete_and_audit_fields(self):
        cols = {c.name for c in IdentityRolePermissionModel.__table__.columns}
        for f in ("is_deleted", "deleted_at", "deleted_by", "created_by", "updated_by"):
            assert f in cols, f"{f} missing from IdentityRolePermissionModel"


class TestIdentityUserRoleModel:
    """Tests for IdentityUserRoleModel."""

    def test_instantiation(self):
        ur = IdentityUserRoleModel(id=1, user_id=5, role_id=10, tenant_id=3, granted_by=1)
        assert ur.id == 1
        assert ur.user_id == 5
        assert ur.role_id == 10
        assert ur.tenant_id == 3
        assert ur.granted_by == 1

    def test_defaults(self):
        ur = IdentityUserRoleModel(user_id=1, role_id=1, tenant_id=1, granted_by=1)
        assert ur.__table__.columns["is_deleted"].default.arg is False

    def test_to_dict(self):
        now = datetime.now()
        ur = IdentityUserRoleModel(
            id=7,
            user_id=100,
            role_id=20,
            tenant_id=50,
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            granted_by=3,
            granted_at=now,
            created_by=1,
            updated_by=2,
            created_at=now,
            updated_at=now,
        )
        d = ur.to_dict()
        assert d["id"] == 7
        assert d["user_id"] == 100
        assert d["role_id"] == 20
        assert d["tenant_id"] == 50
        assert d["is_deleted"] is False
        assert d["deleted_at"] is None
        assert d["deleted_by"] is None
        assert d["granted_by"] == 3
        assert isinstance(d["granted_at"], str)
        assert d["created_by"] == 1
        assert d["updated_by"] == 2

    def test_has_tenant_id(self):
        col_names = [c.name for c in IdentityUserRoleModel.__table__.columns]
        assert "tenant_id" in col_names

    def test_unique_constraint(self):
        constraint_names = [getattr(c, "name", None) for c in IdentityUserRoleModel.__table__.constraints]
        assert "uq_identity_user_role_tenant" in constraint_names

    def test_soft_delete_and_audit_fields(self):
        cols = {c.name for c in IdentityUserRoleModel.__table__.columns}
        for f in ("is_deleted", "deleted_at", "deleted_by", "created_by", "updated_by"):
            assert f in cols, f"{f} missing from IdentityUserRoleModel"


class TestRelationships:
    """Tests for cross-model relationship resolution."""

    def test_department_organization_relationship(self):
        cols = {c.name for c in IdentityDepartmentModel.__table__.columns}
        rels = {r.key: r for r in IdentityDepartmentModel.__mapper__.relationships}
        assert "organization" in rels
        assert "organization_id" in cols

    def test_department_self_referential(self):
        rels = {r.key: r for r in IdentityDepartmentModel.__mapper__.relationships}
        assert "parent" in rels
        assert "children" in rels

    def test_role_permissions_relationship(self):
        rels = {r.key: r for r in IdentityRoleModel.__mapper__.relationships}
        assert "permissions" in rels
        assert "user_assignments" in rels

    def test_permission_roles_relationship(self):
        rels = {r.key: r for r in IdentityPermissionModel.__mapper__.relationships}
        assert "roles" in rels

    def test_role_permission_junction_back_populates(self):
        rels = {r.key: r for r in IdentityRolePermissionModel.__mapper__.relationships}
        assert "role" in rels
        assert "permission" in rels

    def test_user_role_relationships(self):
        ur_rels = {r.key: r for r in IdentityUserRoleModel.__mapper__.relationships}
        assert "role" in ur_rels

    def test_userrole_role_back_populates(self):
        role_rels = {r.key: r for r in IdentityRoleModel.__mapper__.relationships}
        assert "user_assignments" in role_rels
        ur_rels = {r.key: r for r in IdentityUserRoleModel.__mapper__.relationships}
        assert ur_rels["role"].back_populates == "user_assignments"
