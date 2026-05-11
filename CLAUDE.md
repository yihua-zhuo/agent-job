# dev-agent-system — Claude Code Reference

Multi-tenant CRM system (FastAPI + SQLAlchemy 2.x async + PostgreSQL).

Branch: fastapi-migration → master
CI: GitHub Actions (Unit Tests + Integration Tests + Ruff/Lint)

---

## Project Structure

dev-agent-system/
├── src/
│   ├── api/routers/          # FastAPI route handlers
│   ├── services/             # Business logic (one service per domain)
│   ├── models/               # Pydantic schemas + ORM models
│   │   └── response.py       # ApiResponse[T] unified response model
│   ├── db/
│   │   ├── connection.py     # get_db_session / engine
│   │   ├── base.py           # Declarative Base
│   │   └── models/           # SQLAlchemy ORM models
│   ├── middleware/
│   ├── dependencies/          # FastAPI DI (get_current_user, etc.)
│   └── main.py               # App entry point
├── tests/
│   ├── unit/                 # Mock DB, fast (<5s)
│   │   ├── conftest.py       # MockRow, MockResult, MockState, domain handlers
│   │   └── test_*.py
│   └── integration/          # Real PostgreSQL
│       └── conftest.py       # Real DB fixtures
├── pyproject.toml
├── pytest.ini
└── .env                      # Required: DATABASE_URL

---

## Key Commands

# Set PYTHONPATH before everything
export PYTHONPATH=src

# Run unit tests (no DB needed)
pytest tests/unit/ -v

# Run integration tests (needs DATABASE_URL)
DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/ -v

# Run all tests except integration
pytest tests/ -m "not integration" -v

# Lint + format
ruff check src/ && ruff format --check src/

# Type check
mypy src/

# Full check pipeline
ruff check src/ && ruff format --check src/ && mypy src/

---

## Alembic Migrations

Migrations live in `alembic/versions/` and target Postgres via the async driver. `alembic/env.py`
loads `db.base.Base.metadata` and every ORM model in `db.models`, so any model registered there is
visible to `--autogenerate`.

**Setup (one-time per shell):**

    export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"  # if `alembic` isn't on PATH
    export PYTHONPATH=src
    export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"

Always use a dedicated, disposable database for autogenerate — never point it at the test DB
(which is populated by `Base.metadata.create_all` in `tests/integration/conftest.py`) or any DB
where you can't tell apart "in models" vs. "in a prior migration." Mixing them produces phantom
diffs.

**Generate a new migration (autogenerate from model diff):**

    # 1. Spin up a clean DB
    docker compose -f configs/docker-compose.test.yml up -d test-db
    docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
    docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

    # 2. Bring it to current head
    alembic upgrade head

    # 3. Autogenerate the diff
    alembic revision --autogenerate -m "describe_change_here"

    # 4. Review alembic/versions/<id>_describe_change_here.py — autogen never gets it 100% right
    #    (data migrations, enum changes, server defaults, indexes on JSON keys, etc).

    # 5. Verify the migration applies and downgrades cleanly
    alembic upgrade head
    alembic downgrade -1
    alembic upgrade head

    # 6. Confirm no residual drift — second autogen should produce an empty migration; delete it
    alembic revision --autogenerate -m "drift_check"
    # If the new file has `pass` in both up/down, delete it. If not, your first migration was incomplete.

**Other useful commands:**

    alembic current               # show applied revision
    alembic history --verbose     # list all revisions
    alembic upgrade <rev>         # apply up to a specific revision
    alembic downgrade <rev>       # revert to a specific revision (use base to revert all)
    alembic stamp head            # mark DB as up-to-date without running migrations (use with care)

**Rules:**

- Every new model in `src/db/models/` must be imported in `alembic/env.py`, otherwise autogen
  ignores it.
- Migrations must be reversible — fill in `downgrade()` even if autogen left it blank.
- Don't edit a migration that has shipped to any environment; write a new one instead.
- Don't run autogenerate against the test database (`test_db`) — it's already at the model state
  via `create_all`, so autogen will produce an empty diff and you'll miss real drift. Use a
  separate `alembic_dev` database as shown above.

---

## Conventions

### Service Pattern

