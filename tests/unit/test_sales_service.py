"""Unit tests for SalesService (pipeline + opportunity CRUD)."""
import pytest
import pytest_asyncio
from services.sales_service import SalesService
from models.opportunity import Stage


@pytest.fixture
def sales_service(mock_db_session):
    return SalesService(mock_db_session)


@pytest_asyncio.fixture
async def sample_pipeline(sales_service):
    result = await sales_service.create_pipeline(1, {"name": "Test Pipeline"})
    return result.data["id"]


@pytest.mark.asyncio
class TestSalesServicePipeline:

    async def test_create_pipeline_empty_name(self, sales_service):
        result = await sales_service.create_pipeline(1, {"name": ""})
        assert bool(result) is False

    async def test_create_pipeline_duplicate(self, sales_service):
        await sales_service.create_pipeline(1, {"name": "Duplicate"})
        dup = await sales_service.create_pipeline(1, {"name": "Duplicate"})
        assert bool(dup) is False


@pytest.mark.asyncio
class TestSalesServiceOpportunity:














    pass
@pytest.mark.asyncio
class TestSalesServiceTenantIsolation:


    pass
