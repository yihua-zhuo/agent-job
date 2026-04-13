"""Unit tests for SalesService (pipeline + opportunity CRUD)."""
import pytest
from src.services.sales_service import SalesService
from src.models.opportunity import Stage


@pytest.fixture
def sales_service():
    return SalesService()


@pytest.fixture
async def sample_pipeline(sales_service):
    result = await sales_service.create_pipeline(1, {"name": "Test Pipeline"})
    return result.data["id"]


@pytest.mark.asyncio
class TestSalesServicePipeline:
    async def test_create_and_get_pipeline(self, sales_service):
        result = await sales_service.create_pipeline(1, {"name": "Main Pipeline"})
        assert bool(result) is True
        pipeline = result.data
        assert pipeline["name"] == "Main Pipeline"
        assert "lead" in pipeline["stages"]

        retrieved = await sales_service.get_pipeline(1, pipeline["id"])
        assert bool(retrieved) is True
        assert retrieved.data["id"] == pipeline["id"]

    async def test_create_pipeline_empty_name(self, sales_service):
        result = await sales_service.create_pipeline(1, {"name": ""})
        assert bool(result) is False

    async def test_create_pipeline_duplicate(self, sales_service):
        await sales_service.create_pipeline(1, {"name": "Duplicate"})
        dup = await sales_service.create_pipeline(1, {"name": "Duplicate"})
        assert bool(dup) is False


@pytest.mark.asyncio
class TestSalesServiceOpportunity:
    async def test_create_opportunity(self, sales_service, sample_pipeline):
        result = await sales_service.create_opportunity(1, {
            "name": "Big Deal",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "50000",
        })
        assert bool(result) is True
        assert result.data["name"] == "Big Deal"
        assert result.data["stage"] == "lead"

    async def test_create_opportunity_missing_field(self, sales_service, sample_pipeline):
        result = await sales_service.create_opportunity(1, {
            "name": "Missing Amount",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            # amount missing
        })
        assert bool(result) is False

    async def test_get_opportunity(self, sales_service, sample_pipeline):
        r1 = await sales_service.create_opportunity(1, {
            "name": "Opp A",
            "stage": Stage.QUALIFIED,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "30000",
        })
        opp_id = r1.data["id"]
        result = await sales_service.get_opportunity(1, opp_id)
        assert bool(result) is True
        assert result.data["name"] == "Opp A"

    async def test_get_opportunity_not_found(self, sales_service):
        result = await sales_service.get_opportunity(1, 9999)
        assert bool(result) is False

    async def test_update_opportunity(self, sales_service, sample_pipeline):
        r1 = await sales_service.create_opportunity(1, {
            "name": "Old Name",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "10000",
        })
        opp_id = r1.data["id"]
        result = await sales_service.update_opportunity(1, opp_id, {"name": "New Name"})
        assert bool(result) is True
        assert result.data["name"] == "New Name"

    async def test_change_stage(self, sales_service, sample_pipeline):
        r1 = await sales_service.create_opportunity(1, {
            "name": "Stage Test",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "10000",
        })
        opp_id = r1.data["id"]
        result = await sales_service.change_stage(1, opp_id, Stage.PROPOSAL)
        assert bool(result) is True
        assert result.data["stage"] == Stage.PROPOSAL.value

    async def test_change_stage_invalid(self, sales_service, sample_pipeline):
        r1 = await sales_service.create_opportunity(1, {
            "name": "Bad Stage",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "5000",
        })
        opp_id = r1.data["id"]
        result = await sales_service.change_stage(1, opp_id, "not_a_stage")
        assert bool(result) is False

    async def test_list_opportunities(self, sales_service, sample_pipeline):
        for i in range(3):
            await sales_service.create_opportunity(1, {
                "name": f"Opp{i}",
                "stage": Stage.LEAD,
                "owner_id": 1,
                "customer_id": i + 1,
                "pipeline_id": sample_pipeline,
                "amount": str(10000 * (i + 1)),
            })
        result = await sales_service.list_opportunities(1, page=1, page_size=10)
        assert bool(result) is True
        assert result.data.total == 3
        assert len(result.data.items) == 3

    async def test_list_opportunities_filter_by_stage(self, sales_service, sample_pipeline):
        await sales_service.create_opportunity(1, {
            "name": "Lead Opp",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "10000",
        })
        await sales_service.create_opportunity(1, {
            "name": "Won Opp",
            "stage": Stage.CLOSED_WON,
            "owner_id": 1,
            "customer_id": 2,
            "pipeline_id": sample_pipeline,
            "amount": "20000",
        })
        result = await sales_service.list_opportunities(1, stage=Stage.LEAD)
        assert bool(result) is True
        assert all(o["stage"] == Stage.LEAD.value for o in result.data.items)

    async def test_list_pipelines(self, sales_service):
        await sales_service.create_pipeline(1, {"name": "Pipe A"})
        await sales_service.create_pipeline(1, {"name": "Pipe B"})
        result = await sales_service.list_pipelines(1)
        assert bool(result) is True
        names = [p["name"] for p in result.data["items"]]
        assert "Pipe A" in names
        assert "Pipe B" in names

    async def test_get_pipeline_stats(self, sales_service, sample_pipeline):
        await sales_service.create_opportunity(1, {
            "name": "Stat Test",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "50000",
        })
        result = await sales_service.get_pipeline_stats(1, sample_pipeline)
        assert bool(result) is True
        assert result.data["total"] == 1

    async def test_get_pipeline_funnel(self, sales_service, sample_pipeline):
        result = await sales_service.get_pipeline_funnel(1, sample_pipeline)
        assert bool(result) is True
        assert "stages" in result.data

    async def test_get_forecast(self, sales_service):
        result = await sales_service.get_forecast(1)
        assert bool(result) is True
        assert "forecast" in result.data


@pytest.mark.asyncio
class TestSalesServiceTenantIsolation:
    async def test_get_opportunity_wrong_tenant(self, sales_service, sample_pipeline):
        r1 = await sales_service.create_opportunity(1, {
            "name": "T1 Opp",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "10000",
        })
        opp_id = r1.data["id"]
        # Tenant 2 cannot access
        result = await sales_service.get_opportunity(2, opp_id)
        assert bool(result) is False

    async def test_update_opportunity_wrong_tenant(self, sales_service, sample_pipeline):
        r1 = await sales_service.create_opportunity(1, {
            "name": "T1 Opp",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "10000",
        })
        opp_id = r1.data["id"]
        result = await sales_service.update_opportunity(2, opp_id, {"name": "Hijacked"})
        assert bool(result) is False

    async def test_list_opportunities_tenant_isolation(self, sales_service, sample_pipeline):
        await sales_service.create_opportunity(1, {
            "name": "T1 Opp",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": "10000",
        })
        # Tenant 99 has no opportunities — returns empty, not error
        result = await sales_service.list_opportunities(99)
        assert bool(result) is True
        assert result.data.total == 0
