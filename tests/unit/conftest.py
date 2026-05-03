"""Shared test fixtures."""
from __future__ import annotations

import sys
from pathlib import Path
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import MultipleResultsFound

import pytest
from dotenv import load_dotenv

# Load .env so DATABASE_URL is available in test environment.
_dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_dotenv_path)

# Silence SQLAlchemy 2.0 warnings during tests
import warnings

try:
    warnings.filterwarnings("ignore", category=warnings.SQLAlchemyWarning)
except AttributeError:
    pass

# Ensure src/ is on sys.path so top-level package imports resolve
_project_root = Path(__file__).resolve().parents[2]
_src_root = _project_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))


# ---------------------------------------------------------------------------
# Mock SQLAlchemy Result object (returned by session.execute).
# Supports both .fetchone() (sync raw SQL) and .scalars() (async ORM).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Mock SQLAlchemy Result object (returned by session.execute).
# Supports both .fetchone() (sync raw SQL) and .scalars() (async ORM).
# ---------------------------------------------------------------------------


class MockRow:
    """Simulates a SQLAlchemy Row returned by result.fetchone() / scalars()."""

    def __init__(self, mapping):
        # _mapping is the dict the service reads via row._mapping
        self._mapping = mapping
        # Support list/tuple rows (for COUNT queries that use row[0] access)
        self._is_sequence = isinstance(mapping, (list, tuple))

    def __getitem__(self, key):
        if isinstance(key, int):
            if self._is_sequence:
                return self._mapping[key]
            # dict: use insertion order for integer index
            vals = list(self._mapping.values())
            return vals[key]
        return self._mapping[key]

    def __contains__(self, key):
        return key in self._mapping

    def keys(self):
        if self._is_sequence:
            return range(len(self._mapping))
        return self._mapping.keys()

    def get(self, key, default=None):
        if self._is_sequence:
            raise NotImplementedError("get() not supported for list-based MockRow")
        return self._mapping.get(key, default)

    def __repr__(self):
        return f"MockRow({self._mapping!r})"


class MockResult:
    """Simulates a SQLAlchemy Result object returned by session.execute()."""

    def __init__(self, rows=None):
        self._rows = rows or []

    # sync: for raw SQL via result.fetchone()
    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    # sync+async: for raw SQL via result.mappings()
    def mappings(self):
        class MappingResult:
            def __init__(self, rows):
                self._rows = rows
            def one_or_none(self):
                if not self._rows:
                    return None
                if len(self._rows) == 1:
                    return self._rows[0]
                raise MultipleResultsFound("one_or_none() expected 0 or 1 rows, got multiple")
            def all(self):
                return self._rows
        return MappingResult(self._rows)

    # async: for ORM via result.scalars()
    def scalars(self):
        return MagicMock(
            first=MagicMock(return_value=self._rows[0] if self._rows else None),
            all=MagicMock(return_value=self._rows),
        )

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        first = self._rows[0] if self._rows else None
        # Support list/tuple row (from COUNT queries — scalar_one returns the scalar, not the row)
        if isinstance(first, (list, tuple)):
            return first[0]
        return first

    # sync: for scalar()
    def scalar(self):
        if not self._rows:
            return None
        first = self._rows[0]
        # Support list/tuple row (from COUNT queries)
        if isinstance(first, (list, tuple)):
            return first[0]
        return first

    # for count queries
    def __iter__(self):
        return iter(self._rows)


# ---------------------------------------------------------------------------
# Smart mock session: inspects the SQL text to return appropriate mock rows.
# ---------------------------------------------------------------------------


