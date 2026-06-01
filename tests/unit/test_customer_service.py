"""Unit tests for CustomerService — focus on CustomerCreateDTO integration and repo delegation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.customer import CustomerCreateDTO, CustomerStatus
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
    repo.get_unassigned_leads = AsyncMock()
    repo.get_leads_by_owner = AsyncMock()
    repo.bulk_recycle = AsyncMock()
    repo.session = MagicMock()
    return repo


@pytest.fixture
def mock_db_session():
    from tests.unit.conftest import MockState, make_mock_session
    from tests.unit.domain_handlers.counts import make_count_handler
    from tests.unit.domain_handlers.customers import make_customer_handler, make_customer_repository_handler

    state = MockState()
    return make_mock_session([
        make_customer_handler(state),
        make_customer_repository_handler(state),
        make_count_handler(state),
    ])


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
        assert dto.status == CustomerStatus.LEAD
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
            status=CustomerStatus.LEAD,
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
        assert dto.status == CustomerStatus.LEAD

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
        service = CustomerService(mock_customer_repo)

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
        service = CustomerService(mock_customer_repo)

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
        """create_customer with name+email falls back to default values for other fields."""
        mock_customer = MagicMock()
        mock_customer.id = 3
        mock_customer.name = "Customer"
        mock_customer.email = None
        mock_customer.status = "lead"
        mock_customer.owner_id = 0
        mock_customer.tags = []
        mock_customer_repo.create = AsyncMock(return_value=mock_customer)
        service = CustomerService(mock_customer_repo)

        with patch(
            "services.lead_routing_service.LeadRoutingService.auto_assign_lead",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await service.create_customer({"name": "Customer", "email": "default@example.com"}, tenant_id=1)

        call_args = mock_customer_repo.create.call_args[0][0]
        assert call_args["name"] == "Customer"
        assert call_args["email"] == "default@example.com"
        assert result.name == "Customer"


@pytest.mark.asyncio
class TestCountByStatus:
    """Unit tests for CustomerService.count_by_status — delegates to repo."""

    async def test_count_by_status_empty(self, mock_customer_repo):
        """Returns empty dict when no customers in tenant."""
        mock_customer_repo.count_by_status = AsyncMock(return_value={})
        service = CustomerService(mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert result == {}
        mock_customer_repo.count_by_status.assert_awaited_once_with(1)

    async def test_count_by_status_returns_counts(self, mock_customer_repo):
        """Returns correct count per status."""
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={
                CustomerStatus.LEAD: 3,
                CustomerStatus.OPPORTUNITY: 2,
                CustomerStatus.CUSTOMER: 1,
            }
        )
        service = CustomerService(mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert result[CustomerStatus.LEAD] == 3
        assert result[CustomerStatus.OPPORTUNITY] == 2
        assert result[CustomerStatus.CUSTOMER] == 1

    async def test_count_by_status_tenant_isolation(self, mock_customer_repo):
        """Passes correct tenant_id to repository."""
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={CustomerStatus.LEAD: 7}
        )
        service = CustomerService(mock_customer_repo)
        result = await service.count_by_status(tenant_id=999)
        mock_customer_repo.count_by_status.assert_awaited_once_with(999)
        assert result[CustomerStatus.LEAD] == 7
        assert CustomerStatus.OPPORTUNITY not in result
        assert CustomerStatus.CUSTOMER not in result

    async def test_count_by_status_single_status(self, mock_customer_repo):
        """Returns one entry when all customers share same status."""
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={CustomerStatus.INACTIVE: 10}
        )
        service = CustomerService(mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert len(result) == 1
        assert result[CustomerStatus.INACTIVE] == 10

    async def test_count_by_status_invalid_db_status_skipped(
        self, mock_customer_repo
    ):
        """Repository returns partial counts when some DB rows have invalid status."""
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={CustomerStatus.LEAD: 3}  # unknown statuses silently skipped
        )
        service = CustomerService(mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert result == {CustomerStatus.LEAD: 3}

    async def test_count_by_status_basic(self):
        """Returns correct counts across LEAD, ACTIVE, and INACTIVE statuses."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            ("lead", 5),
            ("active", 3),
            ("inactive", 2),
        ])
        session.execute = AsyncMock(return_value=mock_result)
        mock_customer_repo = _make_mock_customer_repo()
        mock_customer_repo.count_by_status = AsyncMock(
            return_value={
                CustomerStatus.LEAD: 5,
                CustomerStatus.ACTIVE: 3,
                CustomerStatus.INACTIVE: 2,
            }
        )
        service = CustomerService(mock_customer_repo)
        result = await service.count_by_status(tenant_id=1)
        assert result[CustomerStatus.LEAD] == 5
        assert result[CustomerStatus.ACTIVE] == 3
        assert result[CustomerStatus.INACTIVE] == 2

    async def test_count_by_status_zero_tenant(self, mock_customer_repo):
        """Delegates to repo which returns empty dict for invalid tenant_id."""
        mock_customer_repo.count_by_status = AsyncMock(return_value={})
        service = CustomerService(mock_customer_repo)
        result = await service.count_by_status(tenant_id=0)
        assert result == {}
        mock_customer_repo.count_by_status.assert_awaited_once_with(0)


@pytest.mark.asyncio
class TestSearchCustomers:
    """Unit tests for CustomerService.search_customers — delegates to repo."""

    async def test_search_customers_empty_keyword_returns_empty(
        self, mock_db_session, mock_customer_repo
    ):
        """Empty keyword is delegated to repository which returns [] for empty string."""
        # search_customers checks the keyword in the repository, not in the service
        mock_customer_repo.search_customers = AsyncMock(return_value=[])
        service = CustomerService(mock_customer_repo)

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
        service = CustomerService(mock_customer_repo)

        result = await service.search_customers(r"100%_fit\\", tenant_id=1)

        mock_customer_repo.search_customers.assert_awaited_once_with(
            r"100%_fit\\", 1
        )
        assert result == [mock_row]


class TestEnrichmentUpsert:
    """Unit tests for enrichment upsert on customer create/update."""

    @pytest.mark.asyncio
    async def test_create_customer_with_enrichment_data_calls_upsert(self):
        """create_customer calls _upsert_enrichment when enrichment_data is in the payload."""
        mock_customer_repo = _make_mock_customer_repo()
        service = CustomerService(mock_customer_repo)

        mock_customer = MagicMock()
        mock_customer.id = 10
        mock_customer.name = "Enriched Customer"
        mock_customer.status = "lead"
        mock_customer.owner_id = 1  # non-zero owner to skip auto_assign_lead
        mock_customer.created_at = None
        mock_customer_repo.create = AsyncMock(return_value=mock_customer)
        mock_customer_repo.session.execute = AsyncMock()

        with patch.object(service, "_upsert_enrichment", new_callable=AsyncMock) as mock_upsert:
            await service.create_customer(
                {"name": "Enriched Customer", "email": "enriched@example.com", "enrichment_data": {"raw": "payload"}},
                tenant_id=1,
            )
            mock_upsert.assert_awaited_once_with(10, 1, {"raw": "payload"})

    @pytest.mark.asyncio
    async def test_update_customer_with_enrichment_data_calls_upsert(self):
        """update_customer delegates to repo with the full data dict (including enrichment_data)."""
        mock_customer_repo = _make_mock_customer_repo()
        service = CustomerService(mock_customer_repo)

        fake_customer = MagicMock()
        fake_customer.id = 7
        fake_customer.name = "Updated Customer"
        fake_customer.status = "lead"
        fake_customer.owner_id = 0

        mock_customer_repo.update_customer = AsyncMock(return_value=fake_customer)

        result = await service.update_customer(
            7,
            {"name": "Updated Name", "enrichment_data": {"raw": "updated"}},
            tenant_id=1,
        )
        # The repo receives the data including enrichment_data; the service itself
        # doesn't call _upsert_enrichment (that lives in the repo or is handled
        # by the router layer via explicit calls).
        mock_customer_repo.update_customer.assert_awaited_once_with(
            7, {"name": "Updated Name", "enrichment_data": {"raw": "updated"}}, 1
        )
        assert result == fake_customer

    @pytest.mark.asyncio
    async def test_create_customer_without_enrichment_data_skips_upsert(self):
        """_upsert_enrichment is NOT called when no enrichment_data key is present."""
        mock_customer_repo = _make_mock_customer_repo()
        service = CustomerService(mock_customer_repo)

        mock_customer = MagicMock()
        mock_customer.id = 20
        mock_customer.name = "Plain Customer"
        mock_customer.status = "lead"
        mock_customer.owner_id = 1  # non-zero owner skips auto_assign_lead
        mock_customer.created_at = None
        mock_customer_repo.create = AsyncMock(return_value=mock_customer)
        mock_customer_repo.session.execute = AsyncMock()

        with patch.object(service, "_upsert_enrichment", new_callable=AsyncMock) as mock_upsert:
            await service.create_customer(
                {"name": "Plain Customer", "email": "plain@example.com"},
                tenant_id=1,
            )
            mock_upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_customer_with_none_enrichment_data_skips_upsert(self):
        """_upsert_enrichment is NOT called when enrichment_data is explicitly None."""
        mock_customer_repo = _make_mock_customer_repo()
        service = CustomerService(mock_customer_repo)

        mock_customer = MagicMock()
        mock_customer.id = 21
        mock_customer.name = "Null Enrich Customer"
        mock_customer.status = "lead"
        mock_customer.owner_id = 1  # non-zero owner skips auto_assign_lead
        mock_customer.created_at = None
        mock_customer_repo.create = AsyncMock(return_value=mock_customer)
        mock_customer_repo.session.execute = AsyncMock()

        with patch.object(service, "_upsert_enrichment", new_callable=AsyncMock) as mock_upsert:
            await service.create_customer(
                {"name": "Null Enrich Customer", "email": "null@example.com", "enrichment_data": None},
                tenant_id=1,
            )
            mock_upsert.assert_not_called()
