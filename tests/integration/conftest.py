"""Pytest configuration for integration tests.

Uses a real PostgreSQL database (Supabase by default; override with
TEST_DATABASE_URL env var). Each test function gets a clean schema via
TRUNCATE CASCADE.

Services import `get_db_session` at module load time by name:
    from db.connection import get_db_session
so we monkey-patch that attribute on every service module (not just on
db.connection) so the services transparently use the test DB session.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import pkgutil
import random
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator

# Ensure src/ is on sys.path so top-level package imports resolve
_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


# ── Test database URL ────────────────────────────────────────────────────────────
_DEFAULT_TEST_DB = (
    "postgresql+asyncpg://postgres.unkojburovuewvojcepd:"
    "+t%26d%2BSCF4f69k.y@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
)

TEST_DATABASE_URL: str = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB)
TEST_SYNC_DATABASE_URL: str = TEST_DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql://", 1
)

# Ensure required env vars are present for services instantiated in tests.
os.environ.setdefault("JWT_SECRET_KEY", "integration-test-jwt-secret-key")
os.environ.setdefault("SECRET_KEY", "integration-test-secret-key")
os.environ.setdefault("DATABASE_URL", TEST_SYNC_DATABASE_URL)


# ── Singleton test engine / factory ──────────────────────────────────────────────
_test_async_engine = None
_test_async_session_factory = None
_test_sync_engine = None


def _get_test_async_engine():
    global _test_async_engine
    if _test_async_engine is None:
        _test_async_engine = create_async_engine(
            TEST_DATABASE_URL, poolclass=NullPool, echo=False
        )
    return _test_async_engine


def _get_test_async_session_factory():
    global _test_async_session_factory
    if _test_async_session_factory is None:
        _test_async_session_factory = async_sessionmaker(
            bind=_get_test_async_engine(),
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
        )
    return _test_async_session_factory


def _get_test_sync_engine():
    global _test_sync_engine
    if _test_sync_engine is None:
        from sqlalchemy import create_engine

        _test_sync_engine = create_engine(
            TEST_SYNC_DATABASE_URL, pool_pre_ping=True, pool_size=3
        )
    return _test_sync_engine


# ── Async session provider used by services during integration tests ─────────────
@contextlib.asynccontextmanager
async def _test_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = _get_test_async_session_factory()
    session: AsyncSession = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def _iter_service_modules():
    """Yield every `services.*` submodule that was imported."""
    import services  # noqa: WPS433 - local import so services package is loaded

    for info in pkgutil.iter_modules(services.__path__, prefix="services."):
        try:
            yield importlib.import_module(info.name)
        except Exception:  # pragma: no cover - best-effort patching
            continue


def _install_test_db_session():
    """Patch get_db_session everywhere a service has already imported it."""
    import db.connection as conn_mod

    conn_mod.get_db_session = _test_get_db_session
    conn_mod.engine = _get_test_async_engine()
    conn_mod.async_session_maker = _get_test_async_session_factory()

    for mod in _iter_service_modules():
        if hasattr(mod, "get_db_session"):
            mod.get_db_session = _test_get_db_session


# ── Schema setup / teardown ──────────────────────────────────────────────────────
_TABLES = [
    "pipeline_stages",
    "pipelines",
    "activities",
    "workflows",
    "campaign_events",
    "campaigns",
    "dashboards",
    "reports",
    "tickets",
    "ticket_replies",
    "users",
    "opportunities",
    "contacts",
    "customers",
    "tenants",
    "notifications",
    "reminders",
    "tasks",
]


@pytest.fixture(scope="session")
def fresh_schema() -> Generator[None, None, None]:
    """Create/recreate the full test schema once per test session."""
    # 1. Patch the async session so services hit the test DB.
    _install_test_db_session()

    # 2. Ensure ORM models are registered with Base.metadata.
    import db.base as db_base_module  # noqa: F401
    import db.models  # noqa: F401

    # 3. Drop and recreate all tables via the sync engine.
    sync_engine = _get_test_sync_engine()
    with sync_engine.begin() as conn:
        for tbl in _TABLES:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
            except Exception:
                pass

    db_base_module.Base.metadata.create_all(bind=sync_engine)

    yield

    if _test_sync_engine is not None:
        _test_sync_engine.dispose()


@pytest.fixture(scope="function")
def db_schema(fresh_schema) -> Generator[None, None, None]:
    """Truncate all tables between each test for function-level isolation."""
    sync_engine = _get_test_sync_engine()
    with sync_engine.begin() as conn:
        for table in _TABLES:
            try:
                conn.execute(
                    text(f"TRUNCATE {table} CASCADE RESTART IDENTITY")
                )
            except Exception:
                pass
    yield


# ── Direct-session fixtures for tests that want explicit DB access ──────────────
@pytest_asyncio.fixture(scope="function")
async def async_session(db_schema) -> AsyncGenerator[AsyncSession, None]:
    factory = _get_test_async_session_factory()
    async with factory() as session:
        yield session


@pytest.fixture(scope="function")
def sync_session(db_schema) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(
        bind=_get_test_sync_engine(), autoflush=False, autocommit=False
    )
    with SessionLocal() as session:
        yield session


# ── Tenant ID fixtures (integer — services expect int tenant ids) ───────────────
@pytest.fixture
def tenant_id() -> int:
    """Primary tenant ID for integration tests."""
    return random.randint(10_000_000, 99_999_999)


@pytest.fixture
def tenant_id_2() -> int:
    """Secondary tenant ID for cross-tenant isolation tests."""
    return random.randint(10_000_000, 99_999_999)


# ── Event loop policy ──────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()
