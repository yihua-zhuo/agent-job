"""Unit tests for CustomerService."""
import pytest
from services.customer_service import CustomerService
from models.customer import CustomerStatus


@pytest.fixture
def customer_service(mock_db_session):
    return CustomerService(mock_db_session)


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


# ---------------------------------------------------------------------------
# Tests for _row_to_dict — updated in this PR to accept Row or RowMapping
# ---------------------------------------------------------------------------

class TestRowToDict:
    """Tests for CustomerService._row_to_dict() — supports both Row and RowMapping inputs."""

    def test_converts_mock_row_with_mapping_attr(self):
        """Rows that have a _mapping attribute (MockRow) are converted correctly."""
        from tests.unit.conftest import MockRow
        row = MockRow({
            "id": 1, "tenant_id": 10,
            "name": "Alice", "email": "alice@example.com",
            "phone": None, "company": None,
            "status": "lead", "owner_id": 5,
            "tags": [], "created_at": None, "updated_at": None,
        })
        result = CustomerService._row_to_dict(row)
        assert result["id"] == 1
        assert result["name"] == "Alice"
        assert result["status"] == "lead"

    def test_converts_plain_dict_without_mapping_attr(self):
        """Plain dicts (no _mapping attr) are handled via getattr fallback."""
        plain = {
            "id": 2, "tenant_id": 5,
            "name": "Bob", "email": None,
            "phone": None, "company": None,
            "status": "customer", "owner_id": 0,
            "tags": ["vip"], "created_at": None, "updated_at": None,
        }
        result = CustomerService._row_to_dict(plain)
        assert result["id"] == 2
        assert result["status"] == "customer"
        assert result["tags"] == ["vip"]

    def test_serializes_datetime_fields(self):
        """created_at and updated_at datetime objects are converted to ISO strings."""
        from datetime import datetime
        from tests.unit.conftest import MockRow
        now = datetime(2024, 6, 1, 12, 0, 0)
        row = MockRow({
            "id": 1, "tenant_id": 1, "name": "X",
            "email": None, "phone": None, "company": None,
            "status": "lead", "owner_id": 1,
            "tags": [], "created_at": now, "updated_at": now,
        })
        result = CustomerService._row_to_dict(row)
        assert result["created_at"] == now.isoformat()
        assert result["updated_at"] == now.isoformat()

    def test_none_datetime_stays_none(self):
        """None datetime fields are left as None (not converted)."""
        from tests.unit.conftest import MockRow
        row = MockRow({
            "id": 1, "tenant_id": 1, "name": "Y",
            "email": None, "phone": None, "company": None,
            "status": "lead", "owner_id": 1,
            "tags": [], "created_at": None, "updated_at": None,
        })
        result = CustomerService._row_to_dict(row)
        assert result["created_at"] is None
        assert result["updated_at"] is None

    def test_status_enum_value_is_extracted(self):
        """If status is an enum with a .value, the .value is used."""
        from tests.unit.conftest import MockRow
        from models.customer import CustomerStatus
        row = MockRow({
            "id": 1, "tenant_id": 1, "name": "Z",
            "email": None, "phone": None, "company": None,
            "status": CustomerStatus.LEAD, "owner_id": 1,
            "tags": [], "created_at": None, "updated_at": None,
        })
        result = CustomerService._row_to_dict(row)
        assert result["status"] == "lead"


