"""Seed helpers for churn prediction integration tests."""

from __future__ import annotations

from db.models.customer import CustomerModel


async def seed_churn_customer(async_session, tenant_id: int) -> int:
    """Create a customer and return its id."""
    customer = CustomerModel(
        tenant_id=tenant_id,
        name="Churn Test Customer",
        email="churn-test@example.com",
        status="active",
    )
    async_session.add(customer)
    await async_session.flush()
    return customer.id
