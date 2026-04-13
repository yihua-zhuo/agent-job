"""
Unit tests for CustomerService.
"""
import pytest
from src.services.customer_service import CustomerService
from src.models.customer import CustomerStatus


@pytest.fixture
def customer_service():
    """Create a fresh CustomerService instance for each test."""
    return CustomerService()


class TestCustomerService:
    """Tests for CustomerService."""

    def test_create_customer_success(self, customer_service):
        """Test successful customer creation."""
        result = customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "13800138000",
            "company": "Acme Corp",
            "owner_id": 1,
            "tags": ["vip"]
        })

        assert bool(result) is True
        assert result.message == "客户创建成功"
        assert result.data is not None
        assert result.data["name"] == "John Doe"
        assert result.data["email"] == "john@example.com"

    def test_create_customer_empty_name(self, customer_service):
        """Test creating customer with empty name fails."""
        result = customer_service.create_customer({
            "name": "",
            "email": "test@test.com",
            "owner_id": 1,
        })
        assert bool(result) is False

    def test_get_customer(self, customer_service):
        """Test getting a customer by ID."""
        create = customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1,
        })
        customer_id = create.data["id"]

        result = customer_service.get_customer(customer_id)
        assert bool(result) is True
        assert result.data["name"] == "John Doe"

    def test_get_nonexistent_customer(self, customer_service):
        """Test getting a nonexistent customer returns error."""
        result = customer_service.get_customer(9999)
        assert bool(result) is False

    def test_update_customer(self, customer_service):
        """Test updating a customer."""
        create = customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "company": "Old Corp",
            "owner_id": 1,
        })
        customer_id = create.data["id"]

        result = customer_service.update_customer(customer_id, {
            "name": "John Smith",
            "company": "New Corp",
        })
        assert bool(result) is True
        assert result.data["name"] == "John Smith"
        assert result.data["company"] == "New Corp"

    def test_delete_customer(self, customer_service):
        """Test deleting a customer."""
        create = customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1,
        })
        customer_id = create.data["id"]

        result = customer_service.delete_customer(customer_id)
        assert bool(result) is True

        # Verify deleted
        get_result = customer_service.get_customer(customer_id)
        assert bool(get_result) is False

    def test_list_customers_pagination(self, customer_service):
        """Test listing customers with pagination."""
        for i in range(5):
            customer_service.create_customer({
                "name": f"Customer {i}",
                "email": f"c{i}@example.com",
                "owner_id": 1,
            })

        result = customer_service.list_customers(page=1, page_size=3)
        assert bool(result) is True
        assert len(result.data.items) == 3
        assert result.data.total == 5

    def test_list_customers_filter_by_status(self, customer_service):
        """Test filtering customers by status."""
        customer_service.create_customer({
            "name": "Active Customer",
            "email": "active@example.com",
            "owner_id": 1,
        })

        result = customer_service.list_customers(status="inactive")
        assert bool(result) is True
        # No inactive customers created
        assert len(result.data.items) == 0

    def test_count_by_status_basic(self, customer_service):
        """Test count_by_status returns correct counts per status for a tenant."""
        customer_service.create_customer({
            "name": "Lead 1", "email": "lead1@test.com", "owner_id": 1,
            "status": "lead",
        }, tenant_id=1)
        customer_service.create_customer({
            "name": "Active 1", "email": "active1@test.com", "owner_id": 1,
            "status": "customer",
        }, tenant_id=1)
        customer_service.create_customer({
            "name": "Inactive 1", "email": "inactive1@test.com", "owner_id": 1,
            "status": "inactive",
        }, tenant_id=1)

        counts = customer_service.count_by_status(1)
        assert counts == {
            CustomerStatus.LEAD: 1,
            CustomerStatus.CUSTOMER: 1,
            CustomerStatus.INACTIVE: 1,
        }

    def test_count_by_status_multi_tenant(self, customer_service):
        """Test count_by_status isolates counts per tenant."""
        # Tenant 1: 2 customers
        customer_service.create_customer({
            "name": "T1 Customer", "email": "t1a@test.com", "owner_id": 1,
            "status": "customer",
        }, tenant_id=1)
        customer_service.create_customer({
            "name": "T1 Lead", "email": "t1l@test.com", "owner_id": 1,
            "status": "lead",
        }, tenant_id=1)
        # Tenant 2: 1 customer
        customer_service.create_customer({
            "name": "T2 Customer", "email": "t2c@test.com", "owner_id": 2,
            "status": "customer",
        }, tenant_id=2)

        counts_t1 = customer_service.count_by_status(1)
        counts_t2 = customer_service.count_by_status(2)

        assert counts_t1 == {CustomerStatus.CUSTOMER: 1, CustomerStatus.LEAD: 1}
        assert counts_t2 == {CustomerStatus.CUSTOMER: 1}

    def test_count_by_status_zero_tenant(self, customer_service):
        """Test count_by_status returns empty dict for tenant_id <= 0."""
        customer_service.create_customer({
            "name": "Any Customer", "email": "any@test.com", "owner_id": 1,
        }, tenant_id=1)

        assert customer_service.count_by_status(0) == {}
        assert customer_service.count_by_status(-1) == {}

    def test_list_customers_filter_by_owner(self, customer_service):
        """Test filtering customers by owner."""
        customer_service.create_customer({
            "name": "Owner 1 Customer",
            "email": "o1@example.com",
            "owner_id": 1,
        })
        customer_service.create_customer({
            "name": "Owner 2 Customer",
            "email": "o2@example.com",
            "owner_id": 2,
        })

        result = customer_service.list_customers(owner_id=1)
        assert bool(result) is True
        assert len(result.data.items) == 1
        assert result.data.items[0]["name"] == "Owner 1 Customer"

    def test_search_customers(self, customer_service):
        """Test searching customers by keyword."""
        customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "company": "Acme Corp",
            "owner_id": 1,
        })

        result = customer_service.search_customers(keyword="john")
        assert bool(result) is True
        assert len(result.data["items"]) >= 1

    def test_add_tag(self, customer_service):
        """Test adding a tag to a customer."""
        create = customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1,
        })
        customer_id = create.data["id"]

        result = customer_service.add_tag(customer_id, "vip")
        assert bool(result) is True

    def test_remove_tag(self, customer_service):
        """Test removing a tag from a customer."""
        create = customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1,
            "tags": ["vip"],
        })
        customer_id = create.data["id"]

        result = customer_service.remove_tag(customer_id, "vip")
        assert bool(result) is True

    def test_change_status(self, customer_service):
        """Test changing customer status."""
        create = customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1,
        })
        customer_id = create.data["id"]

        result = customer_service.change_status(customer_id, "opportunity")
        assert bool(result) is True
        assert result.data["status"] == "opportunity"

    def test_bulk_import(self, customer_service):
        """Test bulk importing customers."""
        customers = [
            {"name": f"Import {i}", "email": f"imp{i}@test.com", "owner_id": 1}
            for i in range(3)
        ]
        result = customer_service.bulk_import(customers)
        assert bool(result) is True
        assert result.data["imported"] == 3


