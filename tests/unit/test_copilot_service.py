import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.copilot_service import CopilotService
from tests.unit.conftest import make_mock_session


@pytest.fixture
def mock_db_session():
    return make_mock_session([])


@pytest.fixture
def copilot_service(mock_db_session):
    return CopilotService(mock_db_session)


@pytest.mark.asyncio
async def test_build_system_prompt_raises_not_found(copilot_service):
    with pytest.raises(NotFoundException):
        await copilot_service.build_system_prompt(tenant_id=1, customer_id=9999)


def test_tool_registry_returns_six_tools(copilot_service):
    registry = copilot_service.get_tool_registry()
    assert len(registry) == 6
    active = [k for k, v in registry.items() if not v["deferred"]]
    deferred = [k for k, v in registry.items() if v["deferred"]]
    assert set(active) == {"get_customer", "get_opportunities", "get_recent_activities", "get_churn_risk"}
    assert set(deferred) == {"send_email", "create_task"}


def test_constructor_no_default_session(copilot_service, mock_db_session):
    assert copilot_service.session is mock_db_session
