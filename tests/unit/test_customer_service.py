"""Unit tests for CustomerService."""
import pytest
from src.services.customer_service import CustomerService
from src.models.customer import CustomerStatus


@pytest.fixture
def customer_service():
    return CustomerService()


@pytest.mark.asyncio
class TestCustomerService:
    async def test_create_customer_success(self, customer_service):
        result = await customer_service.create_customer(
            {"name": "John Doe", "email": "john@example.com",
             "phone": "13800138000", "company": "Acme Corp",
             "owner_id": 1, "tags": ["vip"]},
            tenant_id=1,
        )
        assert bool(result) is True
        assert result.message == "客户创建成功"
        assert result.data["name"] == "John Doe"
        assert result.data["email"] == "john@example.com"

    async def test_create_customer_empty_name(self, customer_service):
        result = await customer_service.create_customer(
            {"name": "", "email": "test@test.com", "owner_id": 1}
        )
        assert bool(result) is False


    async def test_get_nonexistent_customer(self, customer_service):
        result = await customer_service.get_customer(9999, tenant_id=1)
        assert bool(result) is False


    async def test_delete_customer(self, customer_service):
        create = await customer_service.create_customer(
            {"name": "John Doe", "email": "john@example.com", "owner_id": 1},
            tenant_id=1,
        )
        customer_id = create.data["id"]
        result = await customer_service.delete_customer(customer_id, tenant_id=1)
        assert bool(result) is True
        gone = await customer_service.get_customer(customer_id, tenant_id=1)
        assert bool(gone) is False





    async def test_count_by_status_zero_tenant(self, customer_service):
        await customer_service.create_customer(
            {"name": "Any", "email": "any@test.com", "owner_id": 1}, tenant_id=1
        )
        assert await customer_service.count_by_status(0) == {}
        assert await customer_service.count_by_status(-1) == {}

    async def test_list_customers_filter_by_owner(self, customer_service):
        await customer_service.create_customer(
            {"name": "Owner 1 Customer", "email": "o1@example.com", "owner_id": 1},
            tenant_id=1,
        )
        await customer_service.create_customer(
            {"name": "Owner 2 Customer", "email": "o2@example.com", "owner_id": 2},
            tenant_id=1,
        )
        result = await customer_service.list_customers(owner_id=1, tenant_id=1)
        assert bool(result) is True
        assert len(result.data.items) >= 1
        assert all(c["owner_id"] == 1 for c in result.data.items)

    async def test_search_customers(self, customer_service):
        await customer_service.create_customer(
            {"name": "John Doe", "email": "john@example.com",
             "company": "Acme Corp", "owner_id": 1},
            tenant_id=1,
        )
        result = await customer_service.search_customers("john", tenant_id=1)
        assert bool(result) is True
        assert len(result.data["items"]) >= 1




    async def test_bulk_import(self, customer_service):
        customers = [
            {"name": f"Import {i}", "email": f"imp{i}@test.com", "owner_id": 1}
            for i in range(3)
        ]
        result = await customer_service.bulk_import(customers, tenant_id=1)
        assert bool(result) is True
        assert result.data["imported"] == 3


@pytest.mark.asyncio
class TestCustomerServiceTenantIsolation:
    async def test_create_customer_with_tenant_id(self, customer_service):
        result = await customer_service.create_customer(
            {"name": "Tenant Customer", "email": "t@c.com", "owner_id": 1}, tenant_id=42
        )
        assert bool(result) is True
        assert result.data["tenant_id"] == 42





