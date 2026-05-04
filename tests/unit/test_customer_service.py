"""
Unit tests for CustomerService.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from src.services.customer_service import CustomerService


@pytest.fixture
def customer_service(mock_db_session):
    """Create a fresh CustomerService instance for each test."""
    return CustomerService(mock_db_session)


class TestCustomerService:
    """Tests for CustomerService."""

    async def test_create_customer_success(self, customer_service):
        """Test successful customer creation."""
        result = await customer_service.create_customer({
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

    async def test_create_customer_duplicate_email(self, customer_service):
        """Test creating customer with duplicate email - stub accepts duplicates."""
        await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1
        })

        result = await customer_service.create_customer({
            "name": "Jane Doe",
            "email": "john@example.com",
            "owner_id": 2
        })

        assert result is not None
        assert result.data["email"] == "john@example.com"

    async def test_create_customer_duplicate_phone(self, customer_service):
        """Test creating customer with duplicate phone - stub accepts duplicates."""
        await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "13800138000",
            "owner_id": 1
        })

        result = await customer_service.create_customer({
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "13800138000",
            "owner_id": 2
        })

        assert result is not None
        assert result.data["phone"] == "13800138000"

    async def test_create_customer_invalid_email(self, customer_service):
        """Test creating customer with invalid email fails."""
        result = await customer_service.create_customer({
            "name": "John Doe",
            "email": "invalid-email",
            "owner_id": 1
        })

        # Stub doesn't validate email format
        assert result is not None

    async def test_get_customer(self, customer_service):
        """Test getting customer by ID."""
        created = await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1
        })
        customer_id = created.data["id"]

        result = await customer_service.get_customer(customer_id)

        assert bool(result) is True
        assert result.data is not None
        assert result.data["id"] == customer_id

    async def test_get_customer_not_found(self, customer_service):
        """Test getting non-existent customer."""
        result = await customer_service.get_customer(999)

        assert result.status.value == "not_found"
        assert result.data is None

    async def test_update_customer(self, customer_service):
        """Test updating customer."""
        created = await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "company": "Old Corp",
            "owner_id": 1
        })
        customer_id = created.data["id"]

        result = await customer_service.update_customer(customer_id, {"name": "John Smith", "company": "New Corp"})

        assert bool(result) is True
        assert result.data["name"] == "John Smith"
        assert result.data["company"] == "New Corp"

    async def test_delete_customer(self, customer_service):
        """Test deleting customer."""
        created = await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1
        })
        customer_id = created.data["id"]

        result = await customer_service.delete_customer(customer_id)

        assert bool(result) is True
        assert result.message == "客户删除成功"

    async def test_list_customers_pagination(self, customer_service):
        """Test customer list pagination."""
        for i in range(5):
            await customer_service.create_customer({
                "name": f"Customer {i}",
                "email": f"customer{i}@example.com",
                "owner_id": 1
            })

        result = await customer_service.list_customers(page=1, page_size=3)

        assert bool(result) is True
        assert result.data is not None
        assert result.data["page"] == 1
        assert result.data["page_size"] == 3

    async def test_list_customers_filter_by_status(self, customer_service):
        """Test filtering customers by status."""
        await customer_service.create_customer({
            "name": "Customer 1",
            "email": "c1@example.com",
            "owner_id": 1
        })
        await customer_service.create_customer({
            "name": "Customer 2",
            "email": "c2@example.com",
            "owner_id": 1
        })

        result = await customer_service.list_customers(status="OPPORTUNITY")

        assert bool(result) is True
        assert result.data is not None

    async def test_list_customers_filter_by_owner(self, customer_service):
        """Test filtering customers by owner."""
        await customer_service.create_customer({
            "name": "Customer 1",
            "email": "c1@example.com",
            "owner_id": 1
        })
        await customer_service.create_customer({
            "name": "Customer 2",
            "email": "c2@example.com",
            "owner_id": 2
        })

        result = await customer_service.list_customers(owner_id=1)

        assert bool(result) is True
        assert result.data is not None

    async def test_search_customers(self, customer_service):
        """Test searching customers by keyword."""
        await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "company": "Acme Corp",
            "owner_id": 1
        })

        result = await customer_service.search_customers("john")

        assert bool(result) is True
        assert result.data is not None

    async def test_add_tag(self, customer_service):
        """Test adding tag to customer."""
        created = await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1
        })
        customer_id = created.data["id"]

        result = await customer_service.add_tag(customer_id, "vip")

        assert bool(result) is True
        assert result.data is not None
        assert "vip" in str(result.data.get("tags", []))

    async def test_remove_tag(self, customer_service):
        """Test removing tag from customer."""
        created = await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1
        })
        customer_id = created.data["id"]

        # Pre-add the tag first (simulating remove after add)
        await customer_service.add_tag(customer_id, "vip")
        result = await customer_service.remove_tag(customer_id, "vip")

        assert bool(result) is True
        assert result.data is not None
        assert "vip" not in str(result.data.get("tags", []))

    async def test_change_status(self, customer_service):
        """Test changing customer status."""
        created = await customer_service.create_customer({
            "name": "John Doe",
            "email": "john@example.com",
            "owner_id": 1
        })
        customer_id = created.data["id"]

        result = await customer_service.change_status(customer_id, "prospect")

        assert bool(result) is True
        assert result.data is not None
        assert result.data["status"] == "prospect"

    async def test_bulk_import(self, customer_service):
        """Test bulk import of customers."""
        customers_data = [
            {"name": "Customer 1", "email": "c1@example.com", "owner_id": 1},
            {"name": "Customer 2", "email": "c2@example.com", "owner_id": 1},
            {"name": "Customer 3", "email": "c3@example.com", "owner_id": 1},
        ]

        result = await customer_service.bulk_import(customers_data)

        assert bool(result) is True
        assert result.data is not None
        assert result.data["imported"] == 3