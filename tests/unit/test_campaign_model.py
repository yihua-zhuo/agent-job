"""Unit tests for CampaignModel, CampaignEventModel, TriggerModel ORM to_dict."""

from __future__ import annotations

from datetime import datetime

import pytest

from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.campaigns import make_campaign_handler


@pytest.fixture
def mock_state():
    return MockState()


@pytest.fixture
def mock_db_session(mock_state):
    return make_mock_session(
        handlers=[make_campaign_handler(mock_state)],
        state=mock_state,
    )


class TestCampaignModelToDict:
    """Test CampaignModel.to_dict() via unit mock."""

    async def test_campaign_to_dict_basic(self, mock_db_session, mock_state):
        """Verify to_dict output for a minimal campaign."""
        from db.models.marketing import CampaignModel

        now = datetime.now()
        record = {
            "id": 42,
            "tenant_id": 1,
            "name": "Summer Sale",
            "type": "email",
            "status": "active",
            "subject": "50% Off!",
            "content": "Buy now!",
            "target_audience": "all_customers",
            "trigger_type": "user_register",
            "trigger_days": 7,
            "created_by": 99,
            "sent_count": 100,
            "open_count": 30,
            "click_count": 5,
            "created_at": now,
            "updated_at": now,
        }
        mock_state.campaigns = {42: record}
        mock_state.campaigns_next_id = 43

        result = await mock_db_session.execute(
            "SELECT * FROM campaigns WHERE id = :id", {"id": 42, "tenant_id": 1}
        )
        row = result.fetchone()
        assert row is not None

        model = CampaignModel(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            type=row.type,
            status=row.status,
            subject=row.subject,
            content=row.content,
            target_audience=row.target_audience,
            trigger_type=row.trigger_type,
            trigger_days=row.trigger_days,
            created_by=row.created_by,
            sent_count=row.sent_count,
            open_count=row.open_count,
            click_count=row.click_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        d = model.to_dict()
        assert d["id"] == 42
        assert d["tenant_id"] == 1
        assert d["name"] == "Summer Sale"
        assert d["type"] == "email"
        assert d["status"] == "active"
        assert d["subject"] == "50% Off!"
        assert d["target_audience"] == "all_customers"
        assert d["trigger_type"] == "user_register"
        assert d["trigger_days"] == 7
        assert d["created_by"] == 99
        assert d["sent_count"] == 100
        assert d["open_count"] == 30
        assert d["click_count"] == 5


class TestCampaignEventModelToDict:
    """Test CampaignEventModel.to_dict()."""

    async def test_campaign_event_to_dict(self, mock_db_session, mock_state):
        """Verify to_dict output for a campaign event."""
        from db.models.marketing import CampaignEventModel

        now = datetime.now()
        record = {
            "id": 7,
            "tenant_id": 1,
            "campaign_id": 10,
            "customer_id": 5,
            "event_type": "opened",
            "created_at": now,
        }
        if not hasattr(mock_state, "campaign_events"):
            mock_state.campaign_events = {}
        mock_state.campaign_events[7] = record
        mock_state.campaign_events_next_id = 8

        result = await mock_db_session.execute(
            "SELECT * FROM campaign_events WHERE id = :id", {"id": 7, "tenant_id": 1}
        )
        row = result.fetchone()
        assert row is not None

        model = CampaignEventModel(
            id=row.id,
            tenant_id=row.tenant_id,
            campaign_id=row.campaign_id,
            customer_id=row.customer_id,
            event_type=row.event_type,
            created_at=row.created_at,
        )
        d = model.to_dict()
        assert d["id"] == 7
        assert d["tenant_id"] == 1
        assert d["campaign_id"] == 10
        assert d["customer_id"] == 5
        assert d["event_type"] == "opened"


class TestTriggerModelToDict:
    """Test TriggerModel.to_dict()."""

    async def test_trigger_to_dict_basic(self, mock_db_session, mock_state):
        """Verify to_dict output for a trigger."""
        from db.models.marketing import TriggerModel

        now = datetime.now()
        record = {
            "id": 3,
            "tenant_id": 1,
            "campaign_id": 10,
            "name": "Welcome Series",
            "type": "custom",
            "conditions": {"segment": "new_users"},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        if not hasattr(mock_state, "triggers"):
            mock_state.triggers = {}
        mock_state.triggers[3] = record
        mock_state.trigger_next_id = 4

        result = await mock_db_session.execute(
            "SELECT * FROM campaign_triggers WHERE id = :id", {"id": 3, "tenant_id": 1}
        )
        row = result.fetchone()
        assert row is not None

        model = TriggerModel(
            id=row.id,
            tenant_id=row.tenant_id,
            campaign_id=row.campaign_id,
            name=row.name,
            type=row.type,
            conditions=row.conditions,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        d = model.to_dict()
        assert d["id"] == 3
        assert d["tenant_id"] == 1
        assert d["campaign_id"] == 10
        assert d["name"] == "Welcome Series"
        assert d["type"] == "custom"
        assert d["conditions"] == {"segment": "new_users"}
        assert d["is_active"] is True

    async def test_trigger_to_dict_nullable_campaign(self, mock_db_session, mock_state):
        """Verify trigger with no linked campaign."""
        from db.models.marketing import TriggerModel

        now = datetime.now()
        record = {
            "id": 4,
            "tenant_id": 2,
            "campaign_id": None,
            "name": "Orphan Trigger",
            "type": "user_register",
            "conditions": {},
            "is_active": False,
            "created_at": now,
            "updated_at": now,
        }
        if not hasattr(mock_state, "triggers"):
            mock_state.triggers = {}
        mock_state.triggers[4] = record
        mock_state.trigger_next_id = 5

        result = await mock_db_session.execute(
            "SELECT * FROM campaign_triggers WHERE id = :id", {"id": 4, "tenant_id": 2}
        )
        row = result.fetchone()
        assert row is not None

        model = TriggerModel(
            id=row.id,
            tenant_id=row.tenant_id,
            campaign_id=row.campaign_id,
            name=row.name,
            type=row.type,
            conditions=row.conditions,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        d = model.to_dict()
        assert d["campaign_id"] is None
        assert d["is_active"] is False
        assert d["tenant_id"] == 2
