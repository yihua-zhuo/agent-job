"""Unit tests for NotificationAnalyticsService."""

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.notification_analytics_service import NotificationAnalyticsService
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.notification import make_notification_analytics_handler


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_notification_analytics_handler(state)], state=state)


@pytest.fixture
def service(mock_db_session):
    return NotificationAnalyticsService(mock_db_session)


class TestTrackOpen:
    async def test_track_open_creates_record(self, mock_db_session, service):
        """track_open creates an analytics record with opened_at set."""
        # Pre-seed a notification analytics record in the mock DB
        state = mock_db_session._state
        state._notification_analytics = {
            (10, 1): {
                "id": 1,
                "notification_id": 10,
                "tenant_id": 1,
                "opened_at": None,
                "clicked_at": None,
                "channel": "email",
            }
        }

        result = await service.track_open(notification_id=10, tenant_id=1)

        assert result.notification_id == 10
        assert result.tenant_id == 1
        assert result.opened_at is not None

    async def test_track_open_upsert(self, mock_db_session, service):
        """track_open called twice does not create two rows; second call updates opened_at."""
        state = mock_db_session._state
        state._notification_analytics = {
            (10, 1): {
                "id": 1,
                "notification_id": 10,
                "tenant_id": 1,
                "opened_at": None,
                "clicked_at": None,
                "channel": "email",
            }
        }

        first = await service.track_open(notification_id=10, tenant_id=1)
        second = await service.track_open(notification_id=10, tenant_id=1)

        assert first.id == second.id
        assert len(state._notification_analytics) == 1

    async def test_track_open_not_found(self, mock_db_session, service):
        """track_open with unknown notification_id raises NotFoundException."""
        with pytest.raises(NotFoundException) as exc_info:
            await service.track_open(notification_id=9999, tenant_id=1)
        assert "Notification" in str(exc_info.value.detail)


class TestGetOpenRate:
    async def test_get_open_rate_no_records(self, mock_db_session, service):
        """get_open_rate returns 0.0 when no analytics exist."""
        rate = await service.get_open_rate(notification_id=10, tenant_id=1)
        assert rate == 0.0

    async def test_get_open_rate_with_records(self, mock_db_session, service):
        """get_open_rate returns a positive float when at least one opened record exists."""
        state = mock_db_session._state
        from datetime import UTC, datetime

        state._notification_analytics = {
            (10, 1): {
                "id": 1,
                "notification_id": 10,
                "tenant_id": 1,
                "opened_at": datetime(2026, 1, 1, tzinfo=UTC),
                "clicked_at": None,
                "channel": "email",
            }
        }

        rate = await service.get_open_rate(notification_id=10, tenant_id=1)
        assert rate >= 1.0


class TestCrossTenantIsolation:
    async def test_cross_tenant_isolation(self, mock_db_session, service):
        """track_open for tenant_id=1 does not affect get_open_rate for tenant_id=2."""
        state = mock_db_session._state
        from datetime import UTC, datetime

        state._notification_analytics = {
            (10, 1): {
                "id": 1,
                "notification_id": 10,
                "tenant_id": 1,
                "opened_at": datetime(2026, 1, 1, tzinfo=UTC),
                "clicked_at": None,
                "channel": "email",
            }
        }

        rate_tenant_1 = await service.get_open_rate(notification_id=10, tenant_id=1)
        rate_tenant_2 = await service.get_open_rate(notification_id=10, tenant_id=2)

        assert rate_tenant_1 >= 1.0
        assert rate_tenant_2 == 0.0
