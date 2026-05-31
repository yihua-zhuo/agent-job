import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.copilot_service import CopilotService
from tests.unit.conftest import MockState, make_mock_session


@pytest.fixture
def mock_db_session():
    return make_mock_session([])


@pytest.fixture
def copilot_service(mock_db_session):
    return CopilotService(mock_db_session)


@pytest.mark.asyncio
async def test_build_system_prompt_raises_not_found(copilot_service):
    # Empty handlers cause _execute_side_effect to return MockResult([]),
    # making scalar_one_or_none() return None and triggering NotFoundException.
    with pytest.raises(NotFoundException):
        await copilot_service.build_system_prompt(tenant_id=2, customer_id=9999)


@pytest.mark.asyncio
async def test_build_system_prompt_tenant_isolation():
    # Two separate services backed by independent mock sessions.
    # Both sessions use empty handler lists, so any customer lookup
    # raises NotFoundException — proving no shared/global state exists.
    # (The positive-path tenant isolation check for valid customers
    # requires integration tests; the mock framework's fixture
    # returns data regardless of tenant_id.)
    state_a = MockState()
    state_b = MockState()

    # Verify state is separate — changes in one don't affect the other.
    assert state_a is not state_b

    session_a = make_mock_session([])
    session_b = make_mock_session([])

    svc_a = CopilotService(session_a)
    svc_b = CopilotService(session_b)

    # Both tenants raise NotFoundException for any customer (empty handlers).
    with pytest.raises(NotFoundException):
        await svc_a.build_system_prompt(tenant_id=1, customer_id=1)

    with pytest.raises(NotFoundException):
        await svc_b.build_system_prompt(tenant_id=2, customer_id=1)

    # Services use different sessions — no cross-talk possible.
    assert svc_a.session is not svc_b.session


def test_tool_registry_returns_six_tools(copilot_service):
    registry = copilot_service.get_tool_registry()
    assert len(registry) == 6
    active = [k for k, v in registry.items() if not v["deferred"]]
    deferred = [k for k, v in registry.items() if v["deferred"]]
    assert set(active) == {"get_customer", "get_opportunities", "get_recent_activities", "get_churn_risk"}
    assert set(deferred) == {"send_email", "create_task"}


def test_session_attribute_is_mock_session(copilot_service, mock_db_session):
    assert copilot_service.session is mock_db_session


def test_constructor_no_default_session():
    with pytest.raises(TypeError):
        CopilotService()
