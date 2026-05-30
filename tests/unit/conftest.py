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
from sqlalchemy import insert, table
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
            for json_key in ("tags", "conditions", "actions"):
                if json_key in self._mapping and isinstance(self._mapping[json_key], str):
                    try:
                        self._mapping[json_key] = _json.loads(self._mapping[json_key])
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
        bound_params.update(params or {})
        for h in handlers:
            # Pass lowercased tablename so "INSERT INTO Agent_Tasks" matches
            # "insert into agent_tasks" in handlers.
            result = h(sql_text, bound_params)
            if result is not None:
                return result
        return MockResult([])

    session.execute = AsyncMock(side_effect=_execute_side_effect)
    session.delete = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.scalars = MagicMock()
    session.scalar_one_or_none = MagicMock()
    session.scalar_one = MagicMock()
    session.result = MagicMock()

    # Capture ORM objects added via session.add() so flush() can persist them.
    _pending: list = []

    def _mock_add(obj):
        _pending.append(obj)

    session.add = MagicMock(side_effect=_mock_add)

    async def _mock_flush():
        # Persist each pending ORM object by calling the appropriate INSERT handler.
        for obj in _pending:
            tablename = getattr(obj, "__tablename__", None)
            if tablename is None:
                continue
            # Guard: tablename must be a valid SQL identifier (alphanumeric + underscore).
            # This prevents arbitrary SQL injection through a malicious __tablename__.
            if not tablename.isidentifier():
                continue
            params = {}
            # Extract every public attribute from the ORM object so handlers
            # receive all column values regardless of which model is used.
            for key in list(obj.__dict__.keys()):
                if key.startswith("_") or key == "metadata":
                    continue
                val = getattr(obj, key, None)
                if val is not None:
                    params[key] = val
            # Build INSERT via SQLAlchemy Core to avoid raw string concat.
            # Lowercase the SQL text so handlers that match "insert into <table>"
            # (lowercased by _execute_side_effect) also work here.
            sql_text = str(insert(table(tablename))).lower()
            for h in handlers:
                result = h(sql_text, params)
                if result is not None:
                    row = result.fetchone()
                    if row is not None:
                        for k in row.keys():
                            setattr(obj, k, getattr(row, k))
                    break
        _pending.clear()

    async def _mock_refresh(obj):
        tablename = getattr(obj, "__tablename__", None)
        obj_id = getattr(obj, "id", None)
        if tablename is None or obj_id is None:
            return
        # Guard: tablename must be a valid SQL identifier.
        if not tablename.isidentifier():
            return
        tenant_id = getattr(obj, "tenant_id", None)
        params = {"id": obj_id}
        if tenant_id is not None:
            params["tenant_id"] = tenant_id
            sql_text = "select * from " + tablename + " where id = :id and tenant_id = :tenant_id"  # noqa: S608
        else:
            sql_text = "select * from " + tablename + " where id = :id"  # noqa: S608
        for h in handlers:
            result = h(sql_text, params)
            if result is not None:
                row = result.fetchone()
                if row is not None:
                    for key in row.keys():
                        setattr(obj, key, getattr(row, key))
                break

    session.flush = AsyncMock(side_effect=_mock_flush)
    session.refresh = AsyncMock(side_effect=_mock_refresh)
    session._state = state  # allow tests to seed state directly

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
