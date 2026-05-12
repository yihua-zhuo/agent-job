"""Unit tests for CustomerService — focus on CustomerCreateDTO integration."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.customer import CustomerStatus
from models.customer_create_dto import CustomerCreateDTO
from services.customer_service import CustomerService


@pytest.fixture
def mock_db_session():
    """Async mock session that tracks calls and properly wires execute()."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()

    # Wire execute() to return a mock result object with the ORM methods tests use
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=None)
    mock_result.scalar = AsyncMock(return_value=0)
    mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    mock_result.fetchall = MagicMock(return_value=[])
    mock_result.all = MagicMock(return_value=[])
    mock_result.rowcount = 0
    session.execute = AsyncMock(return_value=mock_result)

    return session


class TestCustomerCreateDTO:
    """Tests for CustomerCreateDTO Pydantic model."""

    def test_required_fields_only(self):
        dto = CustomerCreateDTO(name="Alice", email="alice@example.com")
        assert dto.name == "Alice"
        assert dto.email == "alice@example.com"
        assert dto.status == "lead"
        assert dto.owner_id == 0

    def test_all_fields(self):
        dto = CustomerCreateDTO(
            name="Bob",
            email="bob@example.com",
            status="opportunity",
            owner_id=5,
            tags=["vip", "referral"],
        )
        assert dto.name == "Bob"
        assert dto.email == "bob@example.com"
        assert dto.status == "opportunity"
        assert dto.owner_id == 5
        assert dto.tags == ["vip", "referral"]

    def test_to_dict(self):
        dto = CustomerCreateDTO(name="Charlie", email="charlie@example.com")
        result = dto.to_dict()
        assert result["name"] == "Charlie"
        assert result["email"] == "charlie@example.com"
        assert result["status"] == "lead"
        assert result["owner_id"] == 0
        assert result["tags"] == []

    def test_from_dict(self):
        data = {
            "name": "Diana",
            "email": "diana@example.com",
            "status": "inactive",
            "owner_id": 3,
            "tags": ["newsletter"],
        }
        dto = CustomerCreateDTO.from_dict(data)
        assert dto.name == "Diana"
        assert dto.email == "diana@example.com"
        assert dto.status == "inactive"
        assert dto.owner_id == 3
        assert dto.tags == ["newsletter"]

    def test_from_dict_missing_name_raises(self):
        with pytest.raises(ValueError):
            CustomerCreateDTO.from_dict({"email": "no-name@example.com"})

    def test_from_dict_missing_email_raises(self):
        with pytest.raises(ValueError):
            CustomerCreateDTO.from_dict({"name": "No Email"})

    def test_default_status_is_lead(self):
        dto = CustomerCreateDTO(name="Eve", email="eve@example.com")
        assert dto.status == "lead"

    def test_default_owner_id_is_zero(self):
        dto = CustomerCreateDTO(name="Frank", email="frank@example.com")
        assert dto.owner_id == 0

    def test_to_dict_email_normalized(self):
        dto = CustomerCreateDTO(name="Grace", email="  grace@example.com  ")
        assert dto.email == "grace@example.com"


class TestCreateCustomerService:
    """Tests for CustomerService.create_customer with DTO support."""

    @pytest.mark.asyncio
    async def test_create_customer_accepts_dict(self, mock_db_session):
        """create_customer works with a plain dict (backward compat)."""
        service = CustomerService(mock_db_session)

        async def fake_refresh(obj):
            obj.id = 1
            obj.name = "Test"
            obj.email = "test@example.com"

        mock_db_session.refresh = fake_refresh

        result = await service.create_customer(
            {"name": "Test", "email": "test@example.com"},
            tenant_id=1,
        )
        mock_db_session.add.assert_called_once()
        # Services flush; the router-bound get_db dependency owns commit (rule 121/122).
        mock_db_session.flush.assert_called_once()
        assert result.name == "Test"

    @pytest.mark.asyncio
    async def test_create_customer_accepts_dto(self, mock_db_session):
        """create_customer works with a CustomerCreateDTO instance."""
        service = CustomerService(mock_db_session)

        async def fake_refresh(obj):
            obj.id = 2
            obj.name = "DTO Test"
            obj.email = "dto@example.com"

        mock_db_session.refresh = fake_refresh

        dto = CustomerCreateDTO(name="DTO Test", email="dto@example.com", owner_id=7)
        result = await service.create_customer(dto, tenant_id=1)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        assert result.name == "DTO Test"

    @pytest.mark.asyncio
    async def test_create_customer_empty_dict_uses_defaults(self, mock_db_session):
        """create_customer with empty dict falls back to default values."""
        service = CustomerService(mock_db_session)

        async def fake_refresh(obj):
            obj.id = 3
            obj.name = "Customer"
            obj.email = None

        mock_db_session.refresh = fake_refresh

        result = await service.create_customer({}, tenant_id=1)

        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.name == "Customer"  # default from service
        assert call_args.email is None
        assert call_args.status == "lead"
        assert call_args.owner_id == 0
        assert call_args.tags == []
        assert result.name == "Customer"


class TestCountByStatus:
    """Tests for CustomerService.count_by_status."""

    @pytest.mark.asyncio
    async def test_count_by_status_basic(self, mock_db_session):
        """Create 3 customers (LEAD, OPPORTUNITY, INACTIVE) for tenant 1; assert counts match."""
        service = CustomerService(mock_db_session)

        # Simulate rows: (status_value, count)
        mock_rows = [
            (CustomerStatus.LEAD.value, 2),
            (CustomerStatus.OPPORTUNITY.value, 3),
            (CustomerStatus.INACTIVE.value, 1),
        ]
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=mock_rows)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await service.count_by_status(tenant_id=1)

        assert result[CustomerStatus.LEAD] == 2
        assert result[CustomerStatus.OPPORTUNITY] == 3
        assert result[CustomerStatus.INACTIVE] == 1

    @pytest.mark.asyncio
    async def test_count_by_status_multi_tenant(self, mock_db_session):
        """Tenant 2 customers do not leak into tenant 1 counts."""
        service = CustomerService(mock_db_session)

        mock_rows = [(CustomerStatus.OPPORTUNITY.value, 5)]
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=mock_rows)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await service.count_by_status(tenant_id=2)

        assert result[CustomerStatus.OPPORTUNITY] == 5
        # Tenant 1 statuses should not appear
        assert CustomerStatus.LEAD not in result
        assert CustomerStatus.INACTIVE not in result

    @pytest.mark.asyncio
    async def test_count_by_status_zero_tenant(self, mock_db_session):
        """count_by_status(0) returns empty dict when no customers exist."""
        service = CustomerService(mock_db_session)

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await service.count_by_status(tenant_id=0)

        assert result == {}
