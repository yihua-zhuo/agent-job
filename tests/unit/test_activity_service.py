"""Unit tests for src/services/activity_service.py."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.activity import Activity, ActivityType
from pkg.errors.app_exceptions import NotFoundException
from services.activity_service import ActivityService


@pytest.fixture
def mock_db_session():
    """Async mock session that tracks calls and properly wires execute()."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def activity_service(mock_db_session):
    return ActivityService(mock_db_session)


class TestCreateActivity:
    """Tests for ActivityService.create_activity."""

    @pytest.mark.asyncio
    async def test_create_activity_returns_activity(self, mock_db_session):
        """create_activity returns an Activity with correct fields."""
        created = Activity(
            id=None,
            tenant_id=0,
            customer_id=1,
            opportunity_id=None,
            type=ActivityType.CALL,
            content="Test call",
            created_by=1,
            created_at=datetime.now(UTC),
        )

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=created)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[created])))
            mock_result.scalar = MagicMock(return_value=1)
            return mock_result

        mock_db_session.execute = AsyncMock(side_effect=execute_side_effect)

        async def refresh_side_effect(obj):
            obj.id = 1

        mock_db_session.refresh = refresh_side_effect

        service = ActivityService(mock_db_session)
        result = await service.create_activity(
            customer_id=1,
            activity_type="call",
            content="Test call",
            created_by=1,
            tenant_id=1,
        )

        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        assert result.content == "Test call"
        assert result.type == ActivityType.CALL
        assert result.id == 1


class TestGetActivity:
    """Tests for ActivityService.get_activity."""

    @pytest.mark.asyncio
    async def test_get_activity_found(self, mock_db_session):
        """get_activity returns the activity when it exists."""
        activity = Activity(
            id=1,
            tenant_id=1,
            customer_id=1,
            opportunity_id=None,
            type=ActivityType.CALL,
            content="Test call",
            created_by=1,
            created_at=datetime.now(UTC),
        )

        mock_db_session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=activity),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[activity]))),
        ))

        service = ActivityService(mock_db_session)
        result = await service.get_activity(activity_id=1, tenant_id=1)

        assert result.content == "Test call"
        assert result.type == ActivityType.CALL
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_activity_not_found(self, mock_db_session):
        """get_activity raises NotFoundException when activity does not exist."""
        mock_db_session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None),
        ))

        service = ActivityService(mock_db_session)

        with pytest.raises(NotFoundException):
            await service.get_activity(activity_id=9999, tenant_id=1)


class TestUpdateActivity:
    """Tests for ActivityService.update_activity."""

    @pytest.mark.asyncio
    async def test_update_activity(self, mock_db_session):
        """update_activity returns the activity with updated content."""
        original = Activity(
            id=1,
            tenant_id=1,
            customer_id=1,
            opportunity_id=None,
            type=ActivityType.CALL,
            content="Original content",
            created_by=1,
            created_at=datetime.now(UTC),
        )
        updated = Activity(
            id=1,
            tenant_id=1,
            customer_id=1,
            opportunity_id=None,
            type=ActivityType.CALL,
            content="Updated content",
            created_by=1,
            created_at=datetime.now(UTC),
        )

        # _fetch x2 (existence check + post-update fetch), UPDATE
        mock_db_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=original)),
            MagicMock(),
            MagicMock(scalar_one_or_none=MagicMock(return_value=updated)),
        ])

        service = ActivityService(mock_db_session)
        result = await service.update_activity(activity_id=1, tenant_id=1, content="Updated content")

        assert result.content == "Updated content"
        assert result.id == 1


class TestDeleteActivity:
    """Tests for ActivityService.delete_activity."""

    @pytest.mark.asyncio
    async def test_delete_activity(self, mock_db_session):
        """delete_activity removes the activity and returns id dict."""
        existing = Activity(
            id=1,
            tenant_id=1,
            customer_id=1,
            opportunity_id=None,
            type=ActivityType.CALL,
            content="To be deleted",
            created_by=1,
            created_at=datetime.now(UTC),
        )

        # First _fetch finds the activity, second _fetch returns None (deleted)
        mock_db_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=existing)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])

        service = ActivityService(mock_db_session)
        result = await service.delete_activity(activity_id=1, tenant_id=1)

        assert result == {"id": 1}

        # Verify subsequent get raises NotFoundException
        mock_db_session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None),
        ))

        with pytest.raises(NotFoundException):
            await service.get_activity(activity_id=1, tenant_id=1)


class TestListActivitiesPagination:
    """Tests for ActivityService.list_activities pagination."""

    @pytest.mark.asyncio
    async def test_list_activities_pagination(self, mock_db_session):
        """list_activities returns paginated items and correct total."""
        activity1 = Activity(
            id=1,
            tenant_id=1,
            customer_id=1,
            opportunity_id=None,
            type=ActivityType.CALL,
            content="Call 1",
            created_by=1,
            created_at=datetime.now(UTC),
        )
        activity2 = Activity(
            id=2,
            tenant_id=1,
            customer_id=1,
            opportunity_id=None,
            type=ActivityType.EMAIL,
            content="Email 1",
            created_by=1,
            created_at=datetime.now(UTC),
        )

        # First call: COUNT query -> 3 total; Second call: SELECT with LIMIT/OFFSET -> 2 items
        mock_db_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar=MagicMock(return_value=3)),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[activity1, activity2])))),
        ])

        service = ActivityService(mock_db_session)
        items, total = await service.list_activities(tenant_id=1, page=1, page_size=2)

        assert len(items) == 2
        assert total == 3
