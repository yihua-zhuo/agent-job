"""Shared test fixtures.

Domain SQL handlers are split into separate functions so tests can compose
only the handlers they need via ``make_mock_session([handler1, handler2, ...])``.
"""
from __future__ import annotations

import json as _json
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest
from dotenv import load_dotenv
from sqlalchemy.exc import MultipleResultsFound

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
                except Exception:
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

    @property
    def _fields(self):
        if self._is_sequence:
            return range(len(self._mapping))
        return self._mapping.keys()

    def __getattr__(self, name):
        if name.startswith('_'):
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
        self.automation_rules: dict[int, dict] = {}
        self.automation_rules_next_id: int = 1000


# ---------------------------------------------------------------------------
# Domain SQL handlers
#
# Signature: handler(sql_text: str, params: dict) -> MockResult | None
# Return MockResult to handle the query, or None to pass to the next handler.
#
# Stateful handlers are factories: make_xxx_handler(state) -> handler
# Stateless handlers are plain functions: xxx_handler(sql_text, params)
# ---------------------------------------------------------------------------


def make_customer_handler(state: MockState):
    """Handle all customer-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""

    def handler(sql_text, params):
        # INSERT
        if "insert into customers" in sql_text:
            cid = state.customers_next_id
            state.customers_next_id += 1
            tags_raw = params.get("tags", [])
            tags_val = _json.dumps(tags_raw) if not isinstance(tags_raw, str) else tags_raw
            record = {
                "id": cid,
                "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Test"),
                "email": params.get("email"),
                "phone": params.get("phone"),
                "company": params.get("company"),
                "status": params.get("status", "lead"),
                "owner_id": params.get("owner_id", 0),
                "tags": tags_val,
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.customers[cid] = record
            return MockResult([MockRow(record.copy())])

        # UPDATE
        if sql_text.startswith("update") and "customers" in sql_text:
            customer_id = params.get("id")
            if customer_id in state.customers:
                rec = state.customers[customer_id]
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        rec[k] = v
                return MockResult([MockRow(rec.copy())])
            if customer_id and customer_id >= 1:
                return MockResult([MockRow({
                    "id": customer_id, "tenant_id": params.get("tenant_id", 1),
                    "name": params.get("name", "Customer A"),
                    "email": params.get("email", "a@test.com"),
                    "phone": params.get("phone", "123"),
                    "company": params.get("company", "Acme"),
                    "status": params.get("status", "lead"),
                    "owner_id": params.get("owner_id", 1),
                    "tags": _json.dumps(params.get("tags", [])),
                    "created_at": None, "updated_at": None,
                })])
            return MockResult([])

        # DELETE
        if sql_text.startswith("delete") and "customers" in sql_text:
            return MockResult([MockRow({"id": params.get("id", 1)})])

        # COUNT
        if "select" in sql_text and "count" in sql_text and "from customers" in sql_text:
            tenant_id = params.get("tenant_id")
            count_val = 3 if tenant_id == 1 else 7
            return MockResult([[count_val]])

        # SELECT tags by id (more specific — check before generic SELECT by id)
        if ("select" in sql_text and "from customers" in sql_text
                and "tags" in sql_text and "where id" in sql_text):
            customer_id = params.get("id")
            if customer_id in state.customers:
                c = state.customers[customer_id]
                return MockResult([MockRow({"id": customer_id, "tags": c.get("tags", "[]")})])
            return MockResult([])

        # SELECT by id
        if "from customers where id" in sql_text:
            customer_id = params.get("id")
            if customer_id in state.customers:
                return MockResult([MockRow(state.customers[customer_id].copy())])
            fixtures = {
                1: {"id": 1, "tenant_id": 1, "name": "Customer A", "email": "a@test.com",
                    "phone": "123", "company": "Acme", "status": "lead",
                    "owner_id": 1, "tags": "[]", "created_at": None, "updated_at": None},
            }
            if customer_id in fixtures:
                return MockResult([MockRow(fixtures[customer_id].copy())])
            return MockResult([])

        # SELECT list (no WHERE id)
        if "select" in sql_text and "from customers" in sql_text and "where id" not in sql_text:
            tenant_filter = params.get("tenant_id", 0)
            rows = []
            for cid, rec in state.customers.items():
                if rec.get("tenant_id") == tenant_filter:
                    rows.append(MockRow(rec.copy()))
            rows.extend([
                MockRow({
                    "id": 1, "tenant_id": tenant_filter,
                    "name": "Customer A", "email": "a@test.com",
                    "phone": "123", "company": "Acme",
                    "status": "lead", "owner_id": 1,
                    "tags": "[]", "created_at": None, "updated_at": None,
                }),
                MockRow({
                    "id": 2, "tenant_id": tenant_filter,
                    "name": "Customer B", "email": "b@test.com",
                    "phone": "456", "company": "Beta",
                    "status": "customer", "owner_id": 1,
                    "tags": "[]", "created_at": None, "updated_at": None,
                }),
            ])
            if tenant_filter == 2:
                rows = []
            return MockResult(rows)

        return None

    return handler


def make_user_handler(state: MockState):
    """Handle all user-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""

    def handler(sql_text, params):
        # INSERT (checked before the guard because INSERT doesn't have "from users")
        if "insert into users" in sql_text:
            uid = state.users_next_id
            state.users_next_id += 1
            record = {
                "id": uid,
                "tenant_id": params.get("tenant_id", 0),
                "username": params.get("username"),
                "email": params.get("email"),
                "password_hash": None,
                "role": params.get("role", "user"),
                "status": "pending",
                "full_name": params.get("full_name"),
                "bio": None,
                "created_at": params.get("created_at"),
                "updated_at": params.get("created_at"),
            }
            state.users[uid] = record
            return MockResult([MockRow(record.copy())])

        # Guard: only handle queries that reference the users table
        is_user_query = (
            "from users" in sql_text
            or (sql_text.startswith("update") and "users" in sql_text)
        )
        if not is_user_query:
            return None

        # DELETE
        if sql_text.startswith("delete") and "users" in sql_text:
            user_id = params.get("id")
            was_in_mock = user_id in state.users
            if was_in_mock:
                state.users[user_id]["status"] = "deleted"
                del state.users[user_id]
            state.deleted_user_ids.add(user_id)
            if was_in_mock:
                return MockResult([MockRow({"id": user_id})])
            return MockResult([])

        # UPDATE by id
        if ("set " in sql_text or sql_text.startswith("update")) and "where id" in sql_text:
            user_id = params.get("id")
            if user_id in state.users:
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        state.users[user_id][k] = v
                return MockResult([MockRow(state.users[user_id].copy())])
            return MockResult([])

        # COUNT
        if "select" in sql_text and "count" in sql_text and "from users" in sql_text:
            count_val = len(state.users)
            if count_val == 0:
                tenant_id = params.get("tenant_id")
                count_val = 7 if tenant_id == 1 else 3
            return MockResult([[count_val]])

        # SELECT by username
        if "where username" in sql_text:
            username = params.get("username")
            for uid, rec in state.users.items():
                if rec.get("username") == username:
                    return MockResult([MockRow(rec.copy())])
            fixtures = {
                "existing": {"id": 1, "tenant_id": 0, "username": "existing",
                             "email": "existing@test.com", "password_hash": None,
                             "role": "user", "status": "pending", "full_name": None, "bio": None},
                "alice":    {"id": 1, "tenant_id": 1, "username": "alice",
                             "email": "alice@test.com", "password_hash": None,
                             "role": "user", "status": "active", "full_name": "Alice", "bio": "bio"},
                "john_doe": {"id": 2, "tenant_id": 0, "username": "john_doe",
                             "email": "john@test.com", "password_hash": None,
                             "role": "user", "status": "pending", "full_name": "John Doe", "bio": None},
                "jane_doe": {"id": 3, "tenant_id": 0, "username": "jane_doe",
                             "email": "jane@test.com", "password_hash": None,
                             "role": "user", "status": "pending", "full_name": "Jane Doe", "bio": None},
            }
            if username in fixtures:
                row = fixtures[username].copy()
                now = dt.utcnow()
                row["created_at"] = now
                row["updated_at"] = now
                return MockResult([MockRow(row)])
            return MockResult([])

        # SELECT by email
        if "where email" in sql_text:
            email = params.get("email")
            for uid, rec in state.users.items():
                if rec.get("email") == email:
                    return MockResult([MockRow(rec.copy())])
            if email == "existing@test.com":
                now = dt.utcnow()
                return MockResult([MockRow({
                    "id": 1, "tenant_id": 0, "username": "existing",
                    "email": "existing@test.com", "password_hash": None,
                    "role": "user", "status": "pending", "full_name": None, "bio": None,
                    "created_at": now, "updated_at": now,
                })])
            return MockResult([])

        # SELECT by id
        if "where id" in sql_text:
            user_id = params.get("id")
            if user_id in state.users:
                return MockResult([MockRow(state.users[user_id].copy())])
            if user_id in state.deleted_user_ids:
                return MockResult([])
            fixtures = {
                1: {"id": 1, "tenant_id": 0, "username": "existing",
                    "email": "existing@test.com", "password_hash": None,
                    "role": "user", "status": "pending", "full_name": None, "bio": None},
                5: {"id": 5, "tenant_id": 1, "username": "charlie",
                    "email": "charlie@test.com", "password_hash": None,
                    "role": "admin", "status": "active", "full_name": "Charlie", "bio": "dev"},
            }
            if user_id in fixtures:
                row = fixtures[user_id].copy()
                now = dt.utcnow()
                row["created_at"] = now
                row["updated_at"] = now
                return MockResult([MockRow(row)])
            return MockResult([])

        # SELECT list (generic)
        if state.users:
            return MockResult([MockRow(r.copy()) for r in state.users.values()])
        now = dt.utcnow()
        rows = [
            MockRow({"id": 1, "tenant_id": 0, "username": "existing",
                     "email": "existing@test.com", "password_hash": None,
                     "role": "user", "status": "pending", "full_name": None, "bio": None,
                     "created_at": now, "updated_at": now}),
            MockRow({"id": 2, "tenant_id": 0, "username": "john_doe",
                     "email": "john@test.com", "password_hash": None,
                     "role": "user", "status": "pending", "full_name": "John Doe", "bio": None,
                     "created_at": now, "updated_at": now}),
            MockRow({"id": 3, "tenant_id": 0, "username": "jane_doe",
                     "email": "jane@test.com", "password_hash": None,
                     "role": "user", "status": "pending", "full_name": "Jane Doe", "bio": None,
                     "created_at": now, "updated_at": now}),
        ]
        return MockResult(rows)

    return handler


