"""Pytest configuration for web-layer (FastAPI router) integration tests.

Uses httpx.AsyncClient with ASGITransport to make real HTTP requests
through the FastAPI app — full stack including middleware, routing,
validation, and response serialization.

Requires TEST_DATABASE_URL (same as other integration tests).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env so DATABASE_URL is available at module load time.
_dotenv_path = Path(__file__).resolve().parents[2] / ".env"
from dotenv import load_dotenv

load_dotenv(_dotenv_path)

_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Import the app factory and fixtures from the main integration conftest
# so we share the same test database and schema setup.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integration.conftest import (
    _get_test_async_session_factory,
    db_schema,
    fresh_schema,
)

# ── Web test client factory ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def fresh_schema_web():
    """Re-use fresh_schema from main integration conftest."""
    yield from fresh_schema()


@pytest.fixture(scope="function")
def db_schema_web(fresh_schema_web):
    """Truncate tables — shared with service-level integration tests."""
    yield from db_schema(None)


@pytest_asyncio.fixture(scope="function")
async def async_session_web(db_schema_web) -> AsyncGenerator[AsyncSession, None]:
    """Async session for web tests — shares DB schema with service tests."""
    factory = _get_test_async_session_factory()
    async with factory() as session:
        yield session


@pytest.fixture
def tenant_id_web() -> int:
    """Primary tenant ID for web integration tests."""
    from tests.integration.conftest import tenant_id_web as main_tenant_id_web
    return main_tenant_id_web


@pytest.fixture
def tenant_id_2_web() -> int:
    """Secondary tenant ID for cross-tenant isolation tests."""
    from tests.integration.conftest import tenant_id_2_web as main_tenant_id_2_web
    return main_tenant_id_2_web


# ── Auth fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def auth_headers_web(async_session_web, tenant_id_web) -> dict[str, str]:
    """Return a valid JWT Authorization header for the test tenant."""
    from services.auth_service import AuthService

    # Set env vars directly (do NOT use setdefault — conftest.py already loaded .env
    # which cached the real secret before this fixture runs; we must override it).
    test_secret = "integration-test-jwt-secret-key-32"
    os.environ["JWT_SECRET"] = test_secret
    os.environ["JWT_SECRET_KEY"] = test_secret

    auth_svc = AuthService(async_session_web, secret_key=test_secret)
    token = auth_svc.generate_token(
        user_id=999,
        username="webtest",
        role="admin",
        tenant_id=tenant_id_web,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def auth_headers_tenant_2(async_session_web, tenant_id_2_web) -> dict[str, str]:
    """Return a valid JWT Authorization header for tenant 2."""
    # Set env vars directly — see note in auth_headers_web.
    test_secret = "integration-test-jwt-secret-key-32"
    os.environ["JWT_SECRET"] = test_secret
    os.environ["JWT_SECRET_KEY"] = test_secret
    from services.auth_service import AuthService

    auth_svc = AuthService(async_session_web, secret_key=test_secret)
    token = auth_svc.generate_token(
        user_id=999,
        username="webtest2",
        role="admin",
        tenant_id=tenant_id_2_web,
    )
    return {"Authorization": f"Bearer {token}"}


# ── FastAPI app fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def fastapi_app():
    """Import and return the FastAPI app from main.py."""
    from main import app
    return app


@pytest_asyncio.fixture(scope="function")
async def client(fastapi_app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client that hits the FastAPI app directly via ASGI."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Combined web test client with auth ──────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def api_client(
    client: AsyncClient,
    auth_headers_web: dict[str, str],
) -> AsyncClient:
    """HTTP client pre-populated with valid auth headers."""
    client.headers.update(auth_headers_web)
    return client


@pytest_asyncio.fixture(scope="function")
async def api_client_tenant_2(
    client: AsyncClient,
    auth_headers_tenant_2: dict[str, str],
) -> AsyncClient:
    """HTTP client authenticated as tenant 2."""
    client.headers.update(auth_headers_tenant_2)
    return client
