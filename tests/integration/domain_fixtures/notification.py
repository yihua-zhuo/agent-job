"""Notification-domain fixtures — tenant and customer seeding helpers."""
from __future__ import annotations

import pytest_asyncio


@pytest_asyncio.fixture
async def _seed_tenant(async_session, tenant_id: int) -> int:
    """Seed a tenant record so FK constraints on notifications are satisfied.

    Returns the tenant_id (same as input, for caller convenience).
    """
    from db.models.tenant import TenantModel

    tenant = TenantModel(
        id=tenant_id,
        name="Integration Test Tenant",
        plan="free",
        status="active",
    )
    async_session.add(tenant)
    await async_session.flush()
    return tenant_id


@pytest_asyncio.fixture
async def _seed_customer(async_session, tenant_id, _seed_tenant):
    """Seed a customer record for the given tenant so FK constraints are satisfied.

    Returns the customer_id of the inserted row.
    """
    from db.models.customer import CustomerModel

    customer = CustomerModel(
        tenant_id=tenant_id,
        name="Integration Test Customer",
        email="test-customer@example.com",
        status="active",
    )
    async_session.add(customer)
    await async_session.flush()
    return customer.id
