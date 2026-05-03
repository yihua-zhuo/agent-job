"""Async SQLAlchemy session management for PostgreSQL."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

# Lazily-initialised singletons exposed as public module-level names.
# Use `reset_engine()` to re-initialise (e.g. in test conftest fixtures).
engine: AsyncEngine = None  # type: ignore
async_session_maker: async_sessionmaker = None  # type: ignore


def _build_engine(url: str) -> AsyncEngine:
    """Create the async engine from *url*."""
    connect_args: dict = {}
    if "pooler.supabase.com" in url:
        # Use string slicing since URL has # in password making stdlib parsing fragile
        creds_start = url.index("://") + 3
        creds_end = url.rfind("@")
        credentials = url[creds_start:creds_end]
        user_part, password = credentials.rsplit(":", 1)
        host_port = url[creds_end + 1 :]
        last_colon = host_port.rfind(":")
        host = host_port[:last_colon]
        port_and_path = host_port[last_colon + 1 :]
        if "/" in port_and_path:
            port, path = port_and_path.split("/", 1)
            path = "/" + path
        else:
            port = port_and_path
            path = ""
        connect_args = {
            "host": "13.114.6.6",
            "user": user_part,
            "password": password,
            "database": path.lstrip("/") or "postgres",
            "timeout": 10,
            "statement_cache_size": 0,
        }
        # Pass credentials via connect_args only; URL carries no password
        url = f"postgresql+asyncpg://{user_part}@13.114.6.6:{port}{path}"
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return create_async_engine(url, pool_pre_ping=True, pool_size=5, connect_args=connect_args or None)


def _init_engine(url: str):
    global engine, async_session_maker
    engine = _build_engine(url)
    async_session_maker = async_sessionmaker(  # type: ignore
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def _lazy_init():
    """Initialise the singletons from settings on first use."""
    global engine, async_session_maker
    if engine is None:
        from configs.settings import settings
        url = settings.database_url
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
    session: AsyncSession = async_session_maker()  # type: ignore
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def ensure_engine():
    """Warm-up entry point for FastAPI lifespan. Idempotent."""
    _lazy_init()


def dispose_engine():
    """Dispose engine pool on FastAPI shutdown."""
    global engine, async_session_maker
    if engine is not None:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(engine.dispose())
    engine = None
    async_session_maker = None


def reset_engine(database_url: str):
    """Reinitialise the engine and session maker with *database_url*.

    Call this in test conftest fixtures *before* any service code runs so that
    all subsequent ``async with get_db_session()`` calls use the test database.
    """
    global engine, async_session_maker
    _init_engine(database_url)


# ---------------------------------------------------------------------------
# FastAPI dependency — use this in route handlers via Depends(get_session)
# ---------------------------------------------------------------------------
from typing import Annotated

from fastapi import Depends


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async SQLAlchemy session.

    Commits on normal exit, rolls back on exception, always closes the session.

    Usage::

        @router.get("/")
        async def list_users(session: AsyncSession = Depends(get_db)):
            ...
    """
    _lazy_init()
    session: AsyncSession = async_session_maker()  # type: ignore
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Convenience type alias for route dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_db)]
