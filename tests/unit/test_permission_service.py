"""Unit tests for src/services/permission_service.py."""

import pytest

from services.permission_service import (
    ROLE_PERMISSIONS,
    check_permission,
    has_permission,
)


class TestRolePermissions:
    def test_owner_star_allows_any(self):
        assert has_permission("owner", "anyresource", "anyaction") is True

    def test_admin_exact_match(self):
        assert has_permission("admin", "customer", "read") is True

    def test_admin_no_delete_for_viewer(self):
        assert has_permission("viewer", "customer", "delete") is False

    def test_resource_wildcard(self):
        # support role has ticket:*, so ticket:delete should be allowed
        assert has_permission("support", "ticket", "delete") is True

    def test_unknown_role_returns_false(self):
        assert has_permission("nonexistent", "customer", "read") is False

    def test_member_read_write(self):
        assert has_permission("member", "customer", "read") is True

    def test_sales_opportunity_crud(self):
        assert has_permission("sales", "opportunity", "update") is True

    def test_manager_no_delete(self):
        assert has_permission("manager", "customer", "delete") is False

    def test_check_permission_static(self):
        # Static stub always returns False (no DB session available)
        assert check_permission(1, 1, "customer", "read") is False


class TestRolePermissionsCompleteness:
    def test_owner_has_star(self):
        assert "*" in ROLE_PERMISSIONS.get("owner", [])

    def test_all_roles_are_defined(self):
        expected_roles = {"owner", "admin", "manager", "sales", "support", "viewer", "member"}
        assert set(ROLE_PERMISSIONS.keys()) == expected_roles

    def test_admin_has_all_defined_permissions(self):
        admin_perms = ROLE_PERMISSIONS["admin"]
        assert "customer:read" in admin_perms
        assert "ticket:delete" in admin_perms
        assert "admin:all" in admin_perms

    def test_viewer_readonly(self):
        viewer_perms = ROLE_PERMISSIONS["viewer"]
        assert all(":read" in p for p in viewer_perms)