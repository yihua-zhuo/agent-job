"""Customer domain integration test helpers — seeding and service wiring."""

from __future__ import annotations

import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel


async def seed_customer(
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


@pytest_asyncio.fixture
async def _seed_customer(async_session, _seed_tenant, tenant_id):
    """Domain fixture: seed a customer in the current tenant.

    Returns a callable so individual tests can override score/tier/etc.
    """
    async def _factory(
        *,
        name_suffix: str | None = None,
        score: int | None = None,
        tier: str | None = None,
        score_factors: dict | None = None,
    ) -> int:
        return await seed_customer(
            async_session,
            tenant_id,
            name_suffix=name_suffix,
            score=score,
            tier=tier,
            score_factors=score_factors,
        )

    return _factory


@pytest_asyncio.fixture
async def customer_service(async_session):
    """Wire CustomerService with a real CustomerRepository + session for service-level tests."""
    from db.repositories.customer import CustomerRepository
    from services.customer_service import CustomerService

    return CustomerService(CustomerRepository(async_session))


__all__ = ["seed_customer", "_seed_customer", "customer_service"]
