---
name: dev-agent-system
description: >
  Conventions, patterns, and rules for the dev-agent-system multi-tenant CRM
  (FastAPI + SQLAlchemy 2.x async + PostgreSQL). Use this skill whenever you are
  adding a new service, router, ORM model, unit test, integration test, or Alembic
  migration in this project. Trigger on any task that involves writing or editing
  Python files under src/ or tests/, running pytest, running ruff/mypy, or working
  with Alembic — even if the user doesn't phrase it as "follow the conventions".
  This skill is the authoritative reference for all code patterns in this repo.
---

# dev-agent-system — Coding Skill

Multi-tenant CRM: **FastAPI + SQLAlchemy 2.x async + PostgreSQL**.  
Branch: `fastapi-migration → master`

## Quick-Start Rules

Before writing any code, confirm:

1. `PYTHONPATH=src` is exported.
2. Session is **always** `AsyncSession` — never `None`, never `sync`.
3. Every SQL query includes `WHERE tenant_id = :tenant_id`.
4. Services **return ORM objects** and **raise exceptions** — no `.to_dict()`, no `ApiResponse`.
5. Routers **serialize** and **wrap** — no business logic, no try/catch.
6. Tests use **per-file mock fixtures** — no global autouse patching.
7. Linting: `ruff check src/ && ruff format --check src/` — never flake8/black.

When reviewing code or plans, also check recent recurring failure modes:

- Unit SQL mocks must use the same bind parameter names as the query and must enforce tenant scope.
- DTO validators must match declared optionality/types; enum fields must reject unrelated truthy values.
- `to_dict()`, logs, and response schemas must exclude secrets, tokens, and password hashes by allow-list.
- Tenant-owned ORM models need real `tenants.id` foreign keys plus consistent audit/lifecycle fields.
- `.plans/issue-*.md` must match the issue objectives, implementation files, test counts, and executable validation commands.
- CI must be fork-aware: do not require unavailable secrets for fork PRs, and prefer SHA-based diffs over branch-name diffs.
- CI artifacts must be useful outputs, not internal caches such as `.pytest_cache/`.
- Async tests must use `await asyncio.sleep(...)` or fake clocks, never `time.sleep(...)`.
- Batch/import validation tests should assert counters and representative error records, not only that errors exist.
- Markdown fences in docs/plans/skills need explicit language tags such as `text`, `bash`, `python`, or `yaml`.

---

## Project Layout (abbreviated)

```text
src/
  api/routers/          # FastAPI route handlers
  services/             # Business logic — one class per domain
  models/               # Pydantic schemas + ORM models
  db/
    connection.py       # get_db_session / engine
    base.py             # Declarative Base
    models/             # SQLAlchemy ORM models
  middleware/
  dependencies/         # get_current_user, require_auth, etc.
  main.py
tests/
  unit/
    conftest.py         # MockRow, MockResult, MockState, core handlers + discovery
    domain_handlers/    # Domain-owned mock SQL handlers
    test_*.py
  integration/
    conftest.py         # Real DB fixtures (db_schema, tenant_id, async_session)
    domain_fixtures/    # Domain-owned integration seed helpers
    test_*_integration.py
```

### Domain Ownership

Feature domains own their registration files. Do not add new domains by editing
central registries:

- Routers: add `src/api/routers/<domain>.py` exporting an `APIRouter`; `api.iter_routers()` discovers it.
- ORM models: add `src/db/models/<domain>.py`; `db.models` imports all model modules for `Base.metadata`.
- Unit SQL handlers: add `tests/unit/domain_handlers/<domain>.py` with `get_handlers(state)`.
- Integration seed helpers: add `tests/integration/domain_fixtures/<domain>.py`.
- Do not update `src/api/__init__.py`, `src/db/models/__init__.py`, `tests/unit/conftest.py`, or `tests/integration/conftest.py` for routine domain additions.

---

## Patterns

For detailed, copy-paste-ready templates see the reference files:

| Topic | File |
|---|---|
| Service pattern | `references/service.md` |
| Router pattern | `references/router.md` |
| Unit tests | `references/unit_tests.md` |
| Integration tests | `references/integration_tests.md` |
| Alembic migrations | `references/migrations.md` |

Read only the file(s) relevant to the current task.

---

## Error Handling — Quick Reference

All exceptions live in `pkg/errors/app_exceptions.py` and extend `AppException`.  
The global handler in `main.py` converts them to JSON. **Never catch in routers.**

| Exception | HTTP | When |
|---|---|---|
| `NotFoundException(resource)` | 404 | Entity not found |
| `ValidationException(detail)` | 422 | Invalid input / business rule |
| `ForbiddenException(detail)` | 403 | Insufficient permissions |
| `ConflictException(detail)` | 409 | Duplicate / constraint violation |
| `UnauthorizedException(detail)` | 401 | Missing / invalid auth |

---

## Key Commands

```bash
export PYTHONPATH=src

# Unit tests (no DB)
pytest tests/unit/ -v

# All non-integration tests
pytest tests/ -m "not integration" -v

# Integration tests
DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/ -v

# Lint + format check
ruff check src/ && ruff format --check src/

# Type check
mypy src/
```

---

## Do / Don't Checklist

### ✅ Do
- Services return domain objects (ORM models / dicts from rows).
- Services raise `AppException` subclasses on errors.
- Routers call `.to_dict()` and wrap in `{"success": True, "data": ..., "message": ...}`.
- Routers inject session via `session: AsyncSession = Depends(get_db)`.
- Every `__init__` types session as `AsyncSession` with **no default**.
- Every SQL query filters by `tenant_id`.
- Each test file defines its own `mock_db_session` fixture.
- New domain test helpers live under `tests/unit/domain_handlers/` or `tests/integration/domain_fixtures/`.
- Unit mock handlers validate bind params and tenant scope.
- Identity/auth serialization uses allow-lists that exclude credential material.
- CI/review workflow changes account for forked PRs and missing secrets.

### ❌ Don't
- Call `.to_dict()` inside services.
- Return `ApiResponse` from services.
- Use `async with get_db() as session:` in routers.
- Use try/catch in routers for service errors.
- Use flake8 / pylint / black.
- Use global autouse DB patching in tests.
- Use module-level in-memory state for new services.
- Edit central router/model/conftest registries for routine domain additions.
- Let tests pass with mismatched SQL placeholders and mock params.
- Upload `.pytest_cache/` as a CI test artifact.
- Use `time.sleep()` inside async tests.
