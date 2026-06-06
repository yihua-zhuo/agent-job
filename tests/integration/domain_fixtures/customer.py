"""Customer domain integration test helpers — seeding and service wiring."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel

# owner_id=0 is the application-wide sentinel for "no owner assigned" — used
# by the lead distribution flow to distinguish unassigned leads from leads
# that have been recycled (recycle_count > 0 but owner_id set to a real user).
UNASSIGNED_OWNER_ID = 0


async def seed_customer(
    async_session: AsyncSession,
    tenant_id: int,
    *,
    name_suffix: str | None = None,
    score: int | None = None,
    tier: str | None = None,
    score_factors: dict | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> int:
    """Seed a customer row and return its primary key id.

    ``created_at`` / ``updated_at`` are accepted so tests that need a
    deterministic created_at ordering (e.g. default ORDER BY in
    list_customers) do not have to build the model inline.
    """
    suffix = name_suffix or uuid.uuid4().hex[:8]
    customer = CustomerModel(
        tenant_id=tenant_id,
        name=f"Eng Cust {suffix}",
        email=f"eng_{suffix}@example.com",
        status="lead",
        owner_id=UNASSIGNED_OWNER_ID,
        tags=[],
        score=score,
        tier=tier,
        score_factors=score_factors,
    )
    if created_at is not None:
        customer.created_at = created_at
    if updated_at is not None:
        customer.updated_at = updated_at
    async_session.add(customer)
    await async_session.flush()
    return customer.id


@pytest_asyncio.fixture
async def _seed_customer(async_session, _seed_tenant, tenant_id):
    """Domain fixture: seed a customer in the current tenant.

    Returns a callable so individual tests can override score/tier/etc.
    Pass ``tenant_id=...`` to seed into a different tenant (used by
    cross-tenant isolation tests).
    """
    async def _factory(
        *,
        tenant_id: int = tenant_id,
        name_suffix: str | None = None,
        score: int | None = None,
        tier: str | None = None,
        score_factors: dict | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> int:
        return await seed_customer(
            async_session,
            tenant_id,
            name_suffix=name_suffix,
            score=score,
            tier=tier,
            score_factors=score_factors,
            created_at=created_at,
            updated_at=updated_at,
        )

    return _factory


@pytest_asyncio.fixture
async def customer_service(async_session):
    """Wire CustomerService with the test session for service-level tests.

    The service constructs its own CustomerRepository internally — tests
    only need to provide the session.
    """
    from services.customer_service import CustomerService

    return CustomerService(async_session)


__all__ = ["seed_customer", "_seed_customer", "customer_service"]
