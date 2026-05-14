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

---

## Project Layout (abbreviated)

```
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
    conftest.py         # MockRow, MockResult, MockState, handlers
    test_*.py
  integration/
    conftest.py         # Real DB fixtures (db_schema, tenant_id, async_session)
    test_*_integration.py
```

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

### ❌ Don't
- Call `.to_dict()` inside services.
- Return `ApiResponse` from services.
- Use `async with get_db() as session:` in routers.
- Use try/catch in routers for service errors.
- Use flake8 / pylint / black.
- Use global autouse DB patching in tests.
- Use module-level in-memory state for new services.
