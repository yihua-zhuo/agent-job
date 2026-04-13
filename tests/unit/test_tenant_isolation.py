"""租户隔离测试"""
import pytest
from src.services.tenant_service import TenantService


class TestTenantService:
    """测试租户服务"""

    def test_create_and_get_tenant(self):
        """测试创建和获取租户"""
        service = TenantService()
        result = service.create_tenant(
            name="Test Corp", plan="enterprise", admin_email="test@corp.com"
        )
        assert bool(result) is True
        tenant = result.data
        assert tenant["name"] == "Test Corp"
        assert tenant["plan"] == "enterprise"
        assert tenant["status"] == "active"

        retrieved = service.get_tenant(tenant["id"])
        assert bool(retrieved) is True
        assert retrieved.data["id"] == tenant["id"]

    def test_update_tenant(self):
        """测试更新租户"""
        service = TenantService()
        result = service.create_tenant(
            name="Old Name", plan="basic", admin_email="old@corp.com"
        )
        tenant_id = result.data["id"]

        updated = service.update_tenant(tenant_id, name="New Name", plan="pro")
        assert bool(updated) is True
        assert updated.data["name"] == "New Name"
        assert updated.data["plan"] == "pro"

    def test_suspend_tenant(self):
        """测试暂停租户"""
        service = TenantService()
        result = service.create_tenant(
            name="Suspend Me", plan="basic", admin_email="suspend@corp.com"
        )
        tenant_id = result.data["id"]

        suspended = service.suspend_tenant(tenant_id)
        assert bool(suspended) is True

        retrieved = service.get_tenant(tenant_id)
        assert bool(retrieved) is True
        assert retrieved.data["status"] == "suspended"

    def test_list_tenants(self):
        """测试租户列表"""
        service = TenantService()
        service.create_tenant(name="T1", plan="basic", admin_email="t1@t.com")
        service.create_tenant(name="T2", plan="pro", admin_email="t2@t.com")

        result = service.list_tenants()
        assert bool(result) is True
        assert result.data.total >= 2
        assert len(result.data.items) >= 2

    def test_get_tenant_usage(self):
        """测试获取租户使用量"""
        service = TenantService()
        result = service.create_tenant(
            name="Usage Test", plan="basic", admin_email="usage@t.com"
        )
        tenant_id = result.data["id"]

        usage = service.get_tenant_usage(tenant_id)
        assert bool(usage) is True
        assert "user_count" in usage.data
        assert "storage_used" in usage.data
        assert "api_calls" in usage.data


class TestDataIsolation:
    """测试数据隔离"""

    def test_customer_isolation_between_tenants(self):
        """测试两个租户间的客户数据隔离"""
        from src.services.customer_service import CustomerService

        cs_a = CustomerService()
        cs_b = CustomerService()

        # 租户A创建客户
        r1 = cs_a.create_customer({
            "name": "Customer A", "email": "a@a.com", "owner_id": 1
        }, tenant_id=1)
        assert bool(r1) is True
        assert r1.data["tenant_id"] == 1

        # 租户B创建客户
        r2 = cs_b.create_customer({
            "name": "Customer B", "email": "b@b.com", "owner_id": 1
        }, tenant_id=2)
        assert bool(r2) is True
        assert r2.data["tenant_id"] == 2

        # 各自只能看到自己的客户
        list_a = cs_a.list_customers(tenant_id=1)
        assert bool(list_a) is True
        names_a = [c["name"] for c in list_a.data.items]
        assert "Customer A" in names_a
        assert "Customer B" not in names_a

        list_b = cs_b.list_customers(tenant_id=2)
        assert bool(list_b) is True
        names_b = [c["name"] for c in list_b.data.items]
        assert "Customer B" in names_b
        assert "Customer A" not in names_b
