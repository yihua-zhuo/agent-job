"""Shared test fixtures.

Domain SQL handlers are split into separate functions so tests can compose
only the handlers they need via ``make_mock_session([handler1, handler2, ...])``.
"""

from __future__ import annotations

import importlib
import json as _json
import pkgutil
import sys
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from dotenv import load_dotenv
from sqlalchemy.exc import MultipleResultsFound

# Load .env so DATABASE_URL is available in test environment.
_dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_dotenv_path)

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
# ---------------------------------------------------------------------------


class MockRow:
    """Simulates a SQLAlchemy Row returned by result.fetchone() / scalars()."""

    def __init__(self, mapping):
        self._mapping = mapping
        self._is_sequence = isinstance(mapping, (list, tuple))
        if not self._is_sequence:
            if "tags" in self._mapping and isinstance(self._mapping["tags"], str):
                try:
                    self._mapping["tags"] = _json.loads(self._mapping["tags"])
                except Exception:  # noqa: S110 - invalid JSON should leave the original value intact.
                    pass

    def __getitem__(self, key):
        if isinstance(key, int):
            if self._is_sequence:
                return self._mapping[key]
            vals = list(self._mapping.values())
            return vals[key]
        return self._mapping[key]

    def __contains__(self, key):
        return key in self._mapping

    def keys(self):
        if self._is_sequence:
            return range(len(self._mapping))
        return self._mapping.keys()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._mapping:
            return self._mapping[name]
        raise AttributeError(name)

    def get(self, key, default=None):
        if self._is_sequence:
            raise NotImplementedError("get() not supported for list-based MockRow")
        return self._mapping.get(key, default)

    def __repr__(self):
        return f"MockRow({self._mapping!r})"


class MockResult:
    """Simulates a SQLAlchemy Result object returned by session.execute()."""

    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self._rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

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

    def scalars(self):
        return MagicMock(
            first=MagicMock(return_value=self._rows[0] if self._rows else None),
            all=MagicMock(return_value=self._rows),
        )

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        first = self._rows[0] if self._rows else None
        if isinstance(first, (list, tuple)):
            return first[0]
        return first

    def scalar(self):
        if not self._rows:
            return None
        first = self._rows[0]
        if isinstance(first, (list, tuple)):
            return first[0]
        return first

    def __iter__(self):
        return iter(self._rows)

    @property
    def rowcount(self) -> int:
        return self._rowcount


# ---------------------------------------------------------------------------
# Shared mutable state for stateful handlers (per-test lifecycle)
# ---------------------------------------------------------------------------


class MockState:
    """Per-test mutable state consumed by customer & user handlers."""

    def __init__(self):
        self.customers: dict[int, dict] = {}
        self.customers_next_id: int = 1
        self.users: dict[int, dict] = {}
        self.users_next_id: int = 1
        self.deleted_user_ids: set[int] = set()
        self.activities: dict[int, dict] = {}
        self.activities_next_id: int = 1


def _load_domain_handler_modules():
    """Import domain-owned handler modules and re-export their named helpers.

    Crashes at collection time with a descriptive message if any module fails
    to import, rather than letting an opaque ImportError propagate.
    """
    package_name = "tests.unit.domain_handlers"
    try:
        package = importlib.import_module(package_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Failed to import test package '{package_name}': {exc}. "
            "Ensure the package exists and all dependencies are installed."
        ) from exc
    discovered = []
    for info in sorted(pkgutil.iter_modules(package.__path__, prefix=f"{package_name}."), key=lambda item: item.name):
        try:
            module = importlib.import_module(info.name)
        except ImportError as exc:
            raise RuntimeError(
                f"Failed to import domain handler module '{info.name}': {exc}. "
                "Check for missing dependencies or syntax errors in the module."
            ) from exc
        discovered.append(module)
    modules = []
    for module in sorted(discovered, key=lambda item: (getattr(item, "ORDER", 100), item.__name__)):
        modules.append(module)
        for name in getattr(module, "__all__", []):
            if name != "get_handlers":
                globals()[name] = getattr(module, name)
    return modules


_DOMAIN_HANDLER_MODULES = _load_domain_handler_modules()


def _domain_handlers(state: MockState):
    handlers = []
    for module in _DOMAIN_HANDLER_MODULES:
        get_handlers = getattr(module, "get_handlers", None)
        if get_handlers is not None:
            handlers.extend(get_handlers(state))
    return handlers


def all_handlers(state: MockState):
    """Return the full list of domain handlers (default for backward compat)."""
    return _domain_handlers(state)


def make_mock_session(handlers=None, state=None):
    """Create a mock AsyncSession wired to the given SQL handlers.

    If *handlers* is ``None``, all domain handlers with fresh state are used.
    Tests that want a subset can pass their own list::

        state = MockState()
        session = make_mock_session([
            make_customer_handler(state),
            make_count_handler(state),
        ], state=state)

    If *state* is provided it is used to build handlers; otherwise a fresh
    MockState() is created internally. Sharing the same *state* object across
    the fixture and the handler lets tests seed records directly into state.
    """
    if state is None:
        state = MockState()
    if handlers is None:
        handlers = all_handlers(state)

    session = MagicMock(
        spec=[
            "execute",
            "add",
            "delete",
            "commit",
            "rollback",
            "close",
            "flush",
            "refresh",
            "scalars",
            "scalar_one_or_none",
            "scalar_one",
            "get",
            "result",
            "__aenter__",
            "__aexit__",
        ]
    )

    def _execute_side_effect(sql, params=None):
        sql_text = str(sql).lower().strip()
        bound_params = {}
        try:
            bound_params.update(getattr(sql.compile(), "params", {}) or {})
        except Exception as exc:  # noqa: BLE001 - some SQLAlchemy test doubles are not compilable.
            bound_params["_compile_error"] = exc
            pass
        bound_params.update(params or {})
        for h in handlers:
            result = h(sql_text, bound_params)
            if result is not None:
                return result
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

    @asynccontextmanager
    async def _mock_aenter():
        yield session

    session.__aenter__ = AsyncMock(side_effect=_mock_aenter)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


