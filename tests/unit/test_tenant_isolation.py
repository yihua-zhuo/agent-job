"""租户隔离测试"""
import pytest

from src.middleware.tenant import TenantMiddleware
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


