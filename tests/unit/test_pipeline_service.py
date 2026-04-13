"""Unit tests for PipelineService."""
import pytest
import pytest_asyncio
from services.pipeline_service import PipelineService


@pytest.fixture
def pipeline_service():
    return PipelineService()


@pytest_asyncio.fixture
async def sample_pipeline():
    svc = PipelineService()
    result = await svc.create_pipeline(tenant_id=1, data={"Name": "Test Pipeline"})
    return result.data["id"]


@pytest_asyncio.fixture
async def sample_pipeline_2():
    svc = PipelineService()
    result = await svc.create_pipeline(tenant_id=2, data={"name": "Tenant 2 Pipeline"})
    return result.data["id"]


@pytest.mark.asyncio
class TestPipelineService:
    async def test_create_pipeline(self, pipeline_service):
        result = await pipeline_service.create_pipeline(
            tenant_id=1, data={"name": "My Pipeline"}
        )
        assert bool(result) is True
        assert result.data["name"] == "My Pipeline"
        assert len(result.data["stages"]) == 5
        assert "lead" in [s["name"] for s in result.data["stages"]]

    async def test_create_pipeline_custom_stages(self, pipeline_service):
        result = await pipeline_service.create_pipeline(
            tenant_id=1,
            data={"name": "Custom Stages", "stages": ["s1", "s2", "s3"]},
        )
        assert bool(result) is True
        stage_names = [s["name"] for s in result.data["stages"]]
        assert stage_names == ["s1", "s2", "s3"]

    async def test_create_pipeline_empty_name(self, pipeline_service):
        result = await pipeline_service.create_pipeline(tenant_id=1, data={})
        assert bool(result) is False

    async def test_create_pipeline_duplicate_name(self, pipeline_service):
        await pipeline_service.create_pipeline(tenant_id=1, data={"name": "Dup"})
        dup = await pipeline_service.create_pipeline(tenant_id=1, data={"name": "Dup"})
        assert bool(dup) is False

    async def test_get_pipeline(self, pipeline_service):
        create = await pipeline_service.create_pipeline(tenant_id=1, data={"name": "Get Me"})
        pid = create.data["id"]
        result = await pipeline_service.get_pipeline(tenant_id=1, pipeline_id=pid)
        assert bool(result) is True
        assert result.data["name"] == "Get Me"

    async def test_get_pipeline_not_found(self, pipeline_service):
        result = await pipeline_service.get_pipeline(tenant_id=1, pipeline_id=9999)
        assert bool(result) is False

    async def test_get_pipeline_wrong_tenant(self, pipeline_service, sample_pipeline):
        result = await pipeline_service.get_pipeline(tenant_id=99, pipeline_id=sample_pipeline)
        assert bool(result) is False

    async def test_list_pipelines(self, pipeline_service):
        await pipeline_service.create_pipeline(tenant_id=1, data={"name": "P1"})
        await pipeline_service.create_pipeline(tenant_id=1, data={"name": "P2"})
        result = await pipeline_service.list_pipelines(tenant_id=1)
        assert bool(result) is True
        assert result.data.total >= 2
        names = [p["name"] for p in result.data.items]
        assert "P1" in names
        assert "P2" in names

    async def test_list_pipelines_empty(self, pipeline_service):
        result = await pipeline_service.list_pipelines(tenant_id=9999)
        assert bool(result) is True
        assert result.data.total == 0

    async def test_list_pipelines_pagination(self, pipeline_service):
        for i in range(3):
            await pipeline_service.create_pipeline(tenant_id=1, data={"name": f"Page{i}"})
        result = await pipeline_service.list_pipelines(tenant_id=1, page=1, page_size=2)
        assert bool(result) is True
        assert len(result.data.items) == 2
        assert result.data.total >= 3

    async def test_update_pipeline(self, pipeline_service):
        create = await pipeline_service.create_pipeline(tenant_id=1, data={"name": "Old"})
        pid = create.data["id"]
        result = await pipeline_service.update_pipeline(
            tenant_id=1, pipeline_id=pid, data={"name": "New"}
        )
        assert bool(result) is True
        assert result.data["name"] == "New"

    async def test_update_pipeline_duplicate_name(self, pipeline_service):
        await pipeline_service.create_pipeline(tenant_id=1, data={"name": "NameA"})
        create2 = await pipeline_service.create_pipeline(tenant_id=1, data={"name": "NameB"})
        pid2 = create2.data["id"]
        dup = await pipeline_service.update_pipeline(
            tenant_id=1, pipeline_id=pid2, data={"name": "NameA"}
        )
        assert bool(dup) is False

    async def test_update_pipeline_not_found(self, pipeline_service):
        result = await pipeline_service.update_pipeline(
            tenant_id=1, pipeline_id=9999, data={"name": "X"}
        )
        assert bool(result) is False

    async def test_delete_pipeline(self, pipeline_service):
        create = await pipeline_service.create_pipeline(tenant_id=1, data={"name": "ToDelete"})
        pid = create.data["id"]
        result = await pipeline_service.delete_pipeline(tenant_id=1, pipeline_id=pid)
        assert bool(result) is True
        gone = await pipeline_service.get_pipeline(tenant_id=1, pipeline_id=pid)
        assert bool(gone) is False

    async def test_delete_pipeline_wrong_tenant(self, pipeline_service, sample_pipeline):
        result = await pipeline_service.delete_pipeline(tenant_id=99, pipeline_id=sample_pipeline)
        assert bool(result) is False


