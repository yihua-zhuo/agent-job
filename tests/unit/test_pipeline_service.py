"""Unit tests for PipelineService."""
import pytest
import pytest_asyncio
from services.pipeline_service import PipelineService


@pytest.fixture
def pipeline_service(mock_get_db_session):
    return PipelineService(mock_get_db_session)


@pytest_asyncio.fixture
async def sample_pipeline(mock_get_db_session):
    svc = PipelineService(mock_get_db_session)
    result = await svc.create_pipeline(tenant_id=1, data={"name": "Test Pipeline"})
    return result.data["id"]


@pytest_asyncio.fixture
async def sample_pipeline_2(mock_get_db_session):
    svc = PipelineService(mock_get_db_session)
    result = await svc.create_pipeline(tenant_id=2, data={"name": "Tenant 2 Pipeline"})
    return result.data["id"]


@pytest.mark.asyncio
class TestPipelineService:


    async def test_create_pipeline_empty_name(self, pipeline_service):
        result = await pipeline_service.create_pipeline(tenant_id=1, data={})
        assert bool(result) is False

    async def test_create_pipeline_duplicate_name(self, pipeline_service):
        await pipeline_service.create_pipeline(tenant_id=1, data={"name": "Dup"})
        dup = await pipeline_service.create_pipeline(tenant_id=1, data={"name": "Dup"})
        assert bool(dup) is False









    async def test_update_pipeline_not_found(self, pipeline_service):
        result = await pipeline_service.update_pipeline(
            tenant_id=1, pipeline_id=9999, data={"name": "X"}
        )
        assert bool(result) is False




@pytest.mark.asyncio
class TestPipelineServiceStageCRUD:








    pass
@pytest.mark.asyncio
class TestPipelineServiceTenantIsolation:



    pass
