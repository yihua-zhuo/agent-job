"""Notification-domain fixtures — tenant and user seeding helpers."""

from __future__ import annotations

import uuid

import pytest_asyncio


@pytest_asyncio.fixture
async def _seed_notification_user(async_session, tenant_id: int, _seed_tenant) -> int:
    """Seed tenant + user so notification FK constraints are satisfied.

    Returns the user_id of the inserted row.
    """
    from services.user_service import UserService

    user_svc = UserService(async_session)
    suffix = uuid.uuid4().hex[:8]
    user = await user_svc.create_user(
        username=f"notif_{suffix}",
        email=f"notif_{suffix}@example.com",
        password="TestPass123!",
        tenant_id=tenant_id,
    )
    await async_session.flush()
    return user.id
