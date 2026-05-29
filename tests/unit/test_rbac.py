"""Unit tests for RBACService static methods and Permission value object.

Async DB-backed methods are tested via integration tests
(tests/integration/test_rbac_integration.py) which use a real PostgreSQL
database. Unit tests here focus on the static helpers that don't need a
real DB.
"""

from __future__ import annotations

from src.services.rbac_service import RBACService


class TestRBACServiceStatic:
    """Tests for static RBACService methods (no DB needed)."""

    def test_has_permission_admin_has_all(self):
        assert RBACService.has_permission("admin", "admin:all") is True
        assert RBACService.has_permission("admin", "user:manage") is True
        assert RBACService.has_permission("admin", "customer:create") is True
        assert RBACService.has_permission("admin", "customer:delete") is True
        assert RBACService.has_permission("admin", "opportunity:create") is True
        assert RBACService.has_permission("admin", "opportunity:delete") is True

    def test_has_permission_manager_limited(self):
        assert RBACService.has_permission("manager", "customer:read") is True
        assert RBACService.has_permission("manager", "opportunity:read") is True
        assert RBACService.has_permission("manager", "opportunity:create") is True
        assert RBACService.has_permission("manager", "opportunity:update") is True
        assert RBACService.has_permission("manager", "customer:delete") is False
        assert RBACService.has_permission("manager", "opportunity:delete") is False

    def test_has_permission_sales_customer_ops(self):
        assert RBACService.has_permission("sales", "customer:read") is True
        assert RBACService.has_permission("sales", "customer:create") is True
        assert RBACService.has_permission("sales", "customer:update") is True
        assert RBACService.has_permission("sales", "opportunity:read") is True
        assert RBACService.has_permission("sales", "opportunity:create") is True
        assert RBACService.has_permission("sales", "opportunity:update") is True
        assert RBACService.has_permission("sales", "customer:delete") is False
        assert RBACService.has_permission("sales", "opportunity:delete") is False

    def test_has_permission_support_ticket_ops(self):
        assert RBACService.has_permission("support", "customer:read") is True
        assert RBACService.has_permission("support", "opportunity:read") is True
        assert RBACService.has_permission("support", "customer:create") is False
        assert RBACService.has_permission("support", "opportunity:delete") is False

    def test_has_permission_viewer_read_only(self):
        assert RBACService.has_permission("viewer", "customer:read") is True
        assert RBACService.has_permission("viewer", "opportunity:read") is True
        assert RBACService.has_permission("viewer", "customer:create") is False
        assert RBACService.has_permission("viewer", "opportunity:update") is False

    def test_has_permission_unknown_role(self):
        assert RBACService.has_permission("unknown_role", "customer:read") is False
        assert RBACService.has_permission("unknown_role", "admin:all") is False
        assert RBACService.has_permission("", "customer:read") is False

    def test_has_permission_not_in_role(self):
        assert RBACService.has_permission("viewer", "admin:all") is False
        assert RBACService.has_permission("support", "user:manage") is False

    def test_get_role_permissions_admin(self):
        perms = RBACService.get_role_permissions("admin")
        assert "admin:all" in perms
        assert "user:manage" in perms
        assert "user:read" in perms
        assert "customer:create" in perms
        assert "customer:read" in perms
        assert "customer:update" in perms
        assert "customer:delete" in perms
        assert "opportunity:create" in perms
        assert "opportunity:read" in perms
        assert "opportunity:update" in perms
        assert "opportunity:delete" in perms
        assert "ticket:read" in perms
        assert "ticket:create" in perms
        assert "ticket:update" in perms
        assert "ticket:delete" in perms

    def test_get_role_permissions_manager(self):
        perms = RBACService.get_role_permissions("manager")
        assert "customer:read" in perms
        assert "customer:update" in perms
        assert "opportunity:read" in perms
        assert "opportunity:create" in perms
        assert "opportunity:update" in perms
        assert "ticket:read" in perms
        assert "ticket:create" in perms
        assert "ticket:update" in perms
        assert "user:read" in perms
        assert "customer:delete" not in perms
        assert "opportunity:delete" not in perms
        assert "ticket:delete" not in perms

    def test_get_role_permissions_sales(self):
        perms = RBACService.get_role_permissions("sales")
        assert "customer:read" in perms
        assert "customer:create" in perms
        assert "customer:update" in perms
        assert "opportunity:read" in perms
        assert "opportunity:create" in perms
        assert "opportunity:update" in perms
        assert "customer:delete" not in perms
        assert "opportunity:delete" not in perms
        assert "ticket:delete" not in perms

    def test_get_role_permissions_support(self):
        perms = RBACService.get_role_permissions("support")
        assert "customer:read" in perms
        assert "opportunity:read" in perms
        assert "ticket:read" in perms
        assert "ticket:create" in perms
        assert "ticket:update" in perms
        assert len(perms) == 5

    def test_get_role_permissions_viewer(self):
        perms = RBACService.get_role_permissions("viewer")
        assert "customer:read" in perms
        assert "opportunity:read" in perms
        assert "ticket:read" in perms
        assert len(perms) == 3

    def test_get_role_permissions_unknown(self):
        assert RBACService.get_role_permissions("nonexistent") == []
        assert RBACService.get_role_permissions("") == []
        assert RBACService.get_role_permissions("ADMIN") == []

    def test_check_permission_by_value_valid(self):
        assert RBACService.check_permission_by_value("admin", "admin:all") is True
        assert RBACService.check_permission_by_value("admin", "user:manage") is True
        assert RBACService.check_permission_by_value("admin", "customer:create") is True
        assert RBACService.check_permission_by_value("sales", "customer:read") is True
        assert RBACService.check_permission_by_value("sales", "opportunity:create") is True

    def test_check_permission_by_value_invalid(self):
        assert RBACService.check_permission_by_value("admin", "invalid:permission") is False
        assert RBACService.check_permission_by_value("admin", "not a permission") is False
        assert RBACService.check_permission_by_value("admin", "") is False

    def test_check_permission_by_value_unknown_role(self):
        assert RBACService.check_permission_by_value("unknown", "customer:read") is False

    def test_check_permission_by_value_case_sensitive(self):
        assert RBACService.check_permission_by_value("admin", "CUSTOMER:READ") is False
        assert RBACService.check_permission_by_value("Admin", "admin:all") is False


class TestPermissionValueObject:
    """Tests for Permission value object."""

    def test_permission_equality_by_value(self):
        from src.services.rbac_service import Permission

        p1 = Permission("customer:create")
        p2 = Permission("customer:create")
        assert p1 == p2
        assert hash(p1) == hash(p2)

    def test_permission_inequality(self):
        from src.services.rbac_service import Permission

        p1 = Permission("customer:create")
        p2 = Permission("customer:read")
        assert p1 != p2

    def test_permission_comparable_with_string(self):
        from src.services.rbac_service import Permission

        p = Permission("customer:create")
        assert p == "customer:create"
        assert p != "customer:read"

    def test_permission_auto_registered_as_class_attribute(self):
        from src.services.rbac_service import Permission

        assert hasattr(Permission, "CUSTOMER_CREATE")
        assert hasattr(Permission, "ADMIN_ALL")

    def test_permission_repr(self):
        from src.services.rbac_service import Permission

        p = Permission("customer:create")
        assert repr(p) == "Permission('customer:create')"

    def test_permission_duplicate_instantiation_safe(self):
        from src.services.rbac_service import Permission

        p1 = Permission("customer:create")
        p2 = Permission("customer:create")
        assert p2.value == "customer:create"
        assert p1 == p2
