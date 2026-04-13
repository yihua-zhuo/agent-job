"""Pytest configuration for integration tests.

Uses a dedicated PostgreSQL database on Supabase for integration tests.
Each test function gets a clean schema via TRUNCATE CASCADE.

The key trick: we monkey-patch src.db.connection.get_db_session so all
services (which use it internally) automatically get a session bound to
the test database.
"""
from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

# ── Test database URL ────────────────────────────────────────────────────────────
TEST_DATABASE_URL: str = (
    "postgresql+asyncpg://postgres.unkojburovuewvojcepd:"
    "+t%26d%2BSCF4f69k.y@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
)
TEST_SYNC_DATABASE_URL: str = (
    "postgresql://postgres.unkojburovuewvojcepd:"
    "+t%26d%2BSCF4f69k.y@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
)

# ── Singleton test engine / factory ──────────────────────────────────────────────
_test_async_engine = None
_test_async_session_factory = None
_test_sync_engine = None


def _get_test_async_engine():
    global _test_async_engine
    if _test_async_engine is None:
        _test_async_engine = create_async_engine(
            TEST_DATABASE_URL,
            poolclass=NullPool,
            echo=False,
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
            TEST_SYNC_DATABASE_URL,
            pool_pre_ping=True,
            pool_size=3,
        )
    return _test_sync_engine


# ── Patch src.db.connection so get_db_session() serves test sessions ─────────────
def _install_test_db_connection():
    """Replace get_db_session in src.db.connection with a test-aware version."""
    import src.db.connection as conn_mod

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

    conn_mod._async_engine = _get_test_async_engine()
    conn_mod._async_session_factory = _get_test_async_session_factory()
    conn_mod.get_db_session = _test_get_db_session


# ── Schema management SQL ──────────────────────────────────────────────────────
SCHEMA_SQL = """
DROP TABLE IF EXISTS pipeline_stages      CASCADE;
DROP TABLE IF EXISTS pipelines           CASCADE;
DROP TABLE IF EXISTS activities          CASCADE;
DROP TABLE IF EXISTS workflows           CASCADE;
DROP TABLE IF EXISTS campaign_events     CASCADE;
DROP TABLE IF EXISTS campaigns           CASCADE;
DROP TABLE IF EXISTS dashboards         CASCADE;
DROP TABLE IF EXISTS reports            CASCADE;
DROP TABLE IF EXISTS tickets            CASCADE;
DROP TABLE IF EXISTS ticket_replies     CASCADE;
DROP TABLE IF EXISTS users              CASCADE;
DROP TABLE IF EXISTS opportunities      CASCADE;
DROP TABLE IF EXISTS contacts           CASCADE;
DROP TABLE IF EXISTS customers          CASCADE;
DROP TABLE IF EXISTS tenants            CASCADE;
DROP TABLE IF EXISTS notifications     CASCADE;
DROP TABLE IF EXISTS reminders          CASCADE;
DROP TABLE IF EXISTS tasks              CASCADE;
"""


# ── Fixture: set up schema once per session ─────────────────────────────────────
@pytest.fixture(scope="session")
def fresh_schema() -> Generator[None, None, None]:
    """Create/recreate the full test schema once per test session.

    - Patches src.db.connection.get_db_session to serve test DB sessions.
    - Patches src.internal.db.engine so sync fixtures also hit the test DB.
    - Creates all tables via SQLAlchemy ORM metadata.
    """
    # 1. Install the patched async connection FIRST (before any service is loaded)
    _install_test_db_connection()

    # 2. Replace src.db.base.Base with a fresh one so all models register here.
    #    The ORM models import Base once from src.db.base; patching it before
    #    the models are loaded makes Base.metadata contain all tables.
    import src.db.base as db_base_module

    from sqlalchemy.orm import declarative_base

    original_base = getattr(db_base_module, "Base", None)
    db_base_module.Base = declarative_base()

    # 3. Import models so they register their tables with the new Base
    import src.db.models  # noqa: F401
    import src.models  # noqa: F401

    # 4. Patch src.internal.db.engine for sync fixtures / direct ORM access
    import src.internal.db.engine as db_module

    original_engine = getattr(db_module, "_engine", None)
    original_session = getattr(db_module, "SessionLocal", None)

    sync_engine = _get_test_sync_engine()
    db_module._engine = sync_engine

    # 5. Drop + recreate tables via the test sync engine
    with sync_engine.begin() as conn:
        for stmt in SCHEMA_SQL.strip().split(";"):
            s = stmt.strip()
            if s:
                try:
                    conn.execute(text(s))
                except Exception:
                    pass  # ignore drop errors

    db_base_module.Base.metadata.create_all(bind=sync_engine)

    yield

    # ── Cleanup ────────────────────────────────────────────────────────────────
    db_base_module.Base = original_base  # restore original Base
    db_module._engine = original_engine
    db_module.SessionLocal = original_session

    if _test_sync_engine is not None:
        _test_sync_engine.dispose()


# ── Fixture: truncate tables between each test ──────────────────────────────────
@pytest.fixture(scope="function")
def db_schema(fresh_schema) -> Generator[None, None, None]:
    """Truncate all tables between each test for function-level isolation."""
    sync_engine = _get_test_sync_engine()
    with sync_engine.begin() as conn:
        for table in [
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
        ]:
            try:
                conn.execute(
                    text(f"TRUNCATE {table} CASCADE RESTART IDENTITY RESTRICT")
                )
            except Exception:
                pass
    yield


# ── Fixture: async session (for direct DB access in tests) ────────────────────
@pytest_asyncio.fixture(scope="function")
async def async_session(db_schema) -> AsyncGenerator[AsyncSession, None]:
    """Provide a dedicated async session for each test.

    Note: services typically call get_db_session() internally rather than
    accepting a session as a parameter.  This fixture is available for
    direct ORM queries when you need explicit control.
    """
    factory = _get_test_async_session_factory()
    async with factory() as session:
        yield session


# ── Fixture: sync session (for direct ORM access in tests) ───────────────────
@pytest.fixture(scope="function")
def sync_session(db_schema) -> Generator[Session, None, None]:
    """Provide a dedicated sync session for each test."""
    SessionLocal = sessionmaker(
        bind=_get_test_sync_engine(), autoflush=False, autocommit=False
    )
    with SessionLocal() as session:
        yield session


# ── Fixtures: tenant IDs ───────────────────────────────────────────────────────
@pytest.fixture
def tenant_id() -> str:
    """Primary tenant ID for integration tests (UUID string)."""
    return str(uuid.uuid4())


@pytest.fixture
def tenant_id_2() -> str:
    """Secondary tenant ID for cross-tenant isolation tests (UUID string)."""
    return str(uuid.uuid4())


# ── Event loop policy ──────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()
