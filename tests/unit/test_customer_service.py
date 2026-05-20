"""Unit tests for CustomerService — focus on CustomerCreateDTO integration and repo delegation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.customer import CustomerStatus
from models.customer_create_dto import CustomerCreateDTO
from services.customer_service import CustomerService


def _make_mock_customer_repo():
    """Build a mock CustomerRepository with all async methods."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.list_customers = AsyncMock()
    repo.get_customer = AsyncMock()
    repo.update_customer = AsyncMock()
    repo.delete_customer = AsyncMock()
    repo.count_by_status = AsyncMock()
    repo.search_customers = AsyncMock()
    repo.add_tag = AsyncMock()
    repo.remove_tag = AsyncMock()
    repo.bulk_import = AsyncMock()
    return repo


@pytest.fixture
def mock_db_session():
    """Async mock session."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.delete = MagicMock()
    return session


@pytest.fixture
def mock_customer_repo():
    return _make_mock_customer_repo()


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
    """Tests for CustomerService.create_customer — delegates to CustomerRepository.create."""

    @pytest.mark.asyncio
    async def test_create_customer_accepts_dict(self, mock_db_session, mock_customer_repo):
        """create_customer works with a plain dict (backward compat)."""
        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.name = "Test"
        mock_customer.email = "test@example.com"
        mock_customer.status = "lead"
        mock_customer.owner_id = 0
        mock_customer_repo.create = AsyncMock(return_value=mock_customer)
        service = CustomerService(mock_db_session, mock_customer_repo)

        with patch(
            "services.lead_routing_service.LeadRoutingService.auto_assign_lead",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await service.create_customer(
                {"name": "Test", "email": "test@example.com"},
                tenant_id=1,
            )

        mock_customer_repo.create.assert_awaited_once_with(
            {"name": "Test", "email": "test@example.com"}, 1
        )
        assert result.name == "Test"
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_create_customer_accepts_dto(self, mock_db_session, mock_customer_repo):
        """create_customer accepts a CustomerCreateDTO instance."""
        mock_customer = MagicMock()
        mock_customer.id = 2
        mock_customer.name = "DTO Customer"
        mock_customer.email = "dto@example.com"
        mock_customer.status = "customer"
        mock_customer.owner_id = 99
        mock_customer.tags = ["key-account"]
        mock_customer_repo.create = AsyncMock(return_value=mock_customer)
        service = CustomerService(mock_db_session, mock_customer_repo)

        dto = CustomerCreateDTO(
            name="DTO Customer",
            email="dto@example.com",
            phone="13600136000",
            company="DTO Corp",
            status="customer",
            owner_id=99,
            tags=["key-account"],
        )
        with patch(
            "services.lead_routing_service.LeadRoutingService.auto_assign_lead",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await service.create_customer(dto, tenant_id=1)

        call_args = mock_customer_repo.create.call_args[0][0]
        assert call_args["name"] == "DTO Customer"
        assert call_args["email"] == "dto@example.com"
        assert call_args["phone"] == "13600136000"
        assert call_args["company"] == "DTO Corp"
        assert call_args["status"] == "customer"
        assert call_args["owner_id"] == 99
        assert call_args["tags"] == ["key-account"]
        assert result.name == "DTO Customer"

    @pytest.mark.asyncio
    async def test_create_customer_empty_dict_uses_defaults(self, mock_db_session, mock_customer_repo):
        """create_customer with empty dict falls back to default values."""
        mock_customer = MagicMock()
        mock_customer.id = 3
        mock_customer.name = "Customer"
        mock_customer.email = None
        mock_customer.status = "lead"
        mock_customer.owner_id = 0
        mock_customer.tags = []
        mock_customer_repo.create = AsyncMock(return_value=mock_customer)
        service = CustomerService(mock_db_session, mock_customer_repo)

        with patch(
            "services.lead_routing_service.LeadRoutingService.auto_assign_lead",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await service.create_customer({}, tenant_id=1)

        call_args = mock_customer_repo.create.call_args[0][0]
        assert call_args.get("name") is None  # repo fills default "Customer"
        assert call_args.get("email") is None
        assert result.name == "Customer"


@pytest.mark.asyncio
class TestCountByStatus:
    """Unit tests for CustomerService.count_by_status — delegates to repo."""

    async def test_count_by_status_empty(self, mock_db_session, mock_customer_repo):
        """Returns empty dict when no customers in tenant."""
        mock_customer_repo.count_by_status = AsyncMock(return_value={})
        service = CustomerService(mock_db_session, mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert result == {}
        mock_customer_repo.count_by_status.assert_awaited_once_with(1)

    async def test_count_by_status_returns_counts(self, mock_db_session, mock_customer_repo):
        """Returns correct count per status."""
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={
                CustomerStatus.LEAD: 3,
                CustomerStatus.OPPORTUNITY: 2,
                CustomerStatus.CUSTOMER: 1,
            }
        )
        service = CustomerService(mock_db_session, mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert result[CustomerStatus.LEAD] == 3
        assert result[CustomerStatus.OPPORTUNITY] == 2
        assert result[CustomerStatus.CUSTOMER] == 1

    async def test_count_by_status_tenant_isolation(self, mock_db_session, mock_customer_repo):
        """Passes correct tenant_id to repository."""
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={CustomerStatus.LEAD: 7}
        )
        service = CustomerService(mock_db_session, mock_customer_repo)
        result = await service.count_by_status(tenant_id=999)
        mock_customer_repo.count_by_status.assert_awaited_once_with(999)
        assert result[CustomerStatus.LEAD] == 7
        assert CustomerStatus.OPPORTUNITY not in result
        assert CustomerStatus.CUSTOMER not in result

    async def test_count_by_status_single_status(self, mock_db_session, mock_customer_repo):
        """Returns one entry when all customers share same status."""
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={CustomerStatus.INACTIVE: 10}
        )
        service = CustomerService(mock_db_session, mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert len(result) == 1
        assert result[CustomerStatus.INACTIVE] == 10

    async def test_count_by_status_invalid_db_status_skipped(
        self, mock_db_session, mock_customer_repo
    ):
        """Repository returns partial counts when some DB rows have invalid status."""
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={CustomerStatus.LEAD: 3}  # unknown statuses silently skipped
        )
        service = CustomerService(mock_db_session, mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert result == {CustomerStatus.LEAD: 3}


@pytest.mark.asyncio
class TestSearchCustomers:
    """Unit tests for CustomerService.search_customers — delegates to repo."""

    async def test_search_customers_empty_keyword_returns_empty(
        self, mock_db_session, mock_customer_repo
    ):
        """Empty keyword is delegated to repository which returns [] for empty string."""
        # search_customers checks the keyword in the repository, not in the service
        mock_customer_repo.search_customers = AsyncMock(return_value=[])
        service = CustomerService(mock_db_session, mock_customer_repo)

        result = await service.search_customers("", tenant_id=1)

        assert result == []
        # Repository is called even for empty keyword (repo handles the short-circuit internally)
        mock_customer_repo.search_customers.assert_awaited_once_with("", 1)

    async def test_search_customers_delegates_to_repo(
        self, mock_db_session, mock_customer_repo
    ):
        """Delegates to CustomerRepository.search_customers."""
        mock_row = MagicMock()
        mock_customer_repo.search_customers = AsyncMock(return_value=[mock_row])
        service = CustomerService(mock_db_session, mock_customer_repo)

        result = await service.search_customers(r"100%_fit\\", tenant_id=1)

        mock_customer_repo.search_customers.assert_awaited_once_with(
            r"100%_fit\\", 1
        )
        assert result == [mock_row]

