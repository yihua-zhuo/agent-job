"""Shared cross-domain seed helpers for integration tests.

These are intentionally tiny: they exist so that domain test classes
do not each have to redefine a near-identical `_seed_user` method.
Domain-specific fixtures (e.g. customer) still live in their own
domain_fixtures/<domain>.py modules per Rule 125.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from services.user_service import UserService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def seed_user(
    async_session: AsyncSession,
    tenant_id: int,
    *,
    username_prefix: str = "user",
    email_prefix: str = "user",
) -> int:
    """Create a user for the given tenant and return their id.

    Used by several integration test classes that need a real user
    record (e.g. for created_by FK enforcement).
    """
    user_svc = UserService(async_session)
    suffix = uuid.uuid4().hex[:8]
    reg = await user_svc.create_user(
        username=f"{username_prefix}_{suffix}",
        email=f"{email_prefix}_{suffix}@example.com",
        password="Test@Pass1234",
        tenant_id=tenant_id,
    )
    return reg.id
