"""Async SQLAlchemy session infrastructure — Supabase PostgreSQL foundation.

Usage in services::

    from internal.db import session_scope

    async with session_scope() as session:
        result = await session.execute(
            select(MyModel).where(
                MyModel.tenant_id == tenant_id,
                MyModel.id == some_id,
            )
        )
        return result.scalar_one_or_none()

Usage in FastAPI routes::

    from internal.db import SessionDep

    async def my_route(session: SessionDep):
        ...

Acceptance criteria:
  1) create_engine_from_env() — reads DATABASE_URL env var
  2) get_async_engine() singleton with pool_pre_ping=True, pool_size=5
  3) SessionLocal() async_sessionmaker with autoflush=False, autocommit=False
  4) Base declarative base
  5) session_scope() async context manager for safe transaction handling
  6) All services use session_scope() via SessionDep / get_db dependency
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from internal.db.engine import (
    Base,
    async_session_scope,
    create_async_engine_from_env,
    create_engine_from_env,
    get_async_engine,
    get_async_session_factory,
    get_engine,
)

# ---------------------------------------------------------------------------
# Public async sessionmaker — lazily initialised on first call
# ---------------------------------------------------------------------------

def SessionLocal() -> async_sessionmaker[AsyncSession]:
    """Lazily-initialised async sessionmaker.

    Usage::

        factory = SessionLocal()
        session = factory()
    """
    return get_async_session_factory()


# ---------------------------------------------------------------------------
# Async session scope — the primary interface for all services
# ---------------------------------------------------------------------------

@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Async transactional scope for safe DB access in all services.

    Commits on normal exit, rolls back on exception, always closes the session.

    Usage::

        async with session_scope() as session:
            result = await session.execute(select(MyModel).where(...))
            return result.scalar_one_or_none()
    """
    async with async_session_scope() as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI route dependency — prefer SessionDep type alias instead."""
    async with async_session_scope() as session:
        yield session


# Typed dependency alias — use this in route handlers
SessionDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Core
    "Base",
    "create_engine_from_env",
    "create_async_engine_from_env",
    "get_engine",
    "get_async_engine",
    # Session
    "SessionLocal",
    "session_scope",
    "async_session_scope",
    # FastAPI
    "get_db",
    "SessionDep",
]
