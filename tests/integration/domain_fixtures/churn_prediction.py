"""Seed helpers for churn prediction integration tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from db.models.identity import TenantModel


async def seed_churn_customer(async_session: AsyncSession, tenant_id: int) -> int:
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


async def seed_churn_tenant(
    async_session: AsyncSession, tenant_id: int, name: str = "Churn Integration Test Tenant"
) -> int:
    """Seed a tenant record so FK constraints are satisfied. Returns the tenant_id."""
    tenant = TenantModel(
        id=tenant_id,
        name=name,
        plan="free",
        status="active",
    )
    async_session.add(tenant)
    await async_session.flush()
    return tenant_id
