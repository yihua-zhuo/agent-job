"""Integration tests for users list filtering (q and role params).

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_users_integration.py -v

Requires DATABASE_URL pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import uuid

import pytest

from services.user_service import UserService


async def _seed_user(async_session, tenant_id: int, username: str, email: str, role: str = "user") -> int:
    """Create a user and return their id."""
    svc = UserService(async_session)
    user = await svc.create_user(
        username=username,
        email=email,
        password="Test@Pass1234",
        role=role,
        tenant_id=tenant_id,
    )
    return user.id


@pytest.mark.integration
class TestListUsersFiltered:
    async def test_list_users_no_filter(self, db_schema, tenant_id, async_session):
        svc = UserService(async_session)
        await _seed_user(async_session, tenant_id, "alice01", "alice01@example.com", "admin")
        await _seed_user(async_session, tenant_id, "bob02", "bob02@example.com", "user")
        await _seed_user(async_session, tenant_id, "carol03", "carol03@example.com", "manager")

        items, total = await svc.list_users(tenant_id=tenant_id)
        assert total == 3

    async def test_list_users_filter_by_q(self, db_schema, tenant_id, async_session):
        svc = UserService(async_session)
        await _seed_user(async_session, tenant_id, "alice_w", "alice_w@example.com", "user")
        await _seed_user(async_session, tenant_id, "bob_a", "bob_a@example.com", "user")
        await _seed_user(async_session, tenant_id, "charlie", "charlie_doe@example.com", "user")

        items, total = await svc.list_users(q="alice", tenant_id=tenant_id)
        assert total == 1
        assert items[0].username == "alice_w"

    async def test_list_users_filter_by_role(self, db_schema, tenant_id, async_session):
        svc = UserService(async_session)
        await _seed_user(async_session, tenant_id, "admin1", "admin1@example.com", "admin")
        await _seed_user(async_session, tenant_id, "admin2", "admin2@example.com", "admin")
        await _seed_user(async_session, tenant_id, "manager1", "manager1@example.com", "manager")
        await _seed_user(async_session, tenant_id, "user1", "user1@example.com", "user")

        items, total = await svc.list_users(role="admin", tenant_id=tenant_id)
        assert total == 2
        assert all(u.role == "admin" for u in items)

    async def test_list_users_filter_by_q_and_role(self, db_schema, tenant_id, async_session):
        svc = UserService(async_session)
        await _seed_user(async_session, tenant_id, "alice_admin", "alice_admin@example.com", "admin")
        await _seed_user(async_session, tenant_id, "alice_user", "alice_user@example.com", "user")
        await _seed_user(async_session, tenant_id, "bob_admin", "bob_admin@example.com", "admin")
        await _seed_user(async_session, tenant_id, "bob_user", "bob_user@example.com", "user")

        items, total = await svc.list_users(q="alice", role="admin", tenant_id=tenant_id)
        assert total == 1
        assert items[0].username == "alice_admin"
        assert items[0].role == "admin"

    async def test_list_users_filter_by_full_name(self, db_schema, tenant_id, async_session):
        svc = UserService(async_session)
        await _seed_user(async_session, tenant_id, "usr001", "usr001@example.com", "user")
        await svc.create_user(
            username="alice_full",
            email="alice_full@example.com",
            password="Test@Pass1234",
            role="user",
            full_name="Alice Johnson",
            tenant_id=tenant_id,
        )
        await svc.create_user(
            username="bob_full",
            email="bob_full@example.com",
            password="Test@Pass1234",
            role="user",
            full_name="Bob Smith",
            tenant_id=tenant_id,
        )

        items, total = await svc.list_users(q="alice", tenant_id=tenant_id)
        assert total == 1
        assert items[0].username == "alice_full"

    async def test_list_users_pagination(self, db_schema, tenant_id, async_session):
        svc = UserService(async_session)
        for i in range(5):
            await _seed_user(async_session, tenant_id, f"pageuser{i}", f"pageuser{i}@example.com", "user")

        page1, total1 = await svc.list_users(page=1, page_size=2, tenant_id=tenant_id)
        assert total1 == 5
        assert len(page1) == 2

        page2, total2 = await svc.list_users(page=2, page_size=2, tenant_id=tenant_id)
        assert total2 == 5
        assert len(page2) == 2

        page3, total3 = await svc.list_users(page=3, page_size=2, tenant_id=tenant_id)
        assert total3 == 5
        assert len(page3) == 1