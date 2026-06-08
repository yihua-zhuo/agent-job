"""Async SQLAlchemy session management for PostgreSQL."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import quote, unquote, urlparse

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

# Lazily-initialised singletons exposed as public module-level names.
# Use `reset_engine()` to re-initialise (e.g. in test conftest fixtures).
engine: AsyncEngine = None  # type: ignore
async_session_maker: async_sessionmaker = None  # type: ignore


def _build_engine(url: str) -> AsyncEngine:
    """Create the async engine from *url*."""
    connect_args: dict = {}
    if "pooler.supabase.com" in url:
        # Parse the URL with urllib so we correctly handle percent-encoded
        # passwords (e.g. '#' encoded as %23). Manual index/rfind slicing
        # is fragile when the password contains reserved characters.
        parsed = urlparse(url)
        user_part = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        host_port = parsed.netloc.split("@")[-1] if "@" in parsed.netloc else parsed.netloc
        last_colon = host_port.rfind(":")
        if last_colon == -1:
            port, path = "", parsed.path or ""
        else:
            port = host_port[last_colon + 1 :]
            path = parsed.path or ""
        connect_args = {
            "host": "13.114.6.6",
            "user": user_part,
            "password": password,
            "database": path.lstrip("/") or "postgres",
            "timeout": 10,
            "statement_cache_size": 0,
        }
        # Re-quote the user portion so any reserved characters survive
        # the round-trip into the driver URL.
        url = f"postgresql+asyncpg://{quote(user_part, safe='')}@13.114.6.6:{port}{path}"
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return create_async_engine(url, pool_pre_ping=True, pool_size=5, connect_args=connect_args or {})


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


async def dispose_async_engine():
    """Dispose the async engine pool and reset the singletons.

    Async variant — call this from within an async lifespan handler::

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            yield
            await dispose_async_engine()
    """
    global engine, async_session_maker
    if engine is not None:
        await engine.dispose()
    engine = None
    async_session_maker = None


def _dispose_engine_unsafe():
    """Synchronous engine disposer — UNSAFE inside a running event loop.

    Private helper: only intended for the atexit hook that runs after
    the main event loop has already stopped. Calling
    ``asyncio.new_event_loop()`` and ``run_until_complete`` from inside
    an already-running loop will deadlock the loop and the caller will
    block forever. Always prefer ``dispose_async_engine`` from async
    code.

    Raises ``RuntimeError`` if called from inside a running event loop.
    Detection has a TOCTOU window — concurrent threads starting a
    loop between the check and the new_event_loop call can still
    cause a hang, so callers must ensure single-threaded use.
    """
    global engine, async_session_maker
    if engine is not None:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "_dispose_engine_unsafe() called from within a running event loop; "
                "use await dispose_async_engine() instead."
            )
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(engine.dispose())
        finally:
            loop.close()
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


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async SQLAlchemy session.

    Commits on normal exit, rolls back on exception, always closes the session.

    The active session is attached to ``request.state.db`` so it is
    available to FastAPI dependencies and middleware that need
    access to the live session outside the dependency-injection scope
    (e.g. for logging or observability hooks). The state is cleared
    in the ``finally`` block to avoid stale references on the request
    object if the response is re-used.

    Usage::

        @router.get("/")
        async def list_users(session: AsyncSession = Depends(get_db)):
            ...
    """
    ensure_engine()
    session: AsyncSession = async_session_maker()  # type: ignore
    request.state.db = session
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        if getattr(request.state, "db", None) is session:
            request.state.db = None


# Convenience type alias for route dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_db)]
