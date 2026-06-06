"""Integration tests for the engagement webhook and lead-tier filter / score sort.

Run against a real PostgreSQL database (Supabase via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_engagement_webhook_integration.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from db.models.engagement import EngagementEventModel
from db.models.tenant import TenantModel
from services.customer_service import CustomerService
from db.repositories.customer import CustomerRepository


# ──────────────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────────────


async def _seed_customer(
    async_session: AsyncSession,
    tenant_id: int,
    *,
    name_suffix: str | None = None,
    score: int | None = None,
    tier: str | None = None,
    score_factors: dict | None = None,
) -> int:
    """Seed a customer row and return its primary key id."""
    suffix = name_suffix or uuid.uuid4().hex[:8]
    customer = CustomerModel(
        tenant_id=tenant_id,
        name=f"Eng Cust {suffix}",
        email=f"eng_{suffix}@example.com",
        status="lead",
        owner_id=0,
        tags=[],
        score=score,
        tier=tier,
        score_factors=score_factors,
    )
    async_session.add(customer)
    await async_session.flush()
    return customer.id


async def _seed_tenant(async_session: AsyncSession, tenant_id: int) -> None:
    """Insert a tenant row so FK references are satisfied. Idempotent — no-op if already present."""
    from sqlalchemy import select

    result = await async_session.execute(select(TenantModel).where(TenantModel.id == tenant_id))
    if result.scalar_one_or_none() is not None:
        return
    tenant = TenantModel(
        id=tenant_id,
        name=f"Eng Test Tenant {tenant_id}",
        plan="free",
        status="active",
    )
    async_session.add(tenant)
    await async_session.flush()


# ──────────────────────────────────────────────────────────────────────────────────────
#  Engagement webhook — service-level integration
# ──────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
class TestEngagementWebhookIntegration:
    """POST /events/engagement persists rows and triggers score recalculation."""

    async def test_engagement_event_persisted_with_correct_fields(
        self, db_schema, tenant_id, async_session
    ):
        """EventService writes a row with the expected tenant_id, customer_id, event_type, and metadata."""
        await _seed_tenant(async_session, tenant_id)
        customer_id = await _seed_customer(async_session, tenant_id)

        from services.event_service import EventService

        svc = EventService(async_session)
        metadata = {"campaign": "spring", "source": "newsletter"}
        event = await svc.record_engagement_event(
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type="email_open",
            metadata=metadata,
        )
        # EventService uses flush() (Rule 121 — routers own commit).
        # Commit here so the re-read below sees the row.
        await async_session.commit()

        assert event.id is not None
        assert event.tenant_id == tenant_id
        assert event.customer_id == customer_id
        assert event.event_type == "email_open"
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
        self, db_schema, tenant_id, async_session
    ):
        """ScoreService.calculate_score runs and returns deterministic tier when score_factors are set."""
        await _seed_tenant(async_session, tenant_id)
        # score_factors giving score ~ 90 → tier A
        factors = {
            "engagement_level": 90,
            "deal_velocity": 90,
            "support_health": 90,
            "payment_history": 90,
            "product_adoption": 90,
        }
        customer_id = await _seed_customer(
            async_session, tenant_id, score_factors=factors
        )

        from services.event_service import EventService
        from services.score_service import ScoreService

        event_svc = EventService(async_session)
        score_svc = ScoreService(async_session)

        await event_svc.record_engagement_event(
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type="email_open",
        )
        # EventService uses flush() (Rule 121 — routers own commit).
        # Commit here so ScoreService's select sees the new score_factors-free
        # customer row (the seed above already flushed, so this commit is
        # a no-op for that row, but the service call's flush needs commit
        # for the new event row — the cross-test read in test 3 needs it).
        await async_session.commit()
        result = await score_svc.calculate_score(
            customer_id=customer_id, tenant_id=tenant_id
        )

        assert result.score >= 80
        assert result.tier.value == "A"
        assert result.tier_label == "A"

    async def test_cross_tenant_isolation_event_not_visible(
        self, db_schema, tenant_id, tenant_id_2, async_session
    ):
        """An event recorded for tenant A is invisible from tenant B's perspective."""
        await _seed_tenant(async_session, tenant_id)
        await _seed_tenant(async_session, tenant_id_2)
        customer_id_a = await _seed_customer(async_session, tenant_id)

        from services.event_service import EventService

        svc = EventService(async_session)
        await svc.record_engagement_event(
            tenant_id=tenant_id,
            customer_id=customer_id_a,
            event_type="email_open",
        )
        # Commit so the event row is visible to the cross-tenant score check.
        await async_session.commit()

        # From tenant B's perspective the customer does not exist (different tenant_id filter)
        # so a fresh ScoreService call must raise NotFoundException rather than return stale state.
        from services.score_service import ScoreService
        from pkg.errors.app_exceptions import NotFoundException

        score_svc = ScoreService(async_session)
        with pytest.raises(NotFoundException):
            await score_svc.calculate_score(
                customer_id=customer_id_a, tenant_id=tenant_id_2
            )


