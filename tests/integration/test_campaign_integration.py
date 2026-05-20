"""Integration tests for CampaignModel, CampaignEventModel, TriggerModel.

Uses real PostgreSQL via the db_schema + async_session fixtures.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from db.models.marketing import CampaignEventModel, CampaignModel, TriggerModel


@pytest.mark.integration
class TestCampaignIntegration:
    async def test_create_campaign(self, db_schema, tenant_id, async_session):
        """Create a campaign and verify it can be retrieved from the DB."""
        campaign = CampaignModel(
            tenant_id=tenant_id,
            name="Email Campaign",
            type="email",
            status="draft",
            subject="Welcome!",
            content="Hello world",
            target_audience="all",
            trigger_type="user_register",
            trigger_days=3,
            created_by=1,
            sent_count=0,
            open_count=0,
            click_count=0,
        )
        async_session.add(campaign)
        await async_session.commit()
        await async_session.refresh(campaign)

        assert campaign.id is not None
        assert campaign.name == "Email Campaign"
        assert campaign.type == "email"
        assert campaign.status == "draft"
        assert campaign.tenant_id == tenant_id

    async def test_create_trigger_linked_to_campaign(
        self, db_schema, tenant_id, async_session
    ):
        """Create a campaign with an attached trigger."""
        campaign = CampaignModel(
            tenant_id=tenant_id,
            name="Promotion",
            type="email",
            status="active",
            subject="Sale",
            content="50% off",
            created_by=1,
        )
        async_session.add(campaign)
        await async_session.flush()

        trigger = TriggerModel(
            tenant_id=tenant_id,
            campaign_id=campaign.id,
            name="Post-Signup Promo",
            type="user_register",
            conditions={"segment": "new"},
            is_active=True,
        )
        async_session.add(trigger)
        await async_session.commit()

        # Retrieve trigger and verify it's linked
        result = await async_session.execute(
            text("SELECT * FROM campaign_triggers WHERE id = :id"),
            {"id": trigger.id},
        )
        row = result.fetchone()
        assert row is not None
        assert row.campaign_id == campaign.id

    async def test_create_campaign_event(self, db_schema, tenant_id, async_session):
        """Create a campaign event and verify it records customer interaction."""
        campaign = CampaignModel(
            tenant_id=tenant_id,
            name="Blast",
            type="email",
            status="active",
            content="Send it!",
            created_by=1,
        )
        async_session.add(campaign)
        await async_session.flush()

        event = CampaignEventModel(
            tenant_id=tenant_id,
            campaign_id=campaign.id,
            customer_id=100,
            event_type="opened",
        )
        async_session.add(event)
        await async_session.commit()

        # Verify event is persisted
        result = await async_session.execute(
            text("SELECT * FROM campaign_events WHERE id = :id"),
            {"id": event.id},
        )
        row = result.fetchone()
        assert row is not None
        assert row.campaign_id == campaign.id
        assert row.customer_id == 100
        assert row.event_type == "opened"

    async def test_campaign_events_relationship(self, db_schema, tenant_id, async_session):
        """Create campaign with events and verify events are accessible via ORM."""
        campaign = CampaignModel(
            tenant_id=tenant_id,
            name="Seq",
            type="email",
            status="active",
            content="Test",
            created_by=1,
        )
        async_session.add(campaign)
        await async_session.flush()

        for i, evt_type in enumerate(["sent", "opened", "clicked"]):
            evt = CampaignEventModel(
                tenant_id=tenant_id,
                campaign_id=campaign.id,
                customer_id=100 + i,
                event_type=evt_type,
            )
            async_session.add(evt)

        await async_session.commit()

        # Refresh and check count via direct query (relationship lazy behavior)
        result = await async_session.execute(
            text(
                "SELECT COUNT(*) as cnt FROM campaign_events "
                "WHERE campaign_id = :campaign_id AND tenant_id = :tenant_id"
            ),
            {"campaign_id": campaign.id, "tenant_id": tenant_id},
        )
        row = result.fetchone()
        assert row[0] == 3

    async def test_trigger_cascade_on_delete(
        self, db_schema, tenant_id, async_session
    ):
        """Deleting a campaign should cascade to its triggers and events."""
        campaign = CampaignModel(
            tenant_id=tenant_id,
            name="ToDelete",
            type="email",
            status="draft",
            content="Gone soon",
            created_by=1,
        )
        async_session.add(campaign)
        await async_session.flush()

        trigger = TriggerModel(
            tenant_id=tenant_id,
            campaign_id=campaign.id,
            name="Will be gone",
            type="custom",
            conditions={},
            is_active=True,
        )
        async_session.add(trigger)

        event = CampaignEventModel(
            tenant_id=tenant_id,
            campaign_id=campaign.id,
            customer_id=1,
            event_type="sent",
        )
        async_session.add(event)
        await async_session.commit()

        # Delete the campaign
        await async_session.delete(campaign)
        await async_session.commit()

        # Verify trigger and event are gone
        trig_result = await async_session.execute(
            text("SELECT COUNT(*) as cnt FROM campaign_triggers WHERE campaign_id = :campaign_id"),
            {"campaign_id": campaign.id},
        )
        evt_result = await async_session.execute(
            text("SELECT COUNT(*) as cnt FROM campaign_events WHERE campaign_id = :campaign_id"),
            {"campaign_id": campaign.id},
        )
        assert trig_result.fetchone()[0] == 0
        assert evt_result.fetchone()[0] == 0

    async def test_multi_tenant_isolation(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Campaigns and triggers from one tenant should not be visible to another."""
        camp1 = CampaignModel(
            tenant_id=tenant_id,
            name="Tenant1 Campaign",
            type="email",
            status="active",
            content="For tenant 1",
            created_by=1,
        )
        async_session.add(camp1)
        await async_session.flush()

        trigger1 = TriggerModel(
            tenant_id=tenant_id,
            campaign_id=camp1.id,
            name="T1 Trigger",
            type="custom",
            conditions={},
            is_active=True,
        )
        async_session.add(trigger1)

        camp2 = CampaignModel(
            tenant_id=tenant_id_2,
            name="Tenant2 Campaign",
            type="sms",
            status="active",
            content="For tenant 2",
            created_by=1,
        )
        async_session.add(camp2)
        await async_session.flush()

        trigger2 = TriggerModel(
            tenant_id=tenant_id_2,
            campaign_id=camp2.id,
            name="T2 Trigger",
            type="custom",
            conditions={},
            is_active=True,
        )
        async_session.add(trigger2)
        await async_session.commit()

        # Count campaigns per tenant
        r1 = await async_session.execute(
            text("SELECT COUNT(*) as cnt FROM campaigns WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        r2 = await async_session.execute(
            text("SELECT COUNT(*) as cnt FROM campaigns WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id_2},
        )
        assert r1.fetchone()[0] == 1
        assert r2.fetchone()[0] == 1

        # Count triggers per tenant
        t1 = await async_session.execute(
            text("SELECT COUNT(*) as cnt FROM campaign_triggers WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        t2 = await async_session.execute(
            text("SELECT COUNT(*) as cnt FROM campaign_triggers WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id_2},
        )
        assert t1.fetchone()[0] == 1
        assert t2.fetchone()[0] == 1

    async def test_to_dict_serialization(self, db_schema, tenant_id, async_session):
        """Verify to_dict() produces expected keys and types."""
        campaign = CampaignModel(
            tenant_id=tenant_id,
            name="Serialize Test",
            type="email",
            status="active",
            subject="Test Subject",
            content="Content here",
            target_audience="all",
            trigger_type="purchase_made",
            trigger_days=5,
            created_by=99,
            sent_count=10,
            open_count=3,
            click_count=1,
        )
        async_session.add(campaign)
        await async_session.flush()

        d = campaign.to_dict()
        assert d["name"] == "Serialize Test"
        assert d["type"] == "email"
        assert d["status"] == "active"
        assert d["subject"] == "Test Subject"
        assert d["trigger_type"] == "purchase_made"
        assert d["trigger_days"] == 5
        assert d["sent_count"] == 10
        assert d["open_count"] == 3
        assert d["click_count"] == 1
        assert d["created_at"] is not None

    async def test_trigger_model_to_dict(self, db_schema, tenant_id, async_session):
        """Verify TriggerModel.to_dict() output."""
        trigger = TriggerModel(
            tenant_id=tenant_id,
            campaign_id=None,
            name="Orphan",
            type="user_inactive",
            conditions={"days_inactive": 30},
            is_active=False,
        )
        async_session.add(trigger)
        await async_session.commit()
        await async_session.refresh(trigger)

        d = trigger.to_dict()
        assert d["name"] == "Orphan"
        assert d["type"] == "user_inactive"
        assert d["conditions"] == {"days_inactive": 30}
        assert d["is_active"] is False
        assert d["campaign_id"] is None

    async def test_campaign_event_model_to_dict(self, db_schema, tenant_id, async_session):
        """Verify CampaignEventModel.to_dict() output."""
        campaign = CampaignModel(
            tenant_id=tenant_id,
            name="Event Test",
            type="email",
            status="active",
            content="test",
            created_by=1,
        )
        async_session.add(campaign)
        await async_session.flush()

        event = CampaignEventModel(
            tenant_id=tenant_id,
            campaign_id=campaign.id,
            customer_id=55,
            event_type="bounced",
        )
        async_session.add(event)
        await async_session.commit()
        await async_session.refresh(event)

        d = event.to_dict()
        assert d["customer_id"] == 55
        assert d["event_type"] == "bounced"
        assert d["campaign_id"] == campaign.id
