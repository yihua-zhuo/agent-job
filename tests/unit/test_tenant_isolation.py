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

    @pytest.fixture
    def tenant_service(self, mock_db_session):
        """创建租户服务实例"""
        return TenantService(mock_db_session)

    async def test_user_isolation(self, tenant_service):
        """测试用户数据隔离"""
        data_service = DataIsolationService()

        # 创建两个租户
        tenant_a_resp = await tenant_service.create_tenant(
            name="Company A", plan="pro", admin_email="admin@a.com"
        )
        tenant_a = tenant_a_resp.data
        tenant_b_resp = await tenant_service.create_tenant(
            name="Company B", plan="basic", admin_email="admin@b.com"
        )
        tenant_b = tenant_b_resp.data

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

    @pytest.fixture
    def service(self, mock_db_session):
        """创建租户服务实例"""
        return TenantService(mock_db_session)

    async def test_create_and_get_tenant(self, service):
        """测试创建和获取租户"""
        tenant_resp = await service.create_tenant(
            name="Test Corp", plan="enterprise", admin_email="test@corp.com"
        )
        tenant = tenant_resp.data

        assert tenant["name"] == "Test Corp"
        assert tenant["plan"] == "enterprise"
        assert tenant["status"] == "active"

        retrieved_resp = await service.get_tenant(tenant["id"])
        retrieved = retrieved_resp.data
        assert retrieved["id"] == tenant["id"]

    async def test_update_tenant(self, service):
        """测试更新租户"""
        tenant_resp = await service.create_tenant(
            name="Old Name", plan="basic", admin_email="old@corp.com"
        )
        tenant = tenant_resp.data

        updated_resp = await service.update_tenant(tenant["id"], name="New Name", plan="pro")
        updated = updated_resp.data
        assert updated["name"] == "New Name"
        assert updated["plan"] == "pro"

    async def test_suspend_tenant(self, service):
        """测试暂停租户"""
        tenant_resp = await service.create_tenant(
            name="Suspend Me", plan="basic", admin_email="suspend@corp.com"
        )
        tenant = tenant_resp.data

        await service.suspend_tenant(tenant["id"])
        suspended_resp = await service.get_tenant(tenant["id"])
        suspended = suspended_resp.data
        assert suspended["status"] == "suspended"

    async def test_delete_tenant(self, service):
        """测试删除租户（软删除）"""
        tenant_resp = await service.create_tenant(
            name="Delete Me", plan="basic", admin_email="delete@corp.com"
        )
        tenant = tenant_resp.data

        await service.delete_tenant(tenant["id"])
        # 软删除后再次获取应返回 NOT_FOUND
        deleted_resp = await service.get_tenant(tenant["id"])
        assert deleted_resp.data is None
        assert "deleted" in deleted_resp.message.lower()

    async def test_list_tenants(self, service):
        """测试租户列表"""
        await service.create_tenant(name="T1", plan="basic", admin_email="t1@t.com")
        await service.create_tenant(name="T2", plan="pro", admin_email="t2@t.com")

        result_resp = await service.list_tenants()
        result = result_resp.data
        assert result["total"] >= 2
        assert len(result["items"]) >= 2

    async def test_get_tenant_usage(self, service):
        """测试获取租户使用量"""
        tenant_resp = await service.create_tenant(
            name="Usage Test", plan="basic", admin_email="usage@t.com"
        )
        tenant = tenant_resp.data

        usage_resp = await service.get_tenant_usage(tenant["id"])
        usage = usage_resp.data
        assert "user_count" in usage
        assert "storage_used" in usage
        assert "api_calls" in usage