"""Unit tests for NotificationAnalyticsService."""

import pytest

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
        from datetime import UTC, datetime
        state._notification_analytics = {
            (10, 1): {
                "id": 1,
                "notification_id": 10,
                "tenant_id": 1,
                "opened_at": None,
                "clicked_at": None,
                "channel": "email",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        }

        result = await service.track_open(notification_id=10, tenant_id=1)

        assert result.notification_id == 10
        assert result.tenant_id == 1
        assert result.channel == "email"
        assert result.opened_at is not None
        assert result.updated_at is not None
        assert result.clicked_at is None
        assert len(state._notification_analytics) == 1

    async def test_track_open_upsert(self, mock_db_session, service):
        """track_open called twice does not create two rows; second call updates opened_at."""
        state = mock_db_session._state
        from datetime import UTC, datetime
        state._notification_analytics = {
            (10, 1): {
                "id": 1,
                "notification_id": 10,
                "tenant_id": 1,
                "opened_at": None,
                "clicked_at": None,
                "channel": "email",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        }

        first = await service.track_open(notification_id=10, tenant_id=1)
        second = await service.track_open(notification_id=10, tenant_id=1)

        assert first.id == second.id
        assert len(state._notification_analytics) == 1

    async def test_track_open_update_stamps_opened_at(self, mock_db_session, service):
        """track_open stamps opened_at on a pre-existing record that has no opened_at yet."""
        state = mock_db_session._state
        from datetime import UTC, datetime
        state._notification_analytics = {
            (10, 1): {
                "id": 1,
                "notification_id": 10,
                "tenant_id": 1,
                "opened_at": None,
                "clicked_at": None,
                "channel": "email",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        }

        result = await service.track_open(notification_id=10, tenant_id=1)

        assert result.opened_at is not None
        assert result.updated_at is not None

    async def test_track_open_creates_when_absent(self, mock_db_session, service):
        """track_open inserts a new record when no analytics row exists yet."""
        result = await service.track_open(notification_id=10, tenant_id=1, channel="push")

        assert result.notification_id == 10
        assert result.tenant_id == 1
        assert result.channel == "push"
        assert result.opened_at is not None
        assert result.updated_at is not None


class TestGetOpenCount:
    async def test_get_open_count_no_records(self, mock_db_session, service):
        """get_open_count returns 0 when no analytics exist."""
        count = await service.get_open_count(notification_id=10, tenant_id=1)
        assert count == 0

    async def test_get_open_count_returns_count_not_rate(self, mock_db_session, service):
        """get_open_count returns the raw opened count, not a rate.

        A true open rate requires total-sent context (opened/total_sent), which is
        not computed here — this method returns the raw count of opened records only.
        """
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
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        }

        count = await service.get_open_count(notification_id=10, tenant_id=1)
        # Returns count (1), not rate (1.0).
        assert count == 1


class TestCrossTenantIsolation:
    async def test_get_open_count_respects_tenant_isolation(self, mock_db_session, service):
        """get_open_count for tenant_id=1 does not return records for tenant_id=2."""
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
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        }

        count_tenant_1 = await service.get_open_count(notification_id=10, tenant_id=1)
        count_tenant_2 = await service.get_open_count(notification_id=10, tenant_id=2)

        assert count_tenant_1 == 1
        assert count_tenant_2 == 0

    async def test_track_open_respects_tenant_isolation(self, mock_db_session, service):
        """track_open for tenant_id=2 does not mutate or expose tenant_id=1's data."""
        state = mock_db_session._state
        from datetime import UTC, datetime

        # Seed a record for tenant 1
        state._notification_analytics = {
            (10, 1): {
                "id": 1,
                "notification_id": 10,
                "tenant_id": 1,
                "opened_at": None,
                "clicked_at": None,
                "channel": "email",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        }

        # Track open for tenant 2 — should create a new record, not mutate tenant 1's
        result = await service.track_open(notification_id=10, tenant_id=2, channel="sms")

        assert result.tenant_id == 2
        assert result.channel == "sms"
        assert result.opened_at is not None

        # Tenant 1 record is untouched
        tenant_1_record = state._notification_analytics.get((10, 1))
        assert tenant_1_record is not None
        assert tenant_1_record["tenant_id"] == 1
        assert tenant_1_record["opened_at"] is None

        # Tenant 2 record exists
        tenant_2_record = state._notification_analytics.get((10, 2))
        assert tenant_2_record is not None
        assert tenant_2_record["tenant_id"] == 2
        assert tenant_2_record["channel"] == "sms"
