"""Unit tests for TenantService and data isolation."""
import pytest
from services.tenant_service import TenantService


@pytest.mark.asyncio
class TestTenantService:
    async def test_create_and_get_tenant(self):
        service = TenantService()
        result = await service.create_tenant(
            name="Test Corp", plan="enterprise", admin_email="test@corp.com"
        )
        assert bool(result) is True
        tenant = result.data
        assert tenant["name"] == "Test Corp"
        assert tenant["plan"] == "enterprise"
        assert tenant["status"] == "active"

        retrieved = await service.get_tenant(tenant["id"])
        assert bool(retrieved) is True
        assert retrieved.data["id"] == tenant["id"]

    async def test_update_tenant(self):
        service = TenantService()
        result = await service.create_tenant(
            name="Old Name", plan="basic", admin_email="old@corp.com"
        )
        tenant_id = result.data["id"]

        updated = await service.update_tenant(tenant_id, name="New Name", plan="pro")
        assert bool(updated) is True
        assert updated.data["name"] == "New Name"
        assert updated.data["plan"] == "pro"

    async def test_suspend_tenant(self):
        service = TenantService()
        result = await service.create_tenant(
            name="Suspend Me", plan="basic", admin_email="suspend@corp.com"
        )
        tenant_id = result.data["id"]

        suspended = await service.suspend_tenant(tenant_id)
        assert bool(suspended) is True

        retrieved = await service.get_tenant(tenant_id)
        assert bool(retrieved) is True
        assert retrieved.data["status"] == "suspended"

    async def test_list_tenants(self):
        service = TenantService()
        await service.create_tenant(name="T1", plan="basic", admin_email="t1@t.com")
        await service.create_tenant(name="T2", plan="pro", admin_email="t2@t.com")

        result = await service.list_tenants()
        assert bool(result) is True
        assert result.data.total >= 2
        assert len(result.data.items) >= 2

    async def test_get_tenant_usage(self):
        service = TenantService()
        result = await service.create_tenant(
            name="Usage Test", plan="basic", admin_email="usage@t.com"
        )
        tenant_id = result.data["id"]

        usage = await service.get_tenant_usage(tenant_id)
        assert bool(usage) is True
        assert "user_count" in usage.data
        assert "storage_used" in usage.data
        assert "api_calls" in usage.data


@pytest.mark.asyncio
class TestDataIsolation:
    async def test_customer_isolation_between_tenants(self):
        from services.customer_service import CustomerService

        cs_a = CustomerService()
        cs_b = CustomerService()

        r1 = await cs_a.create_customer(
            {"name": "Customer A", "email": "a@a.com", "owner_id": 1}, tenant_id=1
        )
        assert bool(r1) is True
        assert r1.data["tenant_id"] == 1

        r2 = await cs_b.create_customer(
            {"name": "Customer B", "email": "b@b.com", "owner_id": 1}, tenant_id=2
        )
        assert bool(r2) is True
        assert r2.data["tenant_id"] == 2

        list_a = await cs_a.list_customers(tenant_id=1)
        assert bool(list_a) is True
        names_a = [c["name"] for c in list_a.data.items]
        assert "Customer A" in names_a
        assert "Customer B" not in names_a

        list_b = await cs_b.list_customers(tenant_id=2)
        assert bool(list_b) is True
        names_b = [c["name"] for c in list_b.data.items]
        assert "Customer B" in names_b
        assert "Customer A" not in names_b
