"""Integration tests for Webhook ORM models against a real PostgreSQL database.

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_webhook_model_integration.py -v

Requires DATABASE_URL pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from db.models.webhook import WebhookDeliveryModel, WebhookModel


@pytest.mark.integration
class TestWebhookModelIntegration:
    async def test_insert_webhook_and_delivery(self, db_schema, tenant_id, async_session):
        """Insert a webhook, flush to get the ID, then insert a delivery referencing it, commit, and query back."""
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

    async def test_delivery_queryable_by_tenant(self, db_schema, tenant_id, async_session):
        """Deliveries can be filtered by tenant_id in a query."""
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

    async def test_cascade_delete_parent_webhook(self, db_schema, tenant_id, async_session):
        """Deleting the parent webhook cascades to its deliveries."""
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

    async def test_webhook_is_active_default(self, db_schema, tenant_id, async_session):
        """Newly created webhook has is_active=True when not specified."""
        webhook = WebhookModel(
            tenant_id=tenant_id,
            url="https://example.com/hook4",
            events=["ticket.closed"],
        )
        async_session.add(webhook)
        await async_session.flush()

        assert webhook.is_active is True

    async def test_delivery_defaults(self, db_schema, tenant_id, async_session):
        """Newly created delivery has correct defaults: status=pending, attempts=1."""
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