def tenant_handler(sql_text, params):
    """Handle all tenant-related SQL (stateless)."""

    # INSERT
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

    # DELETE
    if "delete" in sql_text and "tenants" in sql_text:
        tenant_id = params.get("tenant_id")
        if tenant_id and tenant_id != 1:
            return MockResult([])
        return MockResult([[1, "Deleted Tenant", "pro", "deleted", "{}", None, None]])

    # UPDATE
    if "update" in sql_text and "tenants" in sql_text:
        tenant_id = params.get("tenant_id") or params.get("id")
        if tenant_id == 1:
            return MockResult([[1, "Updated Name", "pro", "active", "{}", None, None]])
        return MockResult([])

    # COUNT
    if "select" in sql_text and "count" in sql_text and "from tenants" in sql_text:
        return MockResult([[2]])

    # SELECT (not count)
    if "select" in sql_text and "from tenants" in sql_text and "count" not in sql_text:
        tenant_id = params.get("tenant_id")

        # Specific lookup: LIMIT 1 + WHERE id
        if "limit 1" in sql_text and "where id" in sql_text:
            if tenant_id == 1:
                return MockResult([MockRow({"id": 1})])
            if tenant_id == 42:
                return MockResult([MockRow({
                    "id": 42, "name": "Beta Org", "plan": "enterprise",
                    "status": "active", "settings": '{"sso": true}',
                    "created_at": None, "updated_at": None,
                })])
            return MockResult([])

        # List query (no WHERE id)
        if "where id" not in sql_text:
            rows = [
                MockRow({"id": 1, "name": "Tenant A", "plan": "pro", "status": "active",
                         "settings": "{}", "created_at": None, "updated_at": None}),
                MockRow({"id": 2, "name": "Tenant B", "plan": "enterprise", "status": "active",
                         "settings": "{}", "created_at": None, "updated_at": None}),
            ]
            return MockResult(rows)

        # General SELECT with WHERE id (not LIMIT 1)
        if tenant_id == 42:
            return MockResult([MockRow({
                "id": 42, "name": "Beta Org", "plan": "enterprise",
                "status": "active", "settings": '{"sso": true}',
                "created_at": None, "updated_at": None,
            })])
        return MockResult([])

    return None