# ---------------------------------------------------------------------------
# SLA mock session (scalar-based, for SLAService tests)
# ---------------------------------------------------------------------------


class SlaMockSession:
    """Minimal mock AsyncSession that routes session.scalar() and session.execute() to SQL handlers.

    SLAService.get_sla_summary calls session.scalar(select(func.count(...))) directly.
    SlaMockSession also implements execute() so any future call to session.execute()
    is routed to the same handlers instead of silently passing a bare MagicMock.
    """

    def __init__(self, handlers):
        self._handlers = handlers

    async def scalar(self, sql, params=None):
        params = dict(params) if params else {}

        try:
            # Compile with a specific dialect to get the rendered SQL string
            compiled = sql.compile(dialect=self._get_dialect())
            # Normalize to lower-case so handlers can match patterns case-insensitively
            sql_text = str(compiled).lower()
            # compiled.params is a dict (attribute, not method in SQLAlchemy 2.x)
            for k, v in compiled.params.items():
                if k not in params:
                    params[k] = v
        except Exception as exc:
            # Surface compilation errors rather than silently falling through,
            # so broken SQL is detected immediately instead of being masked by
            # raw-string fallback matching.
            import warnings

            warnings.warn(f"SlaMockSession: SQL compilation failed ({exc}), falling back to raw string", UserWarning)
            sql_text = str(sql).lower().strip()

        for h in self._handlers:
            result = h(sql_text, params)
            if result is not None:
                return result
        return None

    async def execute(self, sql, params=None):
        """Route session.execute() to the same handlers as scalar().

        Returns a MockResult wrapping whatever value the first matching handler returns.
        """
        params = dict(params) if params else {}

        try:
            compiled = sql.compile(dialect=self._get_dialect())
            sql_text = str(compiled).lower()
            for k, v in compiled.params.items():
                if k not in params:
                    params[k] = v
        except Exception as exc:
            import warnings

            warnings.warn(
                f"SlaMockSession.execute: SQL compilation failed ({exc}), falling back to raw string", UserWarning
            )
            sql_text = str(sql).lower().strip()

        for h in self._handlers:
            result = h(sql_text, params)
            if result is not None:
                return MockResult([result])
        return MockResult([[None]])

    @staticmethod
    def _get_dialect():
        """Lazily create a PostgreSQL dialect instance for compilation."""
        if not hasattr(SlaMockSession, "_dialect"):
            from sqlalchemy.dialects.postgresql import dialect as pg_dialect

            SlaMockSession._dialect = pg_dialect()
        return SlaMockSession._dialect

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def sla_mock_session(handlers=None):
    """Create a mock AsyncSession wired to the given SQL handlers for SLA tests.

    Shorthand for ``SlaMockSession(handlers)``.
    """
    return SlaMockSession(handlers or [])


# ---------------------------------------------------------------------------
# SLA summary SQL handler
# ---------------------------------------------------------------------------


def make_sla_summary_handler(
    breached: int,
    at_risk: int,
    total: int,
    *,
    validate_tenant_id: bool = True,
    expected_tenant_id: int | None = None,
):
    """Return a handler that responds to select count(...) from tickets queries.

    Detects which bucket a query targets by inspecting the SQL clause structure:

      - total    : no "response_deadline" column at all
      - at_risk  : "response_deadline" column AND ">=" (the now-to-threshold window)
      - breached : "response_deadline" column present but no ">=" (past-deadline only)

    When ``validate_tenant_id`` is True the handler asserts ``params["tenant_id"]``
    equals ``expected_tenant_id`` (if given), raising ``AssertionError`` if the
    bind is absent or mismatched — ensuring the service actually forwards the
    tenant scope rather than hardcoding it as a literal.

    Uses column-name + operator detection rather than raw ">" / "<" substring
    scanning.
    """

    def handler(sql_text: str, params: dict):
        if not ("select" in sql_text and "count" in sql_text and "from tickets" in sql_text):
            return None

        # Tenant-scope assertion: catch silent tenant_id omissions.
        # SQLAlchemy may label the bind as "tenant_id_1" when multiple tenant_id
        # columns are present, so we check that at least one param key contains
        # "tenant_id" as a prefix.
        if validate_tenant_id:
            tenant_keys = [k for k in params if k.lower().startswith("tenant_id")]
            assert tenant_keys, f"Query is missing tenant_id bind param. sql={sql_text[:100]!r}, params={params!r}"
            if expected_tenant_id is not None:
                # Use whichever tenant_id key SQLAlchemy generated (could be
                # tenant_id, tenant_id_1, tenant_id_2, … when multiple tenant_id
                # conditions appear in the same query).
                actual = next(
                    (params[k] for k in sorted(tenant_keys) if params.get(k) is not None),
                    None,
                )
                assert actual == expected_tenant_id, f"Expected tenant_id={expected_tenant_id}, got {actual}"

        # Total: no response_deadline column at all
        if "response_deadline" not in sql_text:
            return total

        # at_risk: response_deadline column with ">=" (now <= deadline <= at_risk_threshold)
        if ">=" in sql_text:
            return at_risk

        # breached: response_deadline column present but no ">=" (past deadline only)
        return breached

    return handler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