- One service class per domain (e.g. CustomerService, SalesService)
- Constructor takes required `session: AsyncSession` — **null is not allowed**, no default value
- All methods accept tenant_id: int and include it in every SQL WHERE clause
- **Return ORM/model objects** on success — never call `.to_dict()` in the service
- **Raise exceptions** on errors — never return `ApiResponse.error()` from a service
- Router handles serialization (`.to_dict()`) and response envelope

    from sqlalchemy.ext.asyncio import AsyncSession
    from pkg.errors.app_exceptions import NotFoundException, ValidationException

    class MyService:
        def __init__(self, session: AsyncSession):
            self.session = session

        async def get_entity(self, entity_id: int, tenant_id: int) -> EntityModel:
            result = await self.session.execute(...)
            entity = result.scalar_one_or_none()
            if entity is None:
                raise NotFoundException("Entity")
            return entity  # return ORM object, not dict

        async def list_entities(self, tenant_id: int, page: int, page_size: int) -> tuple[list[EntityModel], int]:
            # ... count + fetch ...
            return entities, total  # return (items, total) for paginated

**Rules:**
- Every service `__init__` that takes a session must type it as `AsyncSession` with no default. Never allow `session=None`.
- Services return domain objects. Routers serialize them.
- Services raise `AppException` subclasses (`NotFoundException`, `ValidationException`, `ForbiddenException`). The global exception handler in `main.py` converts them to JSON responses.

### Error Handling

Services raise, routers catch (via global handler in `main.py`):

| Exception | HTTP | When |
|---|---|---|
| `NotFoundException(resource)` | 404 | Entity not found |
| `ValidationException(detail)` | 422 | Invalid input / business rule |
| `ForbiddenException(detail)` | 403 | Insufficient permissions |
| `ConflictException(detail)` | 409 | Duplicate / constraint violation |
| `UnauthorizedException(detail)` | 401 | Missing / invalid auth |

Defined in `pkg/errors/app_exceptions.py`. All extend `AppException`.

### Router Pattern

Routers call services, serialize results, return envelope:

    @router.get("/{entity_id}")
    async def get_entity(
        entity_id: int,
        ctx: AuthContext = Depends(require_auth),
        session: AsyncSession = Depends(get_db),
    ):
        svc = MyService(session)
        entity = await svc.get_entity(entity_id, tenant_id=ctx.tenant_id)
        return {"success": True, "data": entity.to_dict()}

    @router.get("/")
    async def list_entities(
        page: int = 1,
        page_size: int = 20,
        ctx: AuthContext = Depends(require_auth),
        session: AsyncSession = Depends(get_db),
    ):
        svc = MyService(session)
        items, total = await svc.list_entities(tenant_id=ctx.tenant_id, page=page, page_size=page_size)
        return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total, ...}}

**Rules:**
- Session is injected via `Depends(get_db)` — never use `async with get_db() as session:` manually.
- No try/catch needed — `AppException` is caught globally. Router only handles serialization.

### SQLAlchemy Async

- Use asyncpg driver: postgresql+asyncpg://user:pass@host:5432/db
- All DB ops are async (async def, await)
- Use text() for raw SQL when needed

### Multi-Tenancy

Every SQL query must filter by tenant_id:

    WHERE tenant_id = :tenant_id

### Unit Test SQL Mocks

Each test file mocks only what it needs. conftest.py provides composable building blocks:

- **`MockState`** — per-test mutable state (customers, users auto-increment IDs)
- **`MockRow` / `MockResult`** — simulate SQLAlchemy Row / Result objects
- **`make_mock_session(handlers)`** — build a mock session with specific domain handlers
- **Domain handlers** — one per table, each handles INSERT/UPDATE/DELETE/SELECT/COUNT:

| Handler | Factory | Stateful |
|---|---|---|
| `make_customer_handler(state)` | yes | yes |
| `make_user_handler(state)` | yes | yes |
| `tenant_handler` | no | no |
| `pipeline_handler` | no | no |
| `opportunity_handler` | no | no |
| `ticket_sql_handler` | no | no |
| `campaign_handler` | no | no |
| `make_count_handler(state)` | yes | yes |

Each test file defines its own `mock_db_session` fixture with only the handlers it needs:

    from tests.unit.conftest import make_mock_session, make_customer_handler, make_count_handler, MockState

    @pytest.fixture
    def mock_db_session():
        state = MockState()
        return make_mock_session([make_customer_handler(state), make_count_handler(state)])

    @pytest.fixture
    def customer_service(mock_db_session):
        return CustomerService(mock_db_session)

Rule: no global autouse patching — each test owns its mock. Real SQL is never executed in unit tests.

### Integration Test Fixtures

| Fixture | Purpose |
|---|---|
| db_schema | Auto-creates/drops all tables per function |
| tenant_id | Current tenant ID |
| async_session | Function-scoped session, shared across services in one test |

---

## Rules

### Do

1. Services return domain objects (ORM models, dataclasses, dicts from rows) — never `ApiResponse` or `.to_dict()`.
2. Services raise `AppException` subclasses on errors — never return error responses.
3. Routers serialize via `.to_dict()` and wrap in `{"success": True, "data": ..., "message": ...}`.
4. Routers inject session via `session: AsyncSession = Depends(get_db)` — never `async with get_db()`.
5. Every service `__init__` types session as `AsyncSession` with no default — never `session=None`.
6. Every SQL query filters by `tenant_id`.
7. Each test file defines its own `mock_db_session` fixture with only the handlers it needs.
8. Linting uses ruff — `ruff check src/` for lint, `ruff format` for formatting.

### Don't

1. Don't call `.to_dict()` in services — that's the router's job.
2. Don't return `ApiResponse` from services — return the object directly.
3. Don't use `async with get_db() as session:` in routers — use `Depends(get_db)`.
4. Don't use try/catch in routers for service errors — the global `AppException` handler covers it.
5. Don't use flake8/pylint/black — use ruff.
6. Don't use global autouse DB patching in tests — each test owns its mock.
7. Don't use module-level in-memory state for new services — use real DB with ORM models.

## Gotchas & Tips

1. PYTHONPATH is required — always export PYTHONPATH=src before running anything.
2. DATABASE_URL must use `postgresql+asyncpg` — the asyncpg driver, not psycopg2.
3. pre-push hook blocks on ruff/mypy — use `git push --no-verify` as a temporary bypass, then fix the error. Don't normalize the bypass.
4. Integration test TRUNCATE CASCADE — schema fixture truncates all tables between tests; don't rely on data persisting within a test file.
5. Cross-service seeds — use `_seed_customer` / `_seed_user` helpers to set up dependencies (e.g. ticket needs a customer first).

---

## Adding New Features

### New unit test

1. Create tests/unit/test_XXX.py
2. Define a `mock_db_session` fixture with only the handlers your test needs
3. If new SQL pattern needed → add a handler in conftest.py, then use it in the test file

    from tests.unit.conftest import make_mock_session, make_customer_handler, make_count_handler, MockState

    @pytest.fixture
    def mock_db_session():
        state = MockState()
        return make_mock_session([make_customer_handler(state), make_count_handler(state)])

    @pytest.fixture
    def my_service(mock_db_session):
        return MyService(mock_db_session)

### New integration test

1. Create tests/integration/test_XXX_integration.py
2. Use fixtures: db_schema, tenant_id, async_session
3. Seed cross-service data with helpers if needed
4. Services raise exceptions on error — use `pytest.raises()` for error cases

    @pytest.mark.integration
    class TestMyFeature:
        async def test_something(self, db_schema, tenant_id, async_session):
            svc = MyService(async_session)
            _seed_customer(async_session, tenant_id)
            result = await svc.my_method(...)
            assert result.name == "expected"

        async def test_not_found(self, db_schema, tenant_id, async_session):
            svc = MyService(async_session)
            with pytest.raises(NotFoundException):
                await svc.get_entity(9999, tenant_id=tenant_id)

### New API router

    from fastapi import APIRouter, Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from db.connection import get_db
    from internal.middleware.fastapi_auth import AuthContext, require_auth

    router = APIRouter(prefix="/my", tags=["My"])

    @router.get("/")
    async def list_things(
        ctx: AuthContext = Depends(require_auth),
        session: AsyncSession = Depends(get_db),
    ):
        svc = MyService(session)
        items, total = await svc.list_things(tenant_id=ctx.tenant_id)
        return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total}}

    @router.get("/{entity_id}")
    async def get_thing(
        entity_id: int,
        ctx: AuthContext = Depends(require_auth),
        session: AsyncSession = Depends(get_db),
    ):
        svc = MyService(session)
        entity = await svc.get_thing(entity_id, tenant_id=ctx.tenant_id)
        return {"success": True, "data": entity.to_dict()}

---

## Resources

- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.x: https://docs.sqlalchemy.org/en/20/
- Pytest: https://docs.pytest.org/
- Project root: /home/node/.openclaw/workspace/dev-agent-system/
