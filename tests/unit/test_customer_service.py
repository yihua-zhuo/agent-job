"""Unit tests for CustomerService — focus on CustomerCreateDTO integration."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
    mock_result.all = AsyncMock(return_value=[])
    mock_result.rowcount = 0
    session.execute = AsyncMock(return_value=mock_result)

    return session


class TestCustomerCreateDTO:
    """Tests for CustomerCreateDTO Pydantic model."""

    def test_required_fields_only(self):
        """CustomerCreateDTO with only required fields."""
        dto = CustomerCreateDTO(name="Alice", email="alice@example.com")
        assert dto.name == "Alice"
        assert dto.email == "alice@example.com"
        assert dto.phone is None
        assert dto.company is None
        assert dto.status == "lead"
        assert dto.owner_id == 0
        assert dto.tags == []

    def test_all_fields(self):
        """CustomerCreateDTO with all fields specified."""
        dto = CustomerCreateDTO(
            name="Bob",
            email="bob@example.com",
            phone="13800138000",
            company="Acme Corp",
            status="customer",
            owner_id=42,
            tags=["vip", "enterprise"],
        )
        assert dto.name == "Bob"
        assert dto.email == "bob@example.com"
        assert dto.phone == "13800138000"
        assert dto.company == "Acme Corp"
        assert dto.status == "customer"
        assert dto.owner_id == 42
        assert dto.tags == ["vip", "enterprise"]

    def test_to_dict(self):
        """to_dict produces expected flat dict for CustomerService."""
        dto = CustomerCreateDTO(
            name="Carol",
            email="carol@example.com",
            phone="13900139000",
            company="Beta Ltd",
            status="opportunity",
            owner_id=7,
            tags=["trial"],
        )
        d = dto.to_dict()
        assert d == {
            "name": "Carol",
            "email": "carol@example.com",
            "phone": "13900139000",
            "company": "Beta Ltd",
            "status": "opportunity",
            "owner_id": 7,
            "tags": ["trial"],
        }

    def test_from_dict(self):
        """from_dict round-trips through to_dict."""
        original = CustomerCreateDTO(
            name="Dave",
            email="dave@example.com",
            phone="13700137000",
            company="Gamma",
            status="lead",
            owner_id=3,
            tags=["prospect"],
        )
        reconstructed = CustomerCreateDTO.from_dict(original.to_dict())
        assert reconstructed.name == original.name
        assert reconstructed.email == original.email
        assert reconstructed.phone == original.phone
        assert reconstructed.company == original.company
        assert reconstructed.status == original.status
        assert reconstructed.owner_id == original.owner_id
        assert reconstructed.tags == original.tags

    def test_from_dict_missing_name_raises(self):
        """from_dict raises ValueError when name is missing."""
        with pytest.raises(ValueError, match="name is required"):
            CustomerCreateDTO.from_dict({"email": "test@example.com"})

    def test_from_dict_missing_email_raises(self):
        """from_dict raises ValueError when email is missing."""
        with pytest.raises(ValueError, match="email is required"):
            CustomerCreateDTO.from_dict({"name": "Test"})

    def test_default_status_is_lead(self):
        """Default status when not specified."""
        dto = CustomerCreateDTO(name="Eve", email="eve@example.com")
        assert dto.status == "lead"

    def test_default_owner_id_is_zero(self):
        """Default owner_id when not specified."""
        dto = CustomerCreateDTO(name="Frank", email="frank@example.com")
        assert dto.owner_id == 0


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
        mock_db_session.commit.assert_called_once()
        assert result.name == "Test"
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_create_customer_accepts_dto(self, mock_db_session):
        """create_customer accepts a CustomerCreateDTO instance."""
        service = CustomerService(mock_db_session)

        async def fake_refresh(obj):
            obj.id = 2
            obj.name = "DTO Customer"
            obj.email = "dto@example.com"

        mock_db_session.refresh = fake_refresh

        dto = CustomerCreateDTO(
            name="DTO Customer",
            email="dto@example.com",
            phone="13600136000",
            company="DTO Corp",
            status="customer",
            owner_id=99,
            tags=["key-account"],
        )
        result = await service.create_customer(dto, tenant_id=1)

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.name == "DTO Customer"
        assert call_args.email == "dto@example.com"
        assert call_args.phone == "13600136000"
        assert call_args.company == "DTO Corp"
        assert call_args.status == "customer"
        assert call_args.owner_id == 99
        assert call_args.tags == ["key-account"]
        assert result.name == "DTO Customer"

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
