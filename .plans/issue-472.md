Now I have everything needed. The plan is grounded in the real codebase: `src/internal/middleware/` exists with an empty `__init__.py`; `tenant_context.py` doesn't exist yet; the only consumer of the old `TenantContext` in `tests/unit/test_tenant_isolation.py` needs migration awareness.

---

# Implementation Plan — Issue #472

## Goal

Create `src/internal/middleware/tenant_context.py` — a pure-stdlib, async-safe tenant ID storage module backed by `contextvars.ContextVar` — exposing `set_tenant_id`, `get_tenant_id`, and `clear`. Write two required unit tests plus one async propagation test. Leave `TenantMiddleware` and `TenantService` untouched.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/00-foundations/0472-implement-tenantcontext-utility-module.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/00-foundations/0472-implement-tenantcontext-utility-module.md`

## Affected Files

- `src/internal/middleware/tenant_context.py` — **new** — `contextvars`-based tenant ID storage, 3 public functions
- `src/internal/middleware/__init__.py` — **modified** — re-export `set_tenant_id`, `get_tenant_id`, `clear` from the new module
- `tests/unit/test_tenant_context.py` — **new** — 3 unit tests (2 required + 1 async propagation)

## Implementation Steps

### Step 1: Create `src/internal/middleware/tenant_context.py`

Write the new module directly (file does not exist yet). Use `contextvars.ContextVar` — the correct primitive for async/await contexts — not `threading.local`.

```python
"""Thread-safe tenant ID storage using contextvars.

Unlike threading.local, ContextVar correctly propagates across
asyncio tasks within the same request context.
"""
from contextvars import ContextVar
from typing import Optional

_tenant_id_var: ContextVar[Optional[int]] = ContextVar("tenant_id", default=None)


def set_tenant_id(tenant_id: int) -> None:
    """Store the current tenant_id in the request context."""
    _tenant_id_var.set(tenant_id)


def get_tenant_id() -> Optional[int]:
    """Retrieve the current tenant_id from the request context.

    Returns None if no tenant context has been set.
    """
    return _tenant_id_var.get()


def clear() -> None:
    """Clear the tenant context.

    Call this at the end of a request to prevent tenant_id leaking
    into subsequent requests processed by the same worker.
    """
    _tenant_id_var.set(None)
```

### Step 2: Update `src/internal/middleware/__init__.py`

The file already exists as a package marker (`"""空文件，用于 Python 包标识"""`). Overwrite it to add the three re-exports:

```python
from .tenant_context import clear, get_tenant_id, set_tenant_id

__all__ = ["clear", "get_tenant_id", "set_tenant_id"]
```

### Step 3: Create `tests/unit/test_tenant_context.py`

Create the file — does not exist yet. Import path uses `internal.middleware.tenant_context` (no `src.` prefix, consistent with the project's `PYTHONPATH=src` convention).

```python
"""Unit tests for tenant_context module."""
import pytest

from internal.middleware.tenant_context import clear, get_tenant_id, set_tenant_id


class TestTenantContext:
    def test_set_and_get_tenant_id(self):
        """Setting a tenant_id can be retrieved."""
        clear()
        set_tenant_id(42)
        assert get_tenant_id() == 42
        clear()

    def test_clear_tenant_id(self):
        """Clearing removes the stored tenant_id."""
        set_tenant_id(99)
        clear()
        assert get_tenant_id() is None

    @pytest.mark.asyncio
    async def test_tenant_id_propagates_across_await(self):
        """tenant_id is visible inside an awaited helper coroutine."""
        clear()
        set_tenant_id(7)

        async def helper():
            return get_tenant_id()

        result = await helper()
        assert result == 7
        clear()
```

### Step 4: Lint + format verification

Run both ruff check and format check on the two new files, then on the whole `src/` tree to confirm nothing regressed:

```
ruff check src/internal/middleware/tenant_context.py src/internal/middleware/__init__.py tests/unit/test_tenant_context.py
ruff format --check src/internal/middleware/tenant_context.py tests/unit/test_tenant_context.py
ruff check src/
```

Fix any reported issues.

## Test Plan

- Unit tests in `tests/unit/`: create `tests/unit/test_tenant_context.py` covering:
  - `test_set_and_get_tenant_id` — basic set/get roundtrip
  - `test_clear_tenant_id` — clear returns `None`
  - `test_tenant_id_propagates_across_await` — async propagation (bonus test from dev-plan)
- Integration tests in `tests/integration/`: none required — this is a pure utility module with no DB or HTTP surface
- Dev-plan verification (each step has a corresponding check above):
  - Step 1 → `ruff check src/internal/middleware/tenant_context.py` exit 0
  - Step 2 → `ruff check src/internal/middleware/__init__.py` exit 0
  - Step 3 → `PYTHONPATH=src pytest tests/unit/test_tenant_context.py -v` → `3 passed`
  - Step 4 → lint/format full clean

## Acceptance Criteria

- `src/internal/middleware/tenant_context.py` exists with `set_tenant_id(tenant_id: int)`, `get_tenant_id() -> int | None`, and `clear()` — all backed by a single `ContextVar`
- `src/internal/middleware/__init__.py` re-exports the three functions
- `tests/unit/test_tenant_context.py` exists and its 3 tests pass
- `ruff check src/ && ruff format --check src/internal/middleware/` both exit 0
- No FastAPI, Starlette, or SQLAlchemy imports in `tenant_context.py`
- `TenantMiddleware` and `TenantService` are not touched
