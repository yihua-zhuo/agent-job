"""Unit tests for PipelineService."""
import pytest
import pytest_asyncio
from services.pipeline_service import PipelineService
from pkg.errors.app_exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from tests.unit.conftest import (
    make_mock_session,
    pipeline_handler,
    make_count_handler,
    MockResult,
    MockState,
)


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([pipeline_handler, make_count_handler(state)])


def _empty_pipeline_handler(sql_text, params):
    """Pipeline handler that always returns empty results (simulates 'not found')."""
    if "pipelines" in sql_text or "pipeline_stages" in sql_text:
        return MockResult([])
    return None


@pytest.fixture
def mock_db_session_empty_pipeline():
    """Session where pipeline lookups always return empty (not found)."""
    state = MockState()
    return make_mock_session([_empty_pipeline_handler, make_count_handler(state)])


@pytest.fixture
def pipeline_service(mock_db_session):
    return PipelineService(mock_db_session)


@pytest.fixture
def pipeline_service_empty(mock_db_session_empty_pipeline):
    return PipelineService(mock_db_session_empty_pipeline)


@pytest.mark.asyncio
class TestPipelineService:

    async def test_create_pipeline_empty_name(self, pipeline_service):
        with pytest.raises(ValidationException):
            await pipeline_service.create_pipeline(tenant_id=1, data={})

    async def test_create_pipeline_duplicate_name(self, pipeline_service):
        # The mock always returns a row for any 'from pipelines' query,
        # so the duplicate-name check triggers immediately.
        with pytest.raises(ConflictException):
            await pipeline_service.create_pipeline(tenant_id=1, data={"name": "Dup"})

    async def test_update_pipeline_not_found(self, pipeline_service_empty):
        with pytest.raises(NotFoundException):
            await pipeline_service_empty.update_pipeline(
                tenant_id=1, pipeline_id=9999, data={"name": "X"}
            )


@pytest.mark.asyncio
class TestPipelineServiceStageCRUD:
    pass


@pytest.mark.asyncio
class TestPipelineServiceTenantIsolation:
    pass