@pytest.mark.asyncio
class TestPipelineServiceStageCRUD:
    async def test_add_stage(self, pipeline_service, sample_pipeline):
        result = await pipeline_service.add_stage(
            tenant_id=1, pipeline_id=sample_pipeline, data={"name": "New Stage"}
        )
        assert bool(result) is True
        assert result.data["name"] == "New Stage"

    async def test_add_stage_empty_name(self, pipeline_service, sample_pipeline):
        result = await pipeline_service.add_stage(
            tenant_id=1, pipeline_id=sample_pipeline, data={}
        )
        assert bool(result) is False

    async def test_add_stage_pipeline_not_found(self, pipeline_service):
        result = await pipeline_service.add_stage(
            tenant_id=1, pipeline_id=9999, data={"name": "X"}
        )
        assert bool(result) is False

    async def test_update_stage(self, pipeline_service, sample_pipeline):
        stages = await pipeline_service.get_pipeline(tenant_id=1, pipeline_id=sample_pipeline)
        stage_id = stages.data["stages"][0]["id"]
        result = await pipeline_service.update_stage(
            tenant_id=1, pipeline_id=sample_pipeline, stage_id=stage_id,
            data={"name": "Renamed"}
        )
        assert bool(result) is True
        assert result.data["name"] == "Renamed"

    async def test_update_stage_not_found(self, pipeline_service, sample_pipeline):
        result = await pipeline_service.update_stage(
            tenant_id=1, pipeline_id=sample_pipeline, stage_id=9999, data={"name": "X"}
        )
        assert bool(result) is False

    async def test_delete_stage(self, pipeline_service, sample_pipeline):
        stages = await pipeline_service.get_pipeline(tenant_id=1, pipeline_id=sample_pipeline)
        stage_id = stages.data["stages"][0]["id"]
        result = await pipeline_service.delete_stage(
            tenant_id=1, pipeline_id=sample_pipeline, stage_id=stage_id
        )
        assert bool(result) is True

    async def test_reorder_stages(self, pipeline_service, sample_pipeline):
        stages = await pipeline_service.get_pipeline(tenant_id=1, pipeline_id=sample_pipeline)
        stage_ids = [s["id"] for s in reversed(stages.data["stages"])]
        result = await pipeline_service.reorder_stages(
            tenant_id=1, pipeline_id=sample_pipeline, stage_ids=stage_ids
        )
        assert bool(result) is True


@pytest.mark.asyncio
class TestPipelineServiceTenantIsolation:
    async def test_get_pipeline_cross_tenant_rejected(self, pipeline_service, sample_pipeline_2):
        result = await pipeline_service.get_pipeline(tenant_id=99, pipeline_id=sample_pipeline_2)
        assert bool(result) is False

    async def test_update_pipeline_cross_tenant_rejected(self, pipeline_service, sample_pipeline):
        result = await pipeline_service.update_pipeline(
            tenant_id=99, pipeline_id=sample_pipeline, data={"name": "Hijacked"}
        )
        assert bool(result) is False

    async def test_delete_pipeline_cross_tenant_rejected(self, pipeline_service, sample_pipeline):
        result = await pipeline_service.delete_pipeline(tenant_id=99, pipeline_id=sample_pipeline)
        assert bool(result) is False

    async def test_add_stage_cross_tenant_rejected(self, pipeline_service, sample_pipeline):
        result = await pipeline_service.add_stage(
            tenant_id=99, pipeline_id=sample_pipeline, data={"name": "X"}
        )
        assert bool(result) is False
