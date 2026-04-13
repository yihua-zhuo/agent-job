"""Async SQLAlchemy session management for PostgreSQL."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_async_engine = None
_async_session_factory = None


def _get_async_engine():
    """Lazily create and return the singleton async engine."""
    global _async_engine
    if _async_engine is None:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise ValueError("DATABASE_URL environment variable is required")
        # Ensure the URL uses the asyncpg driver.
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        _async_engine = create_async_engine(url, pool_pre_ping=True, pool_size=5)
    return _async_engine


def _get_session_factory() -> async_sessionmaker:
    """Lazily create and return the singleton async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = _get_async_engine()
        _async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _async_session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session.

    Commits on normal exit, rolls back on exception, always closes the session.

    Usage::

        async with get_db_session() as session:
            result = await session.execute(select(UserModel).where(...))
    """
    factory = _get_session_factory()
    session: AsyncSession = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
