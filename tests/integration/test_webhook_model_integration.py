"""Integration tests for Webhook ORM models against a real PostgreSQL database.

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_webhook_model_integration.py -v

Requires DATABASE_URL pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from db.models.webhook import WebhookDeliveryModel, WebhookModel
from services.tenant_service import TenantService


async def _seed_tenant(async_session, *, name: str | None = None) -> int:
    """Create a real tenant row and return its ID (needed for FK on webhook.tenant_id)."""
    suffix = uuid.uuid4().hex[:8]
    result = await TenantService(async_session).create_tenant(
        name=name or f"Webhook Test Tenant {suffix}",
        plan="pro",
        admin_email=f"webhook_admin_{suffix}@example.com",
    )
    return result.id


@pytest.mark.integration
class TestWebhookModelIntegration:
    async def test_insert_webhook_and_delivery(self, db_schema, async_session):
        """Insert a webhook, flush to get the ID, then insert a delivery referencing it, commit, and query back."""
        tenant_id = await _seed_tenant(async_session)
        webhook = WebhookModel(
            tenant_id=tenant_id,
            url="https://example.com/hooks/crm",
            events=["customer.created", "ticket.updated"],
            secret="my-signing-secret",  # noqa: S105  # test fixture, not a real credential
            is_active=True,
        )
        async_session.add(webhook)
        await async_session.flush()  # obtain the PK before inserting the child

        delivery = WebhookDeliveryModel(
            webhook_id=webhook.id,
            tenant_id=tenant_id,
            event_type="customer.created",
            payload={"customer": {"id": 123, "name": "Acme Corp"}},
            status="pending",
            attempts=1,
        )
        async_session.add(delivery)
        await async_session.commit()

        # Query back and verify
        result = await async_session.execute(
            select(WebhookModel).where(WebhookModel.id == webhook.id)
        )
        found = result.scalar_one()
        assert found.tenant_id == tenant_id
        assert found.url == "https://example.com/hooks/crm"
        assert found.events == ["customer.created", "ticket.updated"]
        assert found.secret == "my-signing-secret"  # noqa: S105
        assert found.is_active is True

        del_result = await async_session.execute(
            select(WebhookDeliveryModel).where(WebhookDeliveryModel.id == delivery.id)
        )
        found_del = del_result.scalar_one()
        assert found_del.webhook_id == webhook.id
        assert found_del.tenant_id == tenant_id
        assert found_del.event_type == "customer.created"
        assert found_del.payload == {"customer": {"id": 123, "name": "Acme Corp"}}
        assert found_del.status == "pending"
        assert found_del.attempts == 1
        assert found_del.delivered_at is None

    async def test_delivery_queryable_by_tenant(self, db_schema, async_session):
        """Deliveries can be filtered by tenant_id in a query."""
        tenant_id = await _seed_tenant(async_session)
        webhook = WebhookModel(
            tenant_id=tenant_id,
            url="https://example.com/hook2",
            events=["ticket.created"],
        )
        async_session.add(webhook)
        await async_session.flush()

        delivery = WebhookDeliveryModel(
            webhook_id=webhook.id,
            tenant_id=tenant_id,
            event_type="ticket.created",
            payload={"ticket": {"id": 99}},
            status="delivered",
            attempts=2,
        )
        async_session.add(delivery)
        await async_session.commit()

        result = await async_session.execute(
            select(WebhookDeliveryModel).where(WebhookDeliveryModel.tenant_id == tenant_id)
        )
        rows = result.scalars().all()
        assert any(r.id == delivery.id for r in rows)

    async def test_cascade_delete_parent_webhook(self, db_schema, async_session):
        """Deleting the parent webhook cascades to its deliveries."""
        tenant_id = await _seed_tenant(async_session)
        webhook = WebhookModel(
            tenant_id=tenant_id,
            url="https://example.com/hook3",
            events=["lead.created"],
        )
        async_session.add(webhook)
        await async_session.flush()

        delivery = WebhookDeliveryModel(
            webhook_id=webhook.id,
            tenant_id=tenant_id,
            event_type="lead.created",
            payload={"lead": {"id": 7}},
            status="pending",
        )
        async_session.add(delivery)
        await async_session.commit()
        delivery_id = delivery.id

        # Delete parent — child should be cascade-removed
        await async_session.delete(webhook)
        await async_session.commit()

        remaining = await async_session.execute(
            select(WebhookDeliveryModel).where(WebhookDeliveryModel.id == delivery_id)
        )
        assert remaining.scalar_one_or_none() is None

    async def test_cascade_delete_sibling_webhook_untouched(self, db_schema, async_session):
        """Deleting one webhook does not affect a sibling webhook with the same tenant."""
        tenant_id = await _seed_tenant(async_session)
        webhook1 = WebhookModel(
            tenant_id=tenant_id,
            url="https://example.com/hook-a",
            events=["lead.created"],
        )
        webhook2 = WebhookModel(
            tenant_id=tenant_id,
            url="https://example.com/hook-b",
            events=["lead.created"],
        )
        async_session.add_all([webhook1, webhook2])
        await async_session.flush()
        webhook2_id = webhook2.id

        await async_session.delete(webhook1)
        await async_session.commit()

        remaining = await async_session.execute(
            select(WebhookModel).where(WebhookModel.id == webhook2_id)
        )
        assert remaining.scalar_one_or_none() is not None

    async def test_cross_tenant_webhook_not_visible(self, db_schema, async_session):
        """A webhook belonging to a different tenant is not returned in queries."""
        tenant_a = await _seed_tenant(async_session, name="Tenant A")
        tenant_b = await _seed_tenant(async_session, name="Tenant B")

        webhook_a = WebhookModel(
            tenant_id=tenant_a,
            url="https://example.com/hook-self",
            events=["ticket.created"],
        )
        webhook_b = WebhookModel(
            tenant_id=tenant_b,
            url="https://example.com/hook-other",
            events=["ticket.created"],
        )
        async_session.add_all([webhook_a, webhook_b])
        await async_session.flush()
        self_id = webhook_a.id
        await async_session.commit()

        result = await async_session.execute(
            select(WebhookModel).where(WebhookModel.tenant_id == tenant_a)
        )
        rows = result.scalars().all()
        ids = {r.id for r in rows}
        assert self_id in ids
        assert webhook_b.id not in ids

    async def test_cross_tenant_delivery_not_visible(self, db_schema, async_session):
        """A delivery belonging to a different tenant is not returned in queries."""
        tenant_a = await _seed_tenant(async_session, name="Tenant A Delivery")
        tenant_b = await _seed_tenant(async_session, name="Tenant B Delivery")

        webhook_a = WebhookModel(
            tenant_id=tenant_a,
            url="https://example.com/hook-delivery",
            events=["customer.created"],
        )
        async_session.add(webhook_a)
        await async_session.flush()

        delivery_a = WebhookDeliveryModel(
            webhook_id=webhook_a.id,
            tenant_id=tenant_a,
            event_type="customer.created",
            payload={"customer": {"id": 50}},
            status="delivered",
        )
        delivery_b = WebhookDeliveryModel(
            webhook_id=webhook_a.id,
            tenant_id=tenant_b,
            event_type="customer.created",
            payload={"customer": {"id": 51}},
            status="pending",
        )
        async_session.add_all([delivery_a, delivery_b])
        await async_session.commit()
        self_id = delivery_a.id

        result = await async_session.execute(
            select(WebhookDeliveryModel).where(WebhookDeliveryModel.tenant_id == tenant_a)
        )
        rows = result.scalars().all()
        ids = {r.id for r in rows}
        assert self_id in ids
        assert delivery_b.id not in ids

    async def test_webhook_is_active_default(self, db_schema, async_session):
        """Newly created webhook has is_active=True when not specified."""
        tenant_id = await _seed_tenant(async_session)
        webhook = WebhookModel(
            tenant_id=tenant_id,
            url="https://example.com/hook4",
            events=["ticket.closed"],
        )
        async_session.add(webhook)
        await async_session.flush()

        assert webhook.is_active is True

    async def test_delivery_defaults(self, db_schema, async_session):
        """Newly created delivery has correct defaults: status=pending, attempts=1."""
        tenant_id = await _seed_tenant(async_session)
        webhook = WebhookModel(
            tenant_id=tenant_id,
            url="https://example.com/hook5",
            events=["order.placed"],
        )
        async_session.add(webhook)
        await async_session.flush()

        delivery = WebhookDeliveryModel(
            webhook_id=webhook.id,
            tenant_id=tenant_id,
            event_type="order.placed",
            payload={"order": {}},
        )
        async_session.add(delivery)
        await async_session.flush()

        assert delivery.status == "pending"
        assert delivery.attempts == 1