# ---------------------------------------------------------------------------
# Tests for mappings().one_or_none() usage in service methods (new API)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCustomerServiceMappingsUsage:
    """Verify service methods handle the new result.mappings().one_or_none() pattern."""

    async def test_get_customer_found(self, customer_service):
        """get_customer returns success for the fixture id=1."""
        result = await customer_service.get_customer(1, tenant_id=1)
        assert bool(result) is True
        assert result.data["id"] == 1

    async def test_get_customer_not_found(self, customer_service):
        """get_customer returns error for an id that doesn't exist in mock."""
        result = await customer_service.get_customer(9999, tenant_id=1)
        assert bool(result) is False

    async def test_update_customer_found(self, customer_service):
        """update_customer succeeds for id=1 (fixture row exists)."""
        result = await customer_service.update_customer(
            1, {"name": "Updated Name"}, tenant_id=1
        )
        assert bool(result) is True

    async def test_update_customer_not_found(self, customer_service):
        """update_customer returns error for non-existent id."""
        result = await customer_service.update_customer(
            9999, {"name": "X"}, tenant_id=1
        )
        assert bool(result) is False

    async def test_delete_customer_success(self, customer_service):
        """delete_customer returns success for a valid deletion."""
        result = await customer_service.delete_customer(1, tenant_id=1)
        assert bool(result) is True

    async def test_add_tag_not_found(self, customer_service):
        """add_tag returns error when customer does not exist."""
        result = await customer_service.add_tag(9999, "vip", tenant_id=1)
        assert bool(result) is False

    async def test_add_tag_existing_customer(self, customer_service):
        """add_tag succeeds for the fixture customer (id=1)."""
        result = await customer_service.add_tag(1, "premium", tenant_id=1)
        assert bool(result) is True

    async def test_remove_tag_not_found(self, customer_service):
        """remove_tag returns error when customer does not exist."""
        result = await customer_service.remove_tag(9999, "vip", tenant_id=1)
        assert bool(result) is False

    async def test_change_status_not_found(self, customer_service):
        """change_status returns error when customer does not exist."""
        result = await customer_service.change_status(9999, "active", tenant_id=1)
        assert bool(result) is False

    async def test_change_status_success(self, customer_service):
        """change_status succeeds for fixture customer (id=1)."""
        result = await customer_service.change_status(1, "active", tenant_id=1)
        assert bool(result) is True

    async def test_assign_owner_not_found(self, customer_service):
        """assign_owner returns error when customer does not exist."""
        result = await customer_service.assign_owner(9999, 5, tenant_id=1)
        assert bool(result) is False

    async def test_assign_owner_success(self, customer_service):
        """assign_owner succeeds for fixture customer (id=1)."""
        result = await customer_service.assign_owner(1, 5, tenant_id=1)
        assert bool(result) is True

    async def test_list_customers_returns_paginated(self, customer_service):
        """list_customers returns data with pagination fields."""
        result = await customer_service.list_customers(page=1, page_size=20, tenant_id=1)
        assert bool(result) is True
        # result.data is a PaginatedData Pydantic model, not a plain dict
        assert hasattr(result.data, "items")
        assert hasattr(result.data, "total")
        assert hasattr(result.data, "page")

    async def test_search_customers_returns_keyword_and_items(self, customer_service):
        """search_customers returns data with keyword and items keys."""
        result = await customer_service.search_customers("test", tenant_id=1)
        assert bool(result) is True
        assert "keyword" in result.data
        assert "items" in result.data

    async def test_bulk_import_partial_success(self, customer_service):
        """bulk_import reports correct imported count on full success."""
        customers = [
            {"name": f"Customer {i}", "email": f"c{i}@test.com", "owner_id": 1}
            for i in range(2)
        ]
        result = await customer_service.bulk_import(customers, tenant_id=1)
        assert bool(result) is True
        assert result.data["imported"] == 2


# ---------------------------------------------------------------------------
# ORM model lazy="raise" relationship configuration tests
# ---------------------------------------------------------------------------

class TestLazyRaiseRelationships:
    """Verify that relationships have lazy='raise' configured (prevents N+1 queries)."""

    def test_pipeline_stages_relationship_is_lazy_raise(self):
        """PipelineModel.stages must use lazy='raise' to enforce explicit loading."""
        from sqlalchemy import inspect
        from db.models.pipeline import PipelineModel
        mapper = inspect(PipelineModel)
        stages_rel = mapper.relationships["stages"]
        assert stages_rel.lazy == "raise"

    def test_pipeline_stage_pipeline_relationship_is_lazy_raise(self):
        """PipelineStageModel.pipeline must use lazy='raise'."""
        from sqlalchemy import inspect
        from db.models.pipeline_stage import PipelineStageModel
        mapper = inspect(PipelineStageModel)
        pipeline_rel = mapper.relationships["pipeline"]
        assert pipeline_rel.lazy == "raise"

    def test_campaign_events_relationship_is_lazy_raise(self):
        """CampaignModel.events must use lazy='raise'."""
        from sqlalchemy import inspect
        from db.models.marketing import CampaignModel
        mapper = inspect(CampaignModel)
        events_rel = mapper.relationships["events"]
        assert events_rel.lazy == "raise"

    def test_campaign_event_campaign_relationship_is_lazy_raise(self):
        """CampaignEventModel.campaign must use lazy='raise'."""
        from sqlalchemy import inspect
        from db.models.marketing import CampaignEventModel
        mapper = inspect(CampaignEventModel)
        campaign_rel = mapper.relationships["campaign"]
        assert campaign_rel.lazy == "raise"





