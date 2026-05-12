"""SQLAlchemy engine, session, and base infrastructure — sync + async.

The sync layer (create_engine) is for scripts / non-FastAPI use.
The async layer (create_async_engine) is for FastAPI / service use.
"""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING
from urllib.parse import unquote

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

# ---------------------------------------------------------------------------
# Sync engine (legacy / script use)
# ---------------------------------------------------------------------------

_sync_engine = None
_sync_engine_lock = threading.Lock()
_sync_session_factory = None
_sync_session_lock = threading.Lock()


def create_engine_from_env():
    """Create a sync SQLAlchemy Engine from the DATABASE_URL environment variable.

    Raises:
        ValueError: If DATABASE_URL is not set or is empty.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ValueError("DATABASE_URL environment variable is required")
    return create_engine(url, pool_pre_ping=True, pool_size=5)


def get_engine():
    """Get or create the singleton sync Engine instance."""
    global _sync_engine
    if _sync_engine is None:
        with _sync_engine_lock:
            if _sync_engine is None:
                _sync_engine = create_engine_from_env()
    return _sync_engine


Base = declarative_base()


def get_session():
    """Create a sync Session bound to the lazily initialized Engine."""
    global _sync_session_factory
    if _sync_session_factory is None:
        with _sync_session_lock:
            if _sync_session_factory is None:
                _sync_session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _sync_session_factory()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of sync operations.

    Yields a Session. Commits on normal exit, rolls back on exception,
    and always closes the session.
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Async engine (FastAPI / service use)
# ---------------------------------------------------------------------------

_async_engine: AsyncEngine | None = None
_async_engine_lock = threading.Lock()
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_async_session_lock = threading.Lock()


def _build_async_engine(url: str) -> AsyncEngine:
    """Build an async engine, handling Supabase connection specifics."""
    connect_args: dict = {}
    if "pooler.supabase.com" in url:
        # Parse Supabase pooler URL manually since # in password breaks stdlib URL parsing
        creds_start = url.index("://") + 3
        creds_end = url.rfind("@")
        credentials = url[creds_start:creds_end]
        user_part, password = credentials.rsplit(":", 1)
        password = unquote(password)
        host_port = url[creds_end + 1:]
        last_colon = host_port.rfind(":")
        host = host_port[:last_colon]
        port_and_path = host_port[last_colon + 1:]
        if "/" in port_and_path:
            port, path = port_and_path.split("/", 1)
            path = "/" + path
        else:
            port = port_and_path
            path = ""

        # Supabase pooler host — configurable via env var to avoid hardcoded IP
        pooler_host = os.environ.get("SUPABASE_POOLER_HOST", "13.114.6.6")

        connect_args = {
            "host": pooler_host,
            "user": user_part,
            "password": password,
            "database": path.lstrip("/") or "postgres",
            "timeout": 10,
            "statement_cache_size": 0,
        }
        # Rebuild URL without credentials for asyncpg
        url = f"postgresql+asyncpg://{user_part}@{pooler_host}:{port}{path}"
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return create_async_engine(url, pool_pre_ping=True, pool_size=5, connect_args=connect_args or None)


def create_async_engine_from_env() -> AsyncEngine:
    """Create an async Engine from DATABASE_URL.

    Raises:
        ValueError: If DATABASE_URL is not set or is empty.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ValueError("DATABASE_URL environment variable is required")
    return _build_async_engine(url)


def get_async_engine() -> AsyncEngine:
    """Get or create the singleton async Engine instance."""
    global _async_engine
    if _async_engine is None:
        with _async_engine_lock:
            if _async_engine is None:
                _async_engine = create_async_engine_from_env()
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the singleton async sessionmaker."""
    global _async_session_factory
    if _async_session_factory is None:
        with _async_session_lock:
            if _async_session_factory is None:
                _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _async_session_factory


@asynccontextmanager
async def async_session_scope():
    """Async transactional scope — use this in all service methods.

    Yields an AsyncSession. Commits on normal exit, rolls back on exception,
    always closes the session.

    Usage::

        async def my_service_method(tenant_id: int) -> MyModel:
            async with async_session_scope() as session:
                result = await session.execute(
                    select(MyModel).where(MyModel.tenant_id == tenant_id)
                )
                return result.scalar_one_or_none()
    """
    factory = get_async_session_factory()
    session: AsyncSession = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()