"""Unit tests for CustomerService."""
import pytest
from services.customer_service import CustomerService
from models.customer import CustomerStatus


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

    async def test_get_customer(self, customer_service):
        create = await customer_service.create_customer(
            {"name": "John Doe", "email": "john@example.com", "owner_id": 1},
            tenant_id=1,
        )
        customer_id = create.data["id"]
        result = await customer_service.get_customer(customer_id, tenant_id=1)
        assert bool(result) is True
        assert result.data["name"] == "John Doe"

    async def test_get_nonexistent_customer(self, customer_service):
        result = await customer_service.get_customer(9999, tenant_id=1)
        assert bool(result) is False

    async def test_update_customer(self, customer_service):
        create = await customer_service.create_customer(
            {"name": "John Doe", "email": "john@example.com",
             "company": "Old Corp", "owner_id": 1},
            tenant_id=1,
        )
        customer_id = create.data["id"]
        result = await customer_service.update_customer(
            customer_id, {"name": "John Smith", "company": "New Corp"}, tenant_id=1
        )
        assert bool(result) is True
        assert result.data["name"] == "John Smith"
        assert result.data["company"] == "New Corp"

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

    async def test_list_customers_pagination(self, customer_service):
        for i in range(5):
            await customer_service.create_customer(
                {"name": f"Customer {i}", "email": f"c{i}@example.com", "owner_id": 1},
                tenant_id=1,
            )
        result = await customer_service.list_customers(page=1, page_size=3, tenant_id=1)
        assert bool(result) is True
        assert len(result.data.items) == 3
        assert result.data.total == 5

    async def test_list_customers_filter_by_status(self, customer_service):
        await customer_service.create_customer(
            {"name": "Active Customer", "email": "active@example.com", "owner_id": 1},
            tenant_id=1,
        )
        result = await customer_service.list_customers(status="inactive", tenant_id=1)
        assert bool(result) is True
        assert len(result.data.items) == 0

    async def test_count_by_status_basic(self, customer_service):
        await customer_service.create_customer(
            {"name": "Lead 1", "email": "lead1@test.com", "owner_id": 1, "status": "lead"},
            tenant_id=1,
        )
        await customer_service.create_customer(
            {"name": "Active 1", "email": "active1@test.com", "owner_id": 1,
             "status": "customer"},
            tenant_id=1,
        )
        await customer_service.create_customer(
            {"name": "Inactive 1", "email": "inactive1@test.com", "owner_id": 1,
             "status": "inactive"},
            tenant_id=1,
        )
        counts = await customer_service.count_by_status(1)
        assert CustomerStatus.LEAD in counts
        assert CustomerStatus.CUSTOMER in counts
        assert CustomerStatus.INACTIVE in counts

    async def test_count_by_status_multi_tenant(self, customer_service):
        await customer_service.create_customer(
            {"name": "T1 Customer", "email": "t1a@test.com", "owner_id": 1,
             "status": "customer"},
            tenant_id=1,
        )
        await customer_service.create_customer(
            {"name": "T1 Lead", "email": "t1l@test.com", "owner_id": 1, "status": "lead"},
            tenant_id=1,
        )
        await customer_service.create_customer(
            {"name": "T2 Customer", "email": "t2c@test.com", "owner_id": 2,
             "status": "customer"},
            tenant_id=2,
        )
        counts_t1 = await customer_service.count_by_status(1)
        counts_t2 = await customer_service.count_by_status(2)
        assert CustomerStatus.CUSTOMER in counts_t1
        assert CustomerStatus.LEAD in counts_t1
        assert CustomerStatus.CUSTOMER in counts_t2
        assert CustomerStatus.LEAD not in counts_t2

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

    async def test_add_tag(self, customer_service):
        create = await customer_service.create_customer(
            {"name": "John Doe", "email": "john@example.com", "owner_id": 1},
            tenant_id=1,
        )
        customer_id = create.data["id"]
        result = await customer_service.add_tag(customer_id, "vip", tenant_id=1)
        assert bool(result) is True

    async def test_remove_tag(self, customer_service):
        create = await customer_service.create_customer(
            {"name": "John Doe", "email": "john@example.com", "owner_id": 1,
             "tags": ["vip"]},
            tenant_id=1,
        )
        customer_id = create.data["id"]
        result = await customer_service.remove_tag(customer_id, "vip", tenant_id=1)
        assert bool(result) is True

    async def test_change_status(self, customer_service):
        create = await customer_service.create_customer(
            {"name": "John Doe", "email": "john@example.com", "owner_id": 1},
            tenant_id=1,
        )
        customer_id = create.data["id"]
        result = await customer_service.change_status(customer_id, "opportunity", tenant_id=1)
        assert bool(result) is True
        assert result.data["status"] == "opportunity"

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

    async def test_list_customers_filters_by_tenant(self):
        cs_a = CustomerService()
        cs_b = CustomerService()
        r1 = await cs_a.create_customer(
            {"name": "Customer A", "email": "a@a.com", "owner_id": 1}, tenant_id=1
        )
        await cs_b.create_customer(
            {"name": "Customer B", "email": "b@b.com", "owner_id": 1}, tenant_id=2
        )
        list_a = await cs_a.list_customers(tenant_id=1)
        names_a = [c["name"] for c in list_a.data.items]
        assert "Customer A" in names_a
        assert "Customer B" not in names_a

    async def test_get_customer_verifies_tenant(self):
        cs_a = CustomerService()
        cs_b = CustomerService()
        r1 = await cs_a.create_customer(
            {"name": "A Customer", "email": "a@a.com", "owner_id": 1}, tenant_id=1
        )
        cust_id = r1.data["id"]
        # Tenant 2 cannot see tenant 1's customer
        result = await cs_b.get_customer(cust_id, tenant_id=2)
        assert bool(result) is False
        # Tenant 1 can see their own
        result = await cs_a.get_customer(cust_id, tenant_id=1)
        assert bool(result) is True

    async def test_update_customer_verifies_tenant(self):
        cs_a = CustomerService()
        cs_b = CustomerService()
        r1 = await cs_a.create_customer(
            {"name": "A Customer", "email": "a@a.com", "owner_id": 1}, tenant_id=1
        )
        cust_id = r1.data["id"]
        result = await cs_b.update_customer(cust_id, {"name": "Hacked"}, tenant_id=2)
        assert bool(result) is False
        result = await cs_a.update_customer(cust_id, {"name": "Updated"}, tenant_id=1)
        assert bool(result) is True

    async def test_delete_customer_verifies_tenant(self):
        cs_a = CustomerService()
        cs_b = CustomerService()
        r1 = await cs_a.create_customer(
            {"name": "A Customer", "email": "a@a.com", "owner_id": 1}, tenant_id=1
        )
        cust_id = r1.data["id"]
        result = await cs_b.delete_customer(cust_id, tenant_id=2)
        assert bool(result) is False
        result = await cs_a.delete_customer(cust_id, tenant_id=1)
        assert bool(result) is True

    async def test_search_customers_filters_by_tenant(self):
        cs_a = CustomerService()
        cs_b = CustomerService()
        await cs_a.create_customer(
            {"name": "Alpha Customer", "email": "alpha@c.com", "owner_id": 1}, tenant_id=1
        )
        await cs_b.create_customer(
            {"name": "Beta Customer", "email": "beta@c.com", "owner_id": 1}, tenant_id=2
        )
        result_a = await cs_a.search_customers("Customer", tenant_id=1)
        names_a = [c["name"] for c in result_a.data["items"]]
        assert "Alpha Customer" in names_a
        assert "Beta Customer" not in names_a
        result_b = await cs_b.search_customers("Customer", tenant_id=2)
        names_b = [c["name"] for c in result_b.data["items"]]
        assert "Beta Customer" in names_b
        assert "Alpha Customer" not in names_b