class TestCustomerServiceTenantIsolation:
    """Tests for CustomerService tenant isolation."""

    def test_create_customer_with_tenant_id(self, customer_service):
        """Test creating customer with tenant_id."""
        result = customer_service.create_customer(
            {"name": "Tenant Customer", "email": "t@c.com", "owner_id": 1},
            tenant_id=42
        )
        assert bool(result) is True
        assert result.data["tenant_id"] == 42

    def test_list_customers_filters_by_tenant(self):
        """Test listing customers only returns those for the tenant."""
        cs_a = CustomerService()
        cs_b = CustomerService()

        # Tenant A creates customer
        r1 = cs_a.create_customer({"name": "Customer A", "email": "a@a.com", "owner_id": 1}, tenant_id=1)
        assert bool(r1) is True

        # Tenant B creates customer
        r2 = cs_b.create_customer({"name": "Customer B", "email": "b@b.com", "owner_id": 1}, tenant_id=2)
        assert bool(r2) is True

        # Each tenant only sees their own
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

    def test_get_customer_verifies_tenant(self):
        """Test getting customer verifies tenant ownership."""
        cs_a = CustomerService()
        cs_b = CustomerService()

        r1 = cs_a.create_customer({"name": "A Customer", "email": "a@a.com", "owner_id": 1}, tenant_id=1)
        cust_id = r1.data["id"]

        # Tenant B cannot see Tenant A's customer
        result = cs_b.get_customer(cust_id, tenant_id=2)
        assert bool(result) is False

        # Tenant A can see their own
        result = cs_a.get_customer(cust_id, tenant_id=1)
        assert bool(result) is True

    def test_update_customer_verifies_tenant(self):
        """Test updating customer verifies tenant ownership."""
        cs_a = CustomerService()
        cs_b = CustomerService()

        r1 = cs_a.create_customer({"name": "A Customer", "email": "a@a.com", "owner_id": 1}, tenant_id=1)
        cust_id = r1.data["id"]

        # Tenant B cannot update Tenant A's customer
        result = cs_b.update_customer(cust_id, {"name": "Hacked"}, tenant_id=2)
        assert bool(result) is False

        # Tenant A can update their own
        result = cs_a.update_customer(cust_id, {"name": "Updated"}, tenant_id=1)
        assert bool(result) is True

    def test_delete_customer_verifies_tenant(self):
        """Test deleting customer verifies tenant ownership."""
        cs_a = CustomerService()
        cs_b = CustomerService()

        r1 = cs_a.create_customer({"name": "A Customer", "email": "a@a.com", "owner_id": 1}, tenant_id=1)
        cust_id = r1.data["id"]

        # Tenant B cannot delete Tenant A's customer
        result = cs_b.delete_customer(cust_id, tenant_id=2)
        assert bool(result) is False

        # Tenant A can delete their own
        result = cs_a.delete_customer(cust_id, tenant_id=1)
        assert bool(result) is True

    def test_search_customers_filters_by_tenant(self):
        """Test searching customers only returns those for the tenant."""
        cs_a = CustomerService()
        cs_b = CustomerService()

        cs_a.create_customer({"name": "Alpha Customer", "email": "alpha@c.com", "owner_id": 1}, tenant_id=1)
        cs_b.create_customer({"name": "Beta Customer", "email": "beta@c.com", "owner_id": 1}, tenant_id=2)

        result_a = cs_a.search_customers("Customer", tenant_id=1)
        assert bool(result_a) is True
        names_a = [c["name"] for c in result_a.data["items"]]
        assert "Alpha Customer" in names_a
        assert "Beta Customer" not in names_a

        result_b = cs_b.search_customers("Customer", tenant_id=2)
        assert bool(result_b) is True
        names_b = [c["name"] for c in result_b.data["items"]]
        assert "Beta Customer" in names_b
        assert "Alpha Customer" not in names_b
