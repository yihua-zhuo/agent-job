"""Unit tests for RBACService."""
import pytest
from src.services.rbac_service import RBACService, Permission


@pytest.fixture
def rbac_service():
    return RBACService(None)


class TestRBACService:
    """Tests for RBACService methods (lines 86-115)."""

    # ── has_permission ────────────────────────────────────────────────────────

    def test_has_permission_admin_has_all(self, rbac_service):
        """Admin role should have all permissions."""
        assert rbac_service.has_permission("admin", Permission.ADMIN_ALL) is True
        assert rbac_service.has_permission("admin", Permission.USER_MANAGE) is True
        assert rbac_service.has_permission("admin", Permission.CUSTOMER_CREATE) is True
        assert rbac_service.has_permission("admin", Permission.CUSTOMER_DELETE) is True
        assert rbac_service.has_permission("admin", Permission.OPPORTUNITY_CREATE) is True
        assert rbac_service.has_permission("admin", Permission.OPPORTUNITY_DELETE) is True

    def test_has_permission_manager_has_limited(self, rbac_service):
        """Manager role should have read permissions and limited write permissions."""
        assert rbac_service.has_permission("manager", Permission.CUSTOMER_READ) is True
        assert rbac_service.has_permission("manager", Permission.OPPORTUNITY_READ) is True
        assert rbac_service.has_permission("manager", Permission.OPPORTUNITY_CREATE) is True
        assert rbac_service.has_permission("manager", Permission.OPPORTUNITY_UPDATE) is True
        # Manager should NOT have delete permissions
        assert rbac_service.has_permission("manager", Permission.CUSTOMER_DELETE) is False
        assert rbac_service.has_permission("manager", Permission.OPPORTUNITY_DELETE) is False

    def test_has_permission_sales_has_customer_ops(self, rbac_service):
        """Sales role should have customer and opportunity create/read/update."""
        assert rbac_service.has_permission("sales", Permission.CUSTOMER_READ) is True
        assert rbac_service.has_permission("sales", Permission.CUSTOMER_CREATE) is True
        assert rbac_service.has_permission("sales", Permission.CUSTOMER_UPDATE) is True
        assert rbac_service.has_permission("sales", Permission.OPPORTUNITY_READ) is True
        assert rbac_service.has_permission("sales", Permission.OPPORTUNITY_CREATE) is True
        assert rbac_service.has_permission("sales", Permission.OPPORTUNITY_UPDATE) is True
        # Sales should NOT have delete permissions
        assert rbac_service.has_permission("sales", Permission.CUSTOMER_DELETE) is False
        assert rbac_service.has_permission("sales", Permission.OPPORTUNITY_DELETE) is False

    def test_has_permission_support_read_only(self, rbac_service):
        """Support role should have read-only permissions."""
        assert rbac_service.has_permission("support", Permission.CUSTOMER_READ) is True
        assert rbac_service.has_permission("support", Permission.OPPORTUNITY_READ) is True
        assert rbac_service.has_permission("support", Permission.CUSTOMER_CREATE) is False
        assert rbac_service.has_permission("support", Permission.OPPORTUNITY_DELETE) is False

    def test_has_permission_viewer_read_only(self, rbac_service):
        """Viewer role should have read-only permissions."""
        assert rbac_service.has_permission("viewer", Permission.CUSTOMER_READ) is True
        assert rbac_service.has_permission("viewer", Permission.OPPORTUNITY_READ) is True
        assert rbac_service.has_permission("viewer", Permission.CUSTOMER_CREATE) is False
        assert rbac_service.has_permission("viewer", Permission.OPPORTUNITY_UPDATE) is False

    def test_has_permission_unknown_role_returns_false(self, rbac_service):
        """Unknown role should return False for any permission."""
        assert rbac_service.has_permission("unknown_role", Permission.CUSTOMER_READ) is False
        assert rbac_service.has_permission("unknown_role", Permission.ADMIN_ALL) is False
        assert rbac_service.has_permission("", Permission.CUSTOMER_READ) is False

    def test_has_permission_not_in_role_permissions(self, rbac_service):
        """Permission not in role's list should return False."""
        # Viewer doesn't have ADMIN_ALL
        assert rbac_service.has_permission("viewer", Permission.ADMIN_ALL) is False
        # Support doesn't have USER_MANAGE
        assert rbac_service.has_permission("support", Permission.USER_MANAGE) is False

    # ── get_role_permissions ─────────────────────────────────────────────────

    def test_get_role_permissions_admin(self, rbac_service):
        """Admin should have all permissions."""
        perms = rbac_service.get_role_permissions("admin")
        assert Permission.ADMIN_ALL in perms
        assert Permission.USER_MANAGE in perms
        assert Permission.CUSTOMER_CREATE in perms
        assert Permission.CUSTOMER_READ in perms
        assert Permission.CUSTOMER_UPDATE in perms
        assert Permission.CUSTOMER_DELETE in perms
        assert Permission.OPPORTUNITY_CREATE in perms
        assert Permission.OPPORTUNITY_READ in perms
        assert Permission.OPPORTUNITY_UPDATE in perms
        assert Permission.OPPORTUNITY_DELETE in perms

    def test_get_role_permissions_manager(self, rbac_service):
        """Manager should have read + limited write permissions."""
        perms = rbac_service.get_role_permissions("manager")
        assert Permission.CUSTOMER_READ in perms
        assert Permission.OPPORTUNITY_READ in perms
        assert Permission.OPPORTUNITY_CREATE in perms
        assert Permission.OPPORTUNITY_UPDATE in perms
        assert Permission.CUSTOMER_DELETE not in perms
        assert Permission.OPPORTUNITY_DELETE not in perms

    def test_get_role_permissions_sales(self, rbac_service):
        """Sales should have customer and opportunity create/read/update."""
        perms = rbac_service.get_role_permissions("sales")
        assert Permission.CUSTOMER_READ in perms
        assert Permission.CUSTOMER_CREATE in perms
        assert Permission.CUSTOMER_UPDATE in perms
        assert Permission.OPPORTUNITY_READ in perms
        assert Permission.OPPORTUNITY_CREATE in perms
        assert Permission.OPPORTUNITY_UPDATE in perms
        assert Permission.CUSTOMER_DELETE not in perms
        assert Permission.OPPORTUNITY_DELETE not in perms

    def test_get_role_permissions_support(self, rbac_service):
        """Support should have read-only permissions."""
        perms = rbac_service.get_role_permissions("support")
        assert Permission.CUSTOMER_READ in perms
        assert Permission.OPPORTUNITY_READ in perms
        assert len(perms) == 5

    def test_get_role_permissions_viewer(self, rbac_service):
        """Viewer should have read-only permissions."""
        perms = rbac_service.get_role_permissions("viewer")
        assert Permission.CUSTOMER_READ in perms
        assert Permission.OPPORTUNITY_READ in perms
        assert len(perms) == 3

    def test_get_role_permissions_unknown_role_empty_list(self, rbac_service):
        """Unknown role should return empty list."""
        assert rbac_service.get_role_permissions("nonexistent") == []
        assert rbac_service.get_role_permissions("") == []
        assert rbac_service.get_role_permissions("ADMIN") == []  # case sensitive

    # ── check_permission_by_value ────────────────────────────────────────────

    def test_check_permission_by_value_valid_permission_string(self, rbac_service):
        """Valid permission strings should be checked correctly."""
        assert rbac_service.check_permission_by_value("admin", "admin:all") is True
        assert rbac_service.check_permission_by_value("admin", "user:manage") is True
        assert rbac_service.check_permission_by_value("admin", "customer:create") is True
        assert rbac_service.check_permission_by_value("sales", "customer:read") is True
        assert rbac_service.check_permission_by_value("sales", "opportunity:create") is True

    def test_check_permission_by_value_invalid_permission_string(self, rbac_service):
        """Invalid permission string format should return False."""
        assert rbac_service.check_permission_by_value("admin", "invalid:permission") is False
        assert rbac_service.check_permission_by_value("admin", "not a permission") is False
        assert rbac_service.check_permission_by_value("admin", "") is False

    def test_check_permission_by_value_unknown_role(self, rbac_service):
        """Unknown role should return False even with valid permission string."""
        assert rbac_service.check_permission_by_value("unknown", "customer:read") is False

    def test_check_permission_by_value_case_sensitive(self, rbac_service):
        """Permission value is case-sensitive."""
        assert rbac_service.check_permission_by_value("admin", "CUSTOMER:READ") is False
        assert rbac_service.check_permission_by_value("admin", "Customer:Read") is False

    def test_check_permission_by_value_role_case_sensitive(self, rbac_service):
        """Role name is case-sensitive."""
        assert rbac_service.check_permission_by_value("Admin", "admin:all") is False
        assert rbac_service.check_permission_by_value("ADMIN", "admin:all") is False
