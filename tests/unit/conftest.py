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

# noqa: F401 — imported by name for static analysis; also set via globals() from domain handler modules
# NOTE: opportunity_handler / make_count_handler are populated into conftest globals
# via _load_domain_handler_modules() below, so direct import would circular-import.
# Ruff is silenced with F821 here so the reference in make_analytics_handlers passes.
opportunity_handler = globals().get("opportunity_handler")  # noqa: F821
make_count_handler = globals().get("make_count_handler")  # noqa: F821

# Re-export SLA domain handlers for backward compat — primary location is tests/unit/domain_handlers/sla.py
from tests.unit.domain_handlers.sla import (  # noqa: F401, E402
    SlaMockSession,
    make_sla_summary_handler,
    sla_mock_session,
)

# ---------------------------------------------------------------------------
# Mock SQLAlchemy Result object (returned by session.execute).
# ---------------------------------------------------------------------------


class MockRow:
    """Simulates a SQLAlchemy Row returned by result.fetchone() / scalars()."""

    def __init__(self, mapping):
        self._mapping = mapping
        self._is_sequence = isinstance(mapping, (list, tuple))
        if not self._is_sequence:
            for _key in ("tags", "widgets"):
                if _key in self._mapping and isinstance(self._mapping[_key], str):
                    try:
                        self._mapping[_key] = _json.loads(self._mapping[_key])
                    except (ValueError, TypeError):
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
        class _Scalars:
            def __init__(self, rows):
                self._rows = rows

            def first(self):
                return self._rows[0] if self._rows else None

            def all(self):
                return self._rows

            def one_or_none(self):
                if not self._rows:
                    return None
                if len(self._rows) == 1:
                    return self._rows[0]
                raise MultipleResultsFound("one_or_none() expected 0 or 1 rows, got multiple")

        return _Scalars(self._rows)

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


# ---------------------------------------------------------------------------
# Dashboard / Report handlers (used by make_analytics_handlers)
# ---------------------------------------------------------------------------


def dashboard_handler(sql_text, params):
    """Handle dashboard-related SQL (stateless)."""

    if "insert into dashboards" in sql_text:
        return MockResult([MockRow({
            "id": 1,
            "tenant_id": params.get("tenant_id", 0),
            "name": params.get("name", "Dashboard"),
            "description": params.get("description"),
            "widgets": [],
            "owner_id": params.get("owner_id", 0),
            "is_default": False,
            "created_at": params.get("created_at"),
            "updated_at": params.get("updated_at"),
        })])

    if "from dashboards where id" in sql_text:
        dashboard_id = params.get("id")
        fixtures = {
            1: {
                "id": 1, "tenant_id": 1,
                "name": "Dashboard 1", "description": "Test dashboard",
                "widgets": [], "owner_id": 1,
                "is_default": False,
                "created_at": None, "updated_at": None,
            },
        }
        if dashboard_id in fixtures:
            return MockResult([MockRow(fixtures[dashboard_id].copy())])
        return MockResult([])

    if "from dashboards" in sql_text:
        return MockResult([
            MockRow({
                "id": 1, "tenant_id": 1,
                "name": "Dashboard 1", "description": "First",
                "widgets": [], "owner_id": 1,
                "is_default": False,
                "created_at": None, "updated_at": None,
            }),
            MockRow({
                "id": 2, "tenant_id": 1,
                "name": "Dashboard 2", "description": "Second",
                "widgets": [], "owner_id": 1,
                "is_default": False,
                "created_at": None, "updated_at": None,
            }),
            MockRow({
                "id": 3, "tenant_id": 1,
                "name": "Dashboard 3", "description": "Third",
                "widgets": [], "owner_id": 1,
                "is_default": False,
                "created_at": None, "updated_at": None,
            }),
        ])

    return None


def report_handler(sql_text, params):
    """Handle report-related SQL (stateless)."""

    if "insert into reports" in sql_text:
        return MockResult([MockRow({
            "id": 1,
            "tenant_id": params.get("tenant_id", 0),
            "name": params.get("name", "Report"),
            "type": params.get("type", "sales_revenue"),
            "config": {},
            "date_range": {},
            "created_by": params.get("created_by", 0),
            "last_run_at": None,
            "created_at": params.get("created_at"),
        })])

    if "from reports where id" in sql_text:
        report_id = params.get("id")
        fixtures = {
            1: {
                "id": 1, "tenant_id": 1,
                "name": "Sales Revenue Report",
                "type": "sales_revenue",
                "config": "{}", "date_range": "{}",
                "created_by": 1,
                "last_run_at": None,
                "created_at": None,
            },
        }
        if report_id in fixtures:
            return MockResult([MockRow(fixtures[report_id].copy())])
        return MockResult([])

    if "from reports" in sql_text:
        return MockResult([MockRow({
            "id": 1, "tenant_id": 1,
            "name": "Sales Revenue Report",
            "type": "sales_revenue",
            "config": "{}", "date_range": "{}",
            "created_by": 1,
            "last_run_at": None,
            "created_at": None,
        })])

    return None


def make_analytics_handlers(state: MockState):
    """Return handlers needed by AnalyticsService unit tests."""
    return [
        dashboard_handler,
        report_handler,
        opportunity_handler,
        make_count_handler(state),
    ]


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
