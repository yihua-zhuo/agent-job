"""Integration tests for MarketingService CRUD against real PostgreSQL.

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_marketing_integration.py -v

Requires DATABASE_URL pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""

from __future__ import annotations

import uuid

import pytest

from models.marketing import CampaignStatus, CampaignType, TriggerType
from pkg.errors.app_exceptions import NotFoundException
from services.marketing_service import MarketingService
from services.user_service import UserService


@pytest.mark.integration
class TestMarketingServiceIntegration:
    """Full campaign CRUD lifecycle via the real DB."""

    async def _seed_user(self, async_session, tenant_id: int) -> int:
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"mktuser_{suffix}",
            email=f"mkt_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.id

    async def test_create_and_get(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(async_session, tenant_id)
        svc = MarketingService(async_session)
        suffix = uuid.uuid4().hex[:8]
        result = await svc.create_campaign(
            name=f"Campaign {suffix}",
            campaign_type=CampaignType.EMAIL,
            content="Test content",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Subject line",
            target_audience="all_users",
        )
        assert result.name == f"Campaign {suffix}"
        assert result.status == CampaignStatus.DRAFT.value

        fetched = await svc.get_campaign(result.id, tenant_id=tenant_id)
        assert fetched.id == result.id
        assert fetched.name == f"Campaign {suffix}"

    async def test_update_and_list_filter(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(async_session, tenant_id)
        svc = MarketingService(async_session)
        suffix = uuid.uuid4().hex[:8]

        created = await svc.create_campaign(
            name=f"Update Test {suffix}",
            campaign_type="email",
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Test",
            trigger_type=TriggerType.CUSTOM,
        )
        cid = created.id

        updated = await svc.update_campaign(
            cid,
            tenant_id=tenant_id,
            name=f"Updated {suffix}",
            status=CampaignStatus.ACTIVE,
        )
        assert updated.name == f"Updated {suffix}"
        assert updated.status == CampaignStatus.ACTIVE.value

        # list with status filter
        items, total = await svc.list_campaigns(tenant_id=tenant_id, status=CampaignStatus.ACTIVE)
        assert total >= 1
        assert any(c.id == cid for c in items)

    async def test_delete_not_found(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(async_session, tenant_id)
        svc = MarketingService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_campaign(
            name=f"Delete Test {suffix}",
            campaign_type="email",
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Test",
        )
        cid = created.id

        # delete it
        deleted = await svc.delete_campaign(cid, tenant_id=tenant_id)
        assert deleted.id == cid

        # fetch after delete raises NotFoundException
        with pytest.raises(NotFoundException):
            await svc.get_campaign(cid, tenant_id=tenant_id)

        # update after delete raises NotFoundException
        with pytest.raises(NotFoundException):
            await svc.update_campaign(cid, tenant_id=tenant_id, name="New Name")

        # delete again raises NotFoundException
        with pytest.raises(NotFoundException):
            await svc.delete_campaign(cid, tenant_id=tenant_id)

    async def test_tenant_isolation(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(async_session, tenant_id)
        svc = MarketingService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_campaign(
            name=f"Isolation Test {suffix}",
            campaign_type="email",
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Test",
        )
        cid = created.id

        # another tenant cannot see it
        with pytest.raises(NotFoundException):
            await svc.get_campaign(cid, tenant_id=tenant_id + 9999)

    async def test_list_pagination(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(async_session, tenant_id)
        svc = MarketingService(async_session)
        suffix = uuid.uuid4().hex[:8]

        # create 3 campaigns
        for i in range(3):
            await svc.create_campaign(
                name=f"Page Test {i} {suffix}",
                campaign_type="email",
                content="Body",
                created_by=uid,
                tenant_id=tenant_id,
                subject=f"Subject {i}",
            )

        # page 1, size 2
        items, total = await svc.list_campaigns(tenant_id=tenant_id, page=1, page_size=2)
        assert len(items) == 2
        assert total >= 3

        # page 2, size 2
        items2, _ = await svc.list_campaigns(tenant_id=tenant_id, page=2, page_size=2)
        assert len(items2) >= 1