"""租户隔离测试"""
import pytest
from src.middleware.tenant import TenantMiddleware
from src.services.tenant_service import TenantService
from src.services.data_isolation import DataIsolationService
from src.utils.tenant_context import TenantContext


class TestCustomerIsolation:
    """测试客户数据隔离"""

    def test_customer_isolation(self):
        """测试客户数据隔离"""
        service = DataIsolationService()

        # 创建两个租户的客户数据
        result_a = service.verify_tenant_isolation(tenant_id=1)
        result_b = service.verify_tenant_isolation(tenant_id=2)

        # 验证两个租户的数据是隔离的
        assert result_a["isolated"] is True
        assert result_b["isolated"] is True
        assert result_a["tenant_id"] != result_b["tenant_id"]


class TestUserIsolation:
    """测试用户数据隔离"""

    def test_user_isolation(self):
        """测试用户数据隔离"""
        tenant_service = TenantService()
        data_service = DataIsolationService()

        # 创建两个租户
        tenant_a = tenant_service.create_tenant(
            name="Company A", plan="pro", admin_email="admin@a.com"
        )
        tenant_b = tenant_service.create_tenant(
            name="Company B", plan="basic", admin_email="admin@b.com"
        )

        # 验证用户数据隔离
        isolation_a = data_service.verify_tenant_isolation(tenant_a["id"])
        isolation_b = data_service.verify_tenant_isolation(tenant_b["id"])

        assert isolation_a["isolated"] is True
        assert isolation_b["isolated"] is True


class TestCrossTenantBlocked:
    """测试跨租户访问被阻止"""

    def test_cross_tenant_blocked(self):
        """测试跨租户访问被阻止"""
        service = DataIsolationService()

        # 测试跨租户访问被正确阻止
        access_blocked = service.test_cross_tenant_access(
            tenant_a_id=10, tenant_b_id=20
        )

        assert access_blocked is True

    def test_middleware_requires_tenant(self):
        """测试中间件在未设置租户时正确拒绝"""
        middleware = TenantMiddleware()

        @middleware.require_tenant
        def protected_function():
            return "success"

        # 未设置租户ID时应抛出异常
        with pytest.raises(Exception) as exc_info:
            protected_function()

        assert "Tenant not selected" in str(exc_info.value) or exc_info.value.code == 3001

    def test_middleware_allows_valid_tenant(self):
        """测试中间件在设置有效租户时允许访问"""
        middleware = TenantMiddleware()
        middleware.set_tenant_id(42)

        @middleware.require_tenant
        def protected_function():
            return "success"

        result = protected_function()
        assert result == "success"
        assert middleware.get_tenant_id() == 42


class TestTenantContext:
    """测试租户上下文"""

    def test_set_and_get_tenant_id(self):
        """测试设置和获取租户ID"""
        TenantContext.set_tenant_id(123)
        assert TenantContext.get_tenant_id() == 123
        TenantContext.clear()

    def test_clear_tenant_id(self):
        """测试清除租户ID"""
        TenantContext.set_tenant_id(456)
        TenantContext.clear()
        assert TenantContext.get_tenant_id() is None


class TestTenantService:
    """测试租户服务"""

    def test_create_and_get_tenant(self):
        """测试创建和获取租户"""
        service = TenantService()
        tenant = service.create_tenant(
            name="Test Corp", plan="enterprise", admin_email="test@corp.com"
        )

        assert tenant["name"] == "Test Corp"
        assert tenant["plan"] == "enterprise"
        assert tenant["status"] == "active"

        retrieved = service.get_tenant(tenant["id"])
        assert retrieved["id"] == tenant["id"]

    def test_update_tenant(self):
        """测试更新租户"""
        service = TenantService()
        tenant = service.create_tenant(
            name="Old Name", plan="basic", admin_email="old@corp.com"
        )

        updated = service.update_tenant(tenant["id"], name="New Name", plan="pro")
        assert updated["name"] == "New Name"
        assert updated["plan"] == "pro"

    def test_suspend_tenant(self):
        """测试暂停租户"""
        service = TenantService()
        tenant = service.create_tenant(
            name="Suspend Me", plan="basic", admin_email="suspend@corp.com"
        )

        service.suspend_tenant(tenant["id"])
        suspended = service.get_tenant(tenant["id"])
        assert suspended["status"] == "suspended"

    def test_delete_tenant(self):
        """测试删除租户（软删除）"""
        service = TenantService()
        tenant = service.create_tenant(
            name="Delete Me", plan="basic", admin_email="delete@corp.com"
        )

        service.delete_tenant(tenant["id"])
        # 软删除后再次获取应抛出异常
        with pytest.raises(ValueError) as exc_info:
            service.get_tenant(tenant["id"])
        assert "deleted" in str(exc_info.value)

    def test_list_tenants(self):
        """测试租户列表"""
        service = TenantService()
        service.create_tenant(name="T1", plan="basic", admin_email="t1@t.com")
        service.create_tenant(name="T2", plan="pro", admin_email="t2@t.com")

        result = service.list_tenants()
        assert result["total"] >= 2
        assert len(result["items"]) >= 2

    def test_get_tenant_usage(self):
        """测试获取租户使用量"""
        service = TenantService()
        tenant = service.create_tenant(
            name="Usage Test", plan="basic", admin_email="usage@t.com"
        )

        usage = service.get_tenant_usage(tenant["id"])
        assert "user_count" in usage
        assert "storage_used" in usage
        assert "api_calls" in usage
