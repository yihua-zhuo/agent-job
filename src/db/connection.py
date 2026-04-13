"""Async SQLAlchemy session management for PostgreSQL."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Lazily-initialised singletons exposed as public module-level names.
# Use `reset_engine()` to re-initialise (e.g. in test conftest fixtures).
engine: AsyncSession = None
async_session_maker: async_sessionmaker = None


def _build_engine(url: str):
    """Create the async engine from *url*."""
    # Ensure the URL uses the asyncpg driver.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return create_async_engine(url, pool_pre_ping=True, pool_size=5)


def _init_engine(url: str):
    global engine, async_session_maker
    engine = _build_engine(url)
    async_session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _lazy_init():
    """Initialise the singletons from DATABASE_URL on first use."""
    global engine, async_session_maker
    if engine is None:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise ValueError("DATABASE_URL environment variable is required")
        _init_engine(url)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session.

    Commits on normal exit, rolls back on exception, always closes the session.

    Usage::

        async with get_db_session() as session:
            result = await session.execute(select(UserModel).where(...))
    """
    _lazy_init()
    session: AsyncSession = async_session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def reset_engine(database_url: str):
    """Reinitialise the engine and session maker with *database_url*.

    Call this in test conftest fixtures *before* any service code runs so that
    all subsequent ``async with get_db_session()`` calls use the test database.
    """
    global engine, async_session_maker
    _init_engine(database_url)
