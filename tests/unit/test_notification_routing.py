"""Unit tests for NotificationRoutingService."""

from unittest.mock import MagicMock

import pytest

from pkg.errors.app_exceptions import ValidationException
from services.notification_routing_service import NotificationRoutingService
from tests.unit.conftest import make_mock_session


@pytest.fixture
def mock_db_session():
    return make_mock_session([])


@pytest.fixture
def routing_service(mock_db_session):
    return NotificationRoutingService(mock_db_session)


def _make_notification(priority, user_id=None, email=None):
    n = MagicMock()
    n.priority = priority
    n.user_id = user_id
    n.email = email
    return n


# ---------------------------------------------------------------------------
# Routing rule tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_urgent_routes_to_in_app_and_email(routing_service):
    notification = _make_notification(priority="urgent", user_id=42, email="user@example.com")
    result = await routing_service.route(notification, tenant_id=1)

    assert len(result) == 2
    channels = {r.channel for r in result}
    assert channels == {"in_app", "email"}
    for r in result:
        assert r.status == "routed"
        assert r.priority == "urgent"


@pytest.mark.asyncio
async def test_normal_routes_to_in_app_only(routing_service):
    notification = _make_notification(priority="normal", user_id=42)
    result = await routing_service.route(notification, tenant_id=1)

    assert len(result) == 1
    assert result[0].channel == "in_app"
    assert result[0].status == "routed"


@pytest.mark.asyncio
async def test_low_routes_to_batch(routing_service):
    notification = _make_notification(priority="low")
    result = await routing_service.route(notification, tenant_id=1)

    assert len(result) == 1
    assert result[0].channel == "batch"
    assert result[0].target == "daily_digest"
    assert result[0].status == "pending"


@pytest.mark.asyncio
async def test_unknown_priority_raises(routing_service):
    notification = _make_notification(priority="invalid")
    with pytest.raises(ValidationException) as exc_info:
        await routing_service.route(notification, tenant_id=1)
    assert "invalid" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tenant_id_carried_on_all_records(routing_service):
    notification = _make_notification(priority="urgent", user_id=7, email="nine@example.com")
    result = await routing_service.route(notification, tenant_id=99)

    assert len(result) == 2
    for r in result:
        assert r.tenant_id == 99


@pytest.mark.asyncio
async def test_normal_without_user_id_returns_empty_list(routing_service):
    notification = _make_notification(priority="normal", user_id=None)
    result = await routing_service.route(notification, tenant_id=1)

    assert result == []