def pipeline_handler(sql_text, params):
    """Handle pipeline-related SQL (stateless)."""

    if "insert into pipelines" in sql_text:
        return MockResult([MockRow({
            "id": 1, "tenant_id": params.get("tenant_id", 0),
            "name": params.get("name", "Pipeline"),
            "description": params.get("description"),
            "is_active": True,
            "created_at": params.get("created_at"),
            "updated_at": params.get("updated_at"),
        })])

    if "from pipelines" in sql_text:
        return MockResult([MockRow({
            "id": 1, "tenant_id": 1,
            "name": "Pipeline A", "description": "Desc",
            "is_active": True, "created_at": None, "updated_at": None,
        })])

    return None


def opportunity_handler(sql_text, params):
    """Handle opportunity-related SQL (stateless)."""

    if "insert into opportunities" in sql_text:
        return MockResult([MockRow({
            "id": 1, "tenant_id": params.get("tenant_id", 0),
            "customer_id": 1, "title": params.get("title", "Opportunity"),
            "amount": params.get("amount", 1000),
            "stage": "qualification",
            "probability": 20,
            "owner_id": params.get("owner_id", 0),
            "expected_close_date": params.get("expected_close_date"),
            "created_at": params.get("created_at"),
            "updated_at": params.get("updated_at"),
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

    return None


def ticket_sql_handler(sql_text, params):
    """Handle ticket-related SQL (stateless)."""

    if "insert into tickets" in sql_text:
        return MockResult([MockRow({
            "id": 1, "tenant_id": params.get("tenant_id", 0),
            "subject": params.get("subject", "Ticket"),
            "description": params.get("description"),
            "status": "open",
            "priority": params.get("priority", "medium"),
            "customer_id": 1,
            "assignee_id": params.get("assignee_id"),
            "created_at": params.get("created_at"),
            "updated_at": params.get("updated_at"),
        })])

    if "from tickets" in sql_text:
        return MockResult([MockRow({
            "id": 1, "tenant_id": 1,
            "subject": "Issue A", "description": "Desc",
            "status": "open", "priority": "medium",
            "customer_id": 1, "assignee_id": 1,
            "created_at": None, "updated_at": None,
        })])

    return None


def campaign_handler(sql_text, params):
    """Handle campaign-related SQL (stateless)."""

    if "insert into campaigns" in sql_text:
        return MockResult([MockRow({
            "id": 1, "tenant_id": params.get("tenant_id", 0),
            "name": params.get("name", "Campaign"),
            "campaign_type": params.get("campaign_type", "email"),
            "status": "draft",
            "created_by": params.get("created_by"),
            "created_at": params.get("created_at"),
            "updated_at": params.get("updated_at"),
        })])

    if "from campaigns" in sql_text:
        return MockResult([MockRow({
            "id": 1, "tenant_id": 1,
            "name": "Campaign A", "campaign_type": "email",
            "status": "draft", "created_by": 1,
            "created_at": None, "updated_at": None,
        })])

    return None


def make_count_handler(state: MockState):
    """Fallback COUNT handler for queries not caught by domain handlers."""

    def handler(sql_text, params):
        if "select" not in sql_text or "count" not in sql_text:
            return None
        tenant_id = params.get("tenant_id")
        count_val = 7 if tenant_id == 1 else 3
        return MockResult([[count_val]])

    return handler


def make_automation_handler(state: MockState):
    """Handle automation rules SQL (INSERT, SELECT, DELETE, COUNT)."""

    def handler(sql_text, params):
        tenant_id = params.get("tenant_id", 0)

        # INSERT automation_rule
        if "insert into automation_rules" in sql_text:
            rid = state.automation_rules_next_id
            state.automation_rules_next_id += 1
            record = {
                "id": rid,
                "tenant_id": tenant_id,
                "name": params.get("name", "Rule"),
                "description": params.get("description"),
                "trigger_event": params.get("trigger_event", ""),
                "conditions": _json.dumps(params.get("conditions", [])),
                "actions": _json.dumps(params.get("actions", [])),
                "enabled": params.get("enabled", True),
                "created_by": params.get("created_by"),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.automation_rules[rid] = record
            return MockResult([MockRow(record.copy())], rowcount=1)

        # SELECT automation_rules by id
        if ("select" in sql_text and "from automation_rules" in sql_text
                and "where id" in sql_text and "count" not in sql_text):
            rid = params.get("id")
            if rid in state.automation_rules:
                row = state.automation_rules[rid]
                return MockResult([MockRow(row.copy())])

        # SELECT automation_rules list (no id filter) — count first, then data
        if ("select" in sql_text and "from automation_rules" in sql_text
                and "count" not in sql_text and "order_by" not in sql_text):
            rows = [MockRow(r.copy()) for r in state.automation_rules.values()
                    if r.get("tenant_id") == tenant_id]
            return MockResult(rows if rows else [])

        # SELECT COUNT from automation_rules
        if ("select" in sql_text and "from automation_rules" in sql_text
                and "count" in sql_text):
            count_val = sum(1 for r in state.automation_rules.values() if r.get("tenant_id") == tenant_id)
            if count_val == 0:
                count_val = 2  # seeded count
            return MockResult([[count_val]])

        # UPDATE automation_rules (toggle, general update)
        if "update" in sql_text and "automation_rules" in sql_text:
            rid = params.get("id")
            if rid in state.automation_rules:
                rec = state.automation_rules[rid]
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        rec[k] = v
                return MockResult([MockRow(rec.copy())], rowcount=1)
            return MockResult([], rowcount=0)

        # DELETE automation_rules
        if "delete" in sql_text and "automation_rules" in sql_text:
            rid = params.get("id")
            if rid in state.automation_rules:
                del state.automation_rules[rid]
                return MockResult([MockRow({"id": rid})], rowcount=1)
            return MockResult([], rowcount=0)

        return None

    return handler


# ---------------------------------------------------------------------------
# Session builder
# ---------------------------------------------------------------------------


def all_handlers(state: MockState):
    """Return the full list of domain handlers (default for backward compat)."""
    return [
        make_customer_handler(state),
        make_user_handler(state),
        tenant_handler,
        pipeline_handler,
        opportunity_handler,
        ticket_sql_handler,
        campaign_handler,
        make_automation_handler(state),
        make_count_handler(state),
    ]


def make_mock_session(handlers=None):
    """Create a mock AsyncSession wired to the given SQL handlers.

    If *handlers* is ``None``, all domain handlers with fresh state are used.
    Tests that want a subset can pass their own list::

        state = MockState()
        session = make_mock_session([
            make_customer_handler(state),
            make_count_handler(state),
        ])
    """
    if handlers is None:
        handlers = all_handlers(MockState())

    session = MagicMock(spec=[
        "execute", "add", "delete", "commit", "rollback",
        "close", "flush", "refresh", "scalars", "scalar_one_or_none",
        "scalar_one", "get", "result", "__aenter__", "__aexit__",
    ])

    def _execute_side_effect(sql, params=None):
        sql_text = str(sql).lower().strip()
        params = params or {}
        for h in handlers:
            result = h(sql_text, params)
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