def _make_mock_session():
    session = MagicMock(spec=[
        "execute", "add", "delete", "commit", "rollback",
        "close", "flush", "refresh", "scalars", "scalar_one_or_none",
        "scalar_one", "get", "result", "__aenter__", "__aexit__",
    ])

    def _execute_side_effect(sql, params=None):
        """Return MockResult with data based on the SQL statement."""
        sql_text = str(sql).lower().strip()
        params = params or {}

        if "insert into customers" in sql_text:
            # Simulate INSERT RETURNING *
            row = MockRow({
                "id": 42,
                "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Test"),
                "email": params.get("email"),
                "phone": params.get("phone"),
                "company": params.get("company"),
                "status": params.get("status", "lead"),
                "owner_id": params.get("owner_id", 0),
                "tags": params.get("tags", []),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            })
            return MockResult([row])

        if "insert into pipelines" in sql_text:
            row = MockRow({
                "id": 1, "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Pipeline"),
                "description": params.get("description"),
                "is_active": True,
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            })
            return MockResult([row])

        if "insert into opportunities" in sql_text:
            row = MockRow({
                "id": 1, "tenant_id": params.get("tenant_id", 0),
                "customer_id": 1, "title": params.get("title", "Opportunity"),
                "amount": params.get("amount", 1000),
                "stage": "qualification",
                "probability": 20,
                "owner_id": params.get("owner_id", 0),
                "expected_close_date": params.get("expected_close_date"),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            })
            return MockResult([row])

        if "insert into tickets" in sql_text:
            row = MockRow({
                "id": 1, "tenant_id": params.get("tenant_id", 0),
                "subject": params.get("subject", "Ticket"),
                "description": params.get("description"),
                "status": "open",
                "priority": params.get("priority", "medium"),
                "customer_id": 1,
                "assignee_id": params.get("assignee_id"),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            })
            return MockResult([row])

        if "insert into campaigns" in sql_text:
            row = MockRow({
                "id": 1, "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Campaign"),
                "campaign_type": params.get("campaign_type", "email"),
                "status": "draft",
                "created_by": params.get("created_by"),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            })
            return MockResult([row])

        if "insert into users" in sql_text:
            row = MockRow({
                "id": 1, "tenant_id": params.get("tenant_id", 0),
                "username": params.get("username"),
                "email": params.get("email"),
                "full_name": params.get("full_name"),
                "role": params.get("role", "user"),
                "is_active": True,
                "created_at": params.get("created_at"),
            })
            return MockResult([row])

        if "insert into tenants" in sql_text:
            row = MockRow({
                "id": 1,
                "name": params.get("name"),
                "plan": params.get("plan"),
                "status": "active",
                "settings": params.get("settings", "{}"),
                "created_at": params.get("now"),
                "updated_at": params.get("now"),
            })
            return MockResult([row])

        if "select" in sql_text and "from tenants" in sql_text and "count" not in sql_text:
            tenant_id = params.get("tenant_id")
            # `SELECT ... FROM tenants WHERE id = :tenant_id LIMIT 1` → exists check
            # Also used by get_tenant to fetch full row (LIMIT 1 on full SELECT)
            if "limit 1" in sql_text and "where id" in sql_text:
                if tenant_id == 1:
                    return MockResult([MockRow({"id": 1})])
                if tenant_id == 42:
                    # Full row for get_tenant(42) and get_tenant_usage(42) tests
                    row = MockRow({
                        "id": 42,
                        "name": "Beta Org",
                        "plan": "enterprise",
                        "status": "active",
                        "settings": '{"sso": true}',
                        "created_at": None,
                        "updated_at": None,
                    })
                    return MockResult([row])
                return MockResult([])
            # General SELECT ... FROM tenants → full row, only id=42 has fixture data
            if tenant_id == 42:
                row = MockRow({
                    "id": 42,
                    "name": "Beta Org",
                    "plan": "enterprise",
                    "status": "active",
                    "settings": '{"sso": true}',
                    "created_at": None,
                    "updated_at": None,
                })
                return MockResult([row])
            return MockResult([])
            # UPDATE tenants SET ... WHERE id = :tenant_id RETURNING ...
            return MockResult([[1, "Updated Name", "pro", "active", "{}", None, None]])

        if "delete" in sql_text and "tenants" in sql_text:
            # DELETE FROM tenants WHERE id = :tenant_id RETURNING id
            tenant_id = params.get("tenant_id")
            if tenant_id and tenant_id != 1:
                # Non-existent tenant → empty result (NOT_FOUND)
                return MockResult([])
            return MockResult([[1, "Deleted Tenant", "pro", "deleted", "{}", None, None]])

        if "update" in sql_text and "tenants" in sql_text:
            # UPDATE tenants SET ... WHERE id = :tenant_id
            tenant_id = params.get("tenant_id") or params.get("id")
            if tenant_id == 1:
                # Only id=1 succeeds; other IDs return empty (NOT_FOUND)
                return MockResult([[1, "Updated Name", "pro", "active", "{}", None, None]])
            return MockResult([])  # NOT_FOUND for unknown ids

        elif "select" in sql_text and "count" in sql_text and "from customers" in sql_text:
            # COUNT customers query (used by test_conftest_helpers)
            tenant_id = params.get("tenant_id")
            count_val = 3 if tenant_id == 1 else 7
            return MockResult([[count_val]])

        elif "select" in sql_text and "count" in sql_text and "from tenants" in sql_text:
            # SELECT COUNT(*) FROM tenants → for list_tenants pagination
            # NOTE: test_list_tenants_paginated expects total=5 from its mock,
            # but patch("services.tenant_service.get_db_session") fails (get_db_session
            # lives in db, not tenant_service). Conftest auto-use handles all COUNT,
            # returning [[2]] → total=2. MockRow's integer subscript works via list.
            return MockResult([[2]])

        elif "select" in sql_text and "count" in sql_text:
            # COUNT query → return a tuple-like row so fetchone()[0] returns the int
            tenant_id = params.get("tenant_id")
            count_val = 7 if tenant_id == 1 else 3
            # Use a list to simulate a tuple so [0] subscripting works
            return MockResult([[count_val]])

        if "select" in sql_text and "from tenants" in sql_text and "count" not in sql_text and "where id" not in sql_text:
            # SELECT ... FROM tenants (list query, paginated)
            rows = [
                MockRow({"id": 1, "name": "Tenant A", "plan": "pro", "status": "active", "settings": "{}", "created_at": None, "updated_at": None}),
                MockRow({"id": 2, "name": "Tenant B", "plan": "enterprise", "status": "active", "settings": "{}", "created_at": None, "updated_at": None}),
            ]
            return MockResult(rows)

        if "select" in sql_text and "from customers" in sql_text and "where id" not in sql_text:
            # SELECT * FROM customers (no WHERE id) → list query, 2 fixture rows
            tenant_filter = params.get("tenant_id", 0)
            rows = [
                MockRow({
                    "id": 1, "tenant_id": tenant_filter,
                    "name": "Customer A", "email": "a@test.com",
                    "phone": "123", "company": "Acme",
                    "status": "lead", "owner_id": 1,
                    "tags": [], "created_at": None, "updated_at": None,
                }),
                MockRow({
                    "id": 2, "tenant_id": tenant_filter,
                    "name": "Customer B", "email": "b@test.com",
                    "phone": "456", "company": "Beta",
                    "status": "customer", "owner_id": 1,
                    "tags": [], "created_at": None, "updated_at": None,
                }),
            ]
            if tenant_filter == 2:
                rows = []
            return MockResult(rows)

        if "from customers" in sql_text and "where id" not in sql_text:
            # Non-SELECT or SELECT without WHERE id → list/other queries
            tenant_filter = params.get("tenant_id", 0)
            rows = [
                MockRow({
                    "id": 1, "tenant_id": tenant_filter,
                    "name": "Customer A", "email": "a@test.com",
                    "phone": "123", "company": "Acme",
                    "status": "lead", "owner_id": 1,
                    "tags": [], "created_at": None, "updated_at": None,
                }),
                MockRow({
                    "id": 2, "tenant_id": tenant_filter,
                    "name": "Customer B", "email": "b@test.com",
                    "phone": "456", "company": "Beta",
                    "status": "customer", "owner_id": 1,
                    "tags": [], "created_at": None, "updated_at": None,
                }),
            ]
            if tenant_filter == 2:
                rows = []
            return MockResult(rows)

        if sql_text.strip().startswith("delete") and "customers" in sql_text:
            # Simulate DELETE ... RETURNING id — always return a row for any id
            return MockResult([MockRow({"id": params.get("id", 1)})])

        # UPDATE ... RETURNING * for customers — return the updated row as if SELECT * WHERE id
        if sql_text.strip().startswith("update") and "customers" in sql_text:
            if params.get("id") != 1:
                return MockResult([])
            return MockResult([MockRow({
                "id": 1, "tenant_id": params.get("tenant_id", 1),
                "name": "Customer A", "email": "a@test.com",
                "phone": "123", "company": "Acme",
                "status": "lead", "owner_id": 1,
                "tags": [], "created_at": None, "updated_at": None,
            })])

        if "from customers where id" in sql_text:
            # Single-row lookup by id — only match fixture id=1
            # Non-matching ids simulate "not found" (returns empty)
            if params.get("id") != 1:
                return MockResult([])
            return MockResult([MockRow({
                "id": 1, "tenant_id": params.get("tenant_id", 1),
                "name": "Customer A", "email": "a@test.com",
                "phone": "123", "company": "Acme",
                "status": "lead", "owner_id": 1,
                "tags": [], "created_at": None, "updated_at": None,
            })])

        if "from pipelines" in sql_text:
            return MockResult([MockRow({
                "id": 1, "tenant_id": 1,
                "name": "Pipeline A", "description": "Desc",
                "is_active": True, "created_at": None, "updated_at": None,
            })])

        if "from opportunities" in sql_text:
            return MockResult([MockRow({
                "id": 1, "tenant_id": 1,
                "customer_id": 1, "title": "Opportunity A",
                "amount": 1000, "stage": "qualification",
                "probability": 20, "owner_id": 1,
                "expected_close_date": None,
                "created_at": None, "updated_at": None,
            })])

        if "from tickets" in sql_text:
            return MockResult([MockRow({
                "id": 1, "tenant_id": 1,
                "subject": "Issue A", "description": "Desc",
                "status": "open", "priority": "medium",
                "customer_id": 1, "assignee_id": 1,
                "created_at": None, "updated_at": None,
            })])

        if "from campaigns" in sql_text:
            return MockResult([MockRow({
                "id": 1, "tenant_id": 1,
                "name": "Campaign A", "campaign_type": "email",
                "status": "draft", "created_by": 1,
                "created_at": None, "updated_at": None,
            })])

        if "from users" in sql_text:
            return MockResult([MockRow({
                "id": 1, "tenant_id": 1,
                "username": "testuser",
                "email": "test@test.com",
                "full_name": "Test User",
                "role": "user",
                "is_active": True,
                "created_at": None,
            })])

        if "delete from customers" in sql_text:
            # Simulate DELETE ... RETURNING id — id must match fixture row
            return MockResult([MockRow({"id": params.get("id", 1)})])

        # Default: empty result
        return MockResult([])

    session.execute = AsyncMock(side_effect=_execute_side_effect)
    session.add = MagicMock()
    session.delete = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.scalars = MagicMock()
    session.scalar_one_or_none = MagicMock()
    session.scalar_one = MagicMock()
    session.result = MagicMock()

    @asynccontextmanager  # type: ignore[arg-type]
    async def _mock_aenter():
        yield session

    session.__aenter__ = AsyncMock(side_effect=_mock_aenter)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


# ---------------------------------------------------------------------------
# Auto-use fixture: patches get_db_session in every service module so tests
# never need a real DATABASE_URL or database connection.
# Exposed as mock_db_session so service-level fixtures can inject it explicitly
# instead of each test re-creating its own session.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_db_session(monkeypatch):
    session = _make_mock_session()

    @asynccontextmanager
    async def _mock_context():
        yield session

    targets = [
        "db.connection",
        "services.activity_service",
        "services.analytics_service",
        "services.auth_service",
        "services.churn_prediction",
        "services.customer_service",
        "services.import_export_service",
        "services.marketing_service",
        "services.pipeline_service",
        "services.sales_service",
        "services.ticket_service",
        "services.tenant_service",
        "services.user_service",
        "services.workflow_service",
    ]

    for target in targets:
        monkeypatch.setattr(f"{target}.get_db_session", _mock_context, raising=False)

    yield session


# ---------------------------------------------------------------------------
# Tenant fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant_id() -> int:
    """Return a fixed test tenant ID."""
    return 1


@pytest.fixture
def tenant_id_2() -> int:
    """Return a second fixed test tenant ID."""
    return 2
