"""
Unit tests for Customer model.
"""
import pytest
from datetime import datetime
from models.customer import Customer, CustomerStatus


class TestCustomerModel:
    """Tests for Customer model."""

    def test_create_customer_defaults(self):
        """Test customer creation with default values."""
        customer = Customer(
            name="Test Customer",
            email="test@example.com",
            owner_id=1
        )
        
        assert customer.name == "Test Customer"
        assert customer.email == "test@example.com"
        assert customer.owner_id == 1
        assert customer.status == CustomerStatus.LEAD
        assert customer.tags == []
        assert customer.phone is None
        assert customer.company is None
        assert isinstance(customer.created_at, datetime)
        assert isinstance(customer.updated_at, datetime)

    def test_customer_status_enum(self):
        """Test CustomerStatus enum values."""
        assert CustomerStatus.LEAD.value == "lead"
        assert CustomerStatus.OPPORTUNITY.value == "opportunity"
        assert CustomerStatus.CUSTOMER.value == "customer"
        assert CustomerStatus.INACTIVE.value == "inactive"

    def test_to_dict(self):
        """Test customer to_dict conversion."""
        customer = Customer(
            id=1,
            name="Test Customer",
            email="test@example.com",
            phone="13800138000",
            company="Test Corp",
            owner_id=1,
            status=CustomerStatus.LEAD,
            tags=["vip", "enterprise"]
        )
        
        result = customer.to_dict()
        
        assert result["id"] == 1
        assert result["name"] == "Test Customer"
        assert result["email"] == "test@example.com"
        assert result["phone"] == "13800138000"
        assert result["company"] == "Test Corp"
        assert result["owner_id"] == 1
        assert result["status"] == "lead"
        assert result["tags"] == ["vip", "enterprise"]
        assert "created_at" in result
        assert "updated_at" in result

    def test_from_dict(self):
        """Test customer creation from dict."""
        data = {
            "id": 1,
            "name": "Test Customer",
            "email": "test@example.com",
            "phone": "13800138000",
            "company": "Test Corp",
            "owner_id": 1,
            "status": "opportunity",
            "tags": ["vip"],
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"
        }
        
        customer = Customer.from_dict(data)
        
        assert customer.id == 1
        assert customer.name == "Test Customer"
        assert customer.email == "test@example.com"
        assert customer.phone == "13800138000"
        assert customer.company == "Test Corp"
        assert customer.owner_id == 1
        assert customer.status == CustomerStatus.OPPORTUNITY
        assert customer.tags == ["vip"]

    def test_customer_tags(self):
        """Test customer tags functionality."""
        customer = Customer(
            name="Test Customer",
            email="test@example.com",
            owner_id=1,
            tags=["tag1", "tag2"]
        )
        
        assert len(customer.tags) == 2
        assert "tag1" in customer.tags
        assert "tag2" in customer.tags
        
        # Test adding tags
        customer.tags.append("tag3")
        assert len(customer.tags) == 3
        
        # Test removing tags
        customer.tags.remove("tag1")
        assert len(customer.tags) == 2
        assert "tag1" not in customer.tags
