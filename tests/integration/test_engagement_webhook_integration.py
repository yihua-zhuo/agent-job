"""Integration tests for the engagement webhook and lead-tier filter / score sort.

Run against a real PostgreSQL database (Supabase via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_engagement_webhook_integration.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from db.models.engagement import EngagementEventModel
from db.repositories.customer import CustomerRepository
from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.customer_service import CustomerService
from services.event_service import EventService
from services.score_service import ScoreService


# ──────────────────────────────────────────────────────────────────────────────────────
#  Engagement webhook — service-level integration
# ──────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
class TestEngagementWebhookIntegration:
    """POST /events/engagement persists rows and triggers score recalculation."""

    async def test_engagement_event_persisted_with_correct_fields(
        self, db_schema, _seed_tenant, _seed_customer, tenant_id, async_session
    ):
        """EventService writes a row with the expected tenant_id, customer_id, event_type, and metadata."""
        customer_id = await _seed_customer()

        svc = EventService(async_session)
        metadata = {"campaign": "spring", "source": "newsletter"}
        event = await svc.record_engagement_event(
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type="email_open",
            event_metadata=metadata,
        )
        # EventService uses flush() (Rule 121 — routers own commit).
        # The service's own flush already populated event.id; no extra flush needed
        # for the re-read below because the same session sees its own writes.

        assert event.id is not None
        assert event.tenant_id == tenant_id
        assert event.customer_id == customer_id
        assert event.event_type == "email_open"
        # event_metadata is the ORM attribute name (column: engagement_events.event_metadata)
        assert event.event_metadata == metadata
        assert event.created_at is not None

        # Re-read from DB to confirm persistence
        result = await async_session.execute(
            select(EngagementEventModel).where(EngagementEventModel.id == event.id)
        )
        persisted = result.scalar_one()
        assert persisted.event_type == "email_open"
        assert persisted.event_metadata == metadata

    async def test_score_service_runs_after_event_recorded(
        self, db_schema, _seed_tenant, _seed_customer, tenant_id, async_session
    ):
        """ScoreService.calculate_score runs and returns deterministic tier when score_factors are set."""
        # score_factors giving score ~ 90 → tier A
        factors = {
            "engagement_level": 90,
            "deal_velocity": 90,
            "support_health": 90,
            "payment_history": 90,
            "product_adoption": 90,
        }
        customer_id = await _seed_customer(score_factors=factors)

        event_svc = EventService(async_session)
        score_svc = ScoreService(async_session)

        await event_svc.record_engagement_event(
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type="email_open",
        )
        result = await score_svc.calculate_score(
            customer_id=customer_id, tenant_id=tenant_id
        )

        assert result.score >= 80
        assert result.tier.value == "A"
        assert result.tier_label == "A"

    async def test_cross_tenant_isolation_event_not_visible(
        self,
        db_schema,
        _seed_tenant,
        _seed_tenant_2,
        _seed_customer,
        tenant_id,
        tenant_id_2,
        async_session,
    ):
        """An event recorded for tenant A is invisible from tenant B's perspective.

        Also verifies that events for tenant B's customer are not visible from
        tenant A's view (full Rule 126 cross-tenant negative test).
        """
        customer_id_a = await _seed_customer()
        customer_id_b = await _seed_customer(tenant_id=tenant_id_2)

        svc = EventService(async_session)
        await svc.record_engagement_event(
            tenant_id=tenant_id,
            customer_id=customer_id_a,
            event_type="email_open",
        )
        await svc.record_engagement_event(
            tenant_id=tenant_id_2,
            customer_id=customer_id_b,
            event_type="website_visit",
        )

        # From tenant B's perspective customer A does not exist (different tenant_id filter)
        # so a fresh ScoreService call must raise NotFoundException rather than return stale state.
        score_svc = ScoreService(async_session)
        with pytest.raises(NotFoundException):
            await score_svc.calculate_score(
                customer_id=customer_id_a, tenant_id=tenant_id_2
            )

        # And tenant A must not see tenant B's events.
        events_for_a = await async_session.execute(
            select(EngagementEventModel).where(
                EngagementEventModel.tenant_id == tenant_id
            )
        )
        a_events = events_for_a.scalars().all()
        assert all(ev.tenant_id == tenant_id for ev in a_events)
        assert len(a_events) == 1
        assert a_events[0].customer_id == customer_id_a


# ──────────────────────────────────────────────────────────────────────────────────────
#  Lead-tier filter and order_by_score — repository-level integration
# ──────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
class TestLeadTierAndOrderByScore:
    """GET /customers/ ?lead_tier=...&order_by_score=true integration tests."""

    async def test_lead_tier_filter_returns_only_matching_tier(
        self, db_schema, _seed_tenant, _seed_customer, tenant_id, async_session
    ):
        """lead_tier='hot' returns only customers whose stored tier is 'A' (hot mapping)."""
        customer_id_hot = await _seed_customer(tier="A")
        await _seed_customer(tier="B")
        await _seed_customer(tier="C")

        repo = CustomerRepository(async_session)
        items, total = await repo.list_customers(tenant_id=tenant_id, lead_tier="A")
        assert total == 1
        assert len(items) == 1
        assert items[0].id == customer_id_hot
        assert items[0].tier == "A"

    async def test_lead_tier_filter_with_no_matches_returns_empty(
        self, db_schema, _seed_tenant, _seed_customer, tenant_id, async_session
    ):
        """lead_tier value that no customer has returns an empty result set."""
        await _seed_customer(tier="A")
        await _seed_customer(tier="B")

        repo = CustomerRepository(async_session)
        items, total = await repo.list_customers(tenant_id=tenant_id, lead_tier="D")
        assert total == 0
        assert items == []

    async def test_order_by_score_returns_highest_scoring_first(
        self, db_schema, _seed_tenant, _seed_customer, tenant_id, async_session
    ):
        """order_by_score=True sorts customers by score DESC (COALESCE NULLs to 0)."""
        low_id = await _seed_customer(score=10)
        mid_id = await _seed_customer(score=50)
        high_id = await _seed_customer(score=90)
        null_id = await _seed_customer(score=None)  # NULL → 0

        repo = CustomerRepository(async_session)
        items, total = await repo.list_customers(tenant_id=tenant_id, order_by_score=True)
        assert total == 4
        # Highest first, NULLs treated as 0 (last in DESC order)
        ids_in_order = [c.id for c in items]
        assert ids_in_order.index(high_id) < ids_in_order.index(mid_id)
        assert ids_in_order.index(mid_id) < ids_in_order.index(low_id)
        assert ids_in_order[-1] == null_id

    async def test_default_ordering_unchanged_without_order_by_score(
        self, db_schema, _seed_tenant, _seed_customer, tenant_id, async_session
    ):
        """Without order_by_score the default created_at DESC ordering is preserved."""
        # Seed customers with explicit, distinct created_at timestamps so DESC
        # ordering is deterministic. The seed_customer domain fixture owns the
        # data shape; we just pass the timestamps through it.
        base = datetime.now(UTC)
        ids: list[int] = []
        for offset_minutes in range(3):
            ts = base + timedelta(minutes=offset_minutes)
            customer_id = await _seed_customer(
                name_suffix=f"order_{offset_minutes}",
                created_at=ts,
                updated_at=ts,
            )
            ids.append(customer_id)
        first_id, second_id, third_id = ids

        repo = CustomerRepository(async_session)
        items, _total = await repo.list_customers(tenant_id=tenant_id)
        ids_in_order = [c.id for c in items]
        # Most-recently-created first
        assert ids_in_order[0] == third_id
        assert ids_in_order[-1] == first_id

    async def test_lead_tier_and_order_by_score_combine(
        self, db_schema, _seed_tenant, _seed_customer, tenant_id, async_session
    ):
        """lead_tier + order_by_score combine: filter then sort by score DESC."""
        hot_low = await _seed_customer(tier="A", score=20)
        hot_high = await _seed_customer(tier="A", score=95)
        await _seed_customer(tier="B", score=99)  # excluded

        repo = CustomerRepository(async_session)
        items, total = await repo.list_customers(
            tenant_id=tenant_id, lead_tier="A", order_by_score=True
        )
        assert total == 2
        assert [c.id for c in items] == [hot_high, hot_low]

    async def test_lead_tier_invalid_raises_validation_in_service(
        self, db_schema, _seed_tenant, _seed_customer, customer_service, tenant_id, async_session
    ):
        """Service-layer validation rejects unknown lead_tier values with ValidationException.

        Uses the shared ``customer_service`` fixture (wires a real repository
        with the test session) so the test exercises the service's own
        validation path without going through FastAPI's dependency injection.
        """
        await _seed_customer()

        with pytest.raises(ValidationException, match="lead_tier must be one of"):
            await customer_service.list_customers(tenant_id=tenant_id, lead_tier="bogus")

    async def test_lead_tier_hot_via_service_maps_to_tier_a(
        self, db_schema, _seed_tenant, _seed_customer, customer_service, tenant_id, async_session
    ):
        """Service-level lead_tier='hot' is translated to stored tier 'A' before SQL filtering."""
        customer_id_a = await _seed_customer(tier="A")
        await _seed_customer(tier="B")
        await _seed_customer(tier="C")

        items, total = await customer_service.list_customers(tenant_id=tenant_id, lead_tier="hot")
        assert total == 1
        assert [c.id for c in items] == [customer_id_a]
