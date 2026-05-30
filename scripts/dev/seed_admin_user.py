#!/usr/bin/env python3
"""Seed a login-capable admin user for local development.

Idempotent: if the user already exists, this script is a no-op and reports
the existing record. Otherwise it creates the user via ``AuthService`` (so
the bcrypt password hash matches what login expects) and flips status to
``active`` so the OAuth2 password flow succeeds immediately.

Env vars (all optional, defaults are for LOCAL DEV ONLY):
    DATABASE_URL    Required. e.g. ``postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db``
    SEED_USERNAME   default ``admin``
    SEED_EMAIL      default ``admin@example.com``
    SEED_PASSWORD   default ``admin12345``  (must meet UserService validator)
    SEED_ROLE       default ``admin``
    SEED_TENANT_ID  default ``0``

Designed to be invoked from the Makefile after ``db-up`` + ``migrate``.
"""

from __future__ import annotations

import asyncio
import os
import sys

# scripts/dev/ runs with PYTHONPATH=src set by the Makefile target.
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models.user import UserModel
from services.auth_service import AuthService


def env(key: str, default: str) -> str:
    val = os.environ.get(key, default)
    return val if val else default


async def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("error: DATABASE_URL not set", file=sys.stderr)
        return 2

    username = env("SEED_USERNAME", "admin")
    email = env("SEED_EMAIL", "admin@example.com")
    password = env("SEED_PASSWORD", "admin12345")
    role = env("SEED_ROLE", "admin")
    tenant_id = int(env("SEED_TENANT_ID", "0"))

    # AuthService requires a non-empty secret. The seed script doesn't issue
    # any tokens — it only needs the constructor to succeed — so pass a
    # placeholder. Real backend reads from settings.jwt_secret / env.
    secret = os.environ.get("JWT_SECRET_KEY") or "dev-seed-only"

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            existing = await session.execute(
                select(UserModel).where(
                    and_(UserModel.username == username, UserModel.tenant_id == tenant_id)
                )
            )
            row = existing.scalar_one_or_none()
            if row is not None:
                print(
                    f"user already exists: id={row.id} username={row.username} "
                    f"tenant_id={row.tenant_id} role={row.role} status={row.status}"
                )
                _print_login_hint(username, password)
                return 0

            svc = AuthService(session, secret_key=secret)
            user = await svc.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
                tenant_id=tenant_id,
            )
            # `create_user` sets status="pending"; flip to active so the
            # OAuth2 password flow accepts the user without an extra
            # activation hop.
            user.status = "active"
            await session.commit()
            print(
                f"created user: id={user.id} username={user.username} "
                f"email={user.email} tenant_id={user.tenant_id} role={user.role} "
                f"status={user.status}"
            )
            _print_login_hint(username, password)
            return 0
    finally:
        await engine.dispose()


def _print_login_hint(username: str, password: str) -> None:
    print()
    print("login (curl example — backend must be running):")
    print('  curl -X POST http://localhost:8000/api/v1/auth/login \\')
    print('       -H "Content-Type: application/x-www-form-urlencoded" \\')
    print(f'       -d "username={username}&password={password}"')


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