# ──────────────────────────────────────────────────────────────────────────────────────
#  Lead-tier filter and order_by_score — repository-level integration
# ──────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
class TestLeadTierAndOrderByScore:
    """GET /customers/ ?lead_tier=...&order_by_score=true integration tests."""

    async def test_lead_tier_filter_returns_only_matching_tier(
        self, db_schema, tenant_id, async_session
    ):
        """lead_tier='hot' returns only customers whose stored tier is 'A' (hot mapping)."""
        await _seed_tenant(async_session, tenant_id)
        customer_id_hot = await _seed_customer(async_session, tenant_id, tier="A")
        await _seed_customer(async_session, tenant_id, tier="B")
        await _seed_customer(async_session, tenant_id, tier="C")

        repo = CustomerRepository(async_session)
        items, total = await repo.list_customers(tenant_id=tenant_id, lead_tier="A")
        assert total == 1
        assert len(items) == 1
        assert items[0].id == customer_id_hot
        assert items[0].tier == "A"

    async def test_lead_tier_filter_with_no_matches_returns_empty(
        self, db_schema, tenant_id, async_session
    ):
        """lead_tier value that no customer has returns an empty result set."""
        await _seed_tenant(async_session, tenant_id)
        await _seed_customer(async_session, tenant_id, tier="A")
        await _seed_customer(async_session, tenant_id, tier="B")

        repo = CustomerRepository(async_session)
        items, total = await repo.list_customers(tenant_id=tenant_id, lead_tier="D")
        assert total == 0
        assert items == []

    async def test_order_by_score_returns_highest_scoring_first(
        self, db_schema, tenant_id, async_session
    ):
        """order_by_score=True sorts customers by score DESC (COALESCE NULLs to 0)."""
        await _seed_tenant(async_session, tenant_id)
        low_id = await _seed_customer(async_session, tenant_id, score=10)
        mid_id = await _seed_customer(async_session, tenant_id, score=50)
        high_id = await _seed_customer(async_session, tenant_id, score=90)
        await _seed_customer(async_session, tenant_id, score=None)  # NULL → 0

        repo = CustomerRepository(async_session)
        items, total = await repo.list_customers(tenant_id=tenant_id, order_by_score=True)
        assert total == 4
        # Highest first, NULLs treated as 0 (last in DESC order)
        ids_in_order = [c.id for c in items]
        assert ids_in_order.index(high_id) < ids_in_order.index(mid_id)
        assert ids_in_order.index(mid_id) < ids_in_order.index(low_id)

    async def test_default_ordering_unchanged_without_order_by_score(
        self, db_schema, tenant_id, async_session
    ):
        """Without order_by_score the default created_at DESC ordering is preserved."""
        from datetime import datetime, timedelta, timezone

        await _seed_tenant(async_session, tenant_id)
        # Seed customers with explicit, distinct created_at timestamps so DESC ordering is deterministic
        base = datetime.now(timezone.utc)
        ids: list[int] = []
        for offset_minutes in range(3):
            customer = CustomerModel(
                tenant_id=tenant_id,
                name=f"Order {offset_minutes}",
                email=f"order_{offset_minutes}@example.com",
                status="lead",
                owner_id=0,
                tags=[],
                created_at=base + timedelta(minutes=offset_minutes),
                updated_at=base + timedelta(minutes=offset_minutes),
            )
            async_session.add(customer)
            await async_session.flush()
            ids.append(customer.id)
        first_id, second_id, third_id = ids

        repo = CustomerRepository(async_session)
        items, _total = await repo.list_customers(tenant_id=tenant_id)
        ids_in_order = [c.id for c in items]
        # Most-recently-created first
        assert ids_in_order[0] == third_id
        assert ids_in_order[-1] == first_id

    async def test_lead_tier_and_order_by_score_combine(
        self, db_schema, tenant_id, async_session
    ):
        """lead_tier + order_by_score combine: filter then sort by score DESC."""
        await _seed_tenant(async_session, tenant_id)
        hot_low = await _seed_customer(async_session, tenant_id, tier="A", score=20)
        hot_high = await _seed_customer(async_session, tenant_id, tier="A", score=95)
        await _seed_customer(async_session, tenant_id, tier="B", score=99)  # excluded

        repo = CustomerRepository(async_session)
        items, total = await repo.list_customers(
            tenant_id=tenant_id, lead_tier="A", order_by_score=True
        )
        assert total == 2
        assert [c.id for c in items] == [hot_high, hot_low]

    async def test_lead_tier_invalid_raises_validation_in_service(
        self, db_schema, tenant_id, async_session
    ):
        """Service-layer validation rejects unknown lead_tier values with ValidationException."""
        await _seed_tenant(async_session, tenant_id)
        await _seed_customer(async_session, tenant_id)

        from pkg.errors.app_exceptions import ValidationException

        svc = CustomerService(CustomerRepository(async_session))
        with pytest.raises(ValidationException, match="lead_tier must be one of"):
            await svc.list_customers(tenant_id=tenant_id, lead_tier="bogus")

    async def test_lead_tier_hot_via_service_maps_to_tier_a(
        self, db_schema, tenant_id, async_session
    ):
        """Service-level lead_tier='hot' is translated to stored tier 'A' before SQL filtering."""
        await _seed_tenant(async_session, tenant_id)
        customer_id_a = await _seed_customer(async_session, tenant_id, tier="A")
        await _seed_customer(async_session, tenant_id, tier="B")
        await _seed_customer(async_session, tenant_id, tier="C")

        svc = CustomerService(CustomerRepository(async_session))
        items, total = await svc.list_customers(tenant_id=tenant_id, lead_tier="hot")
        assert total == 1
        assert [c.id for c in items] == [customer_id_a]
