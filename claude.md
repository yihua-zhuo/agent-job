# dev-agent-system — Claude Code Reference

Multi-tenant CRM system (FastAPI + SQLAlchemy 2.x async + PostgreSQL).

**Branch:** `fastapi-migration` → `master`  
**CI:** GitHub Actions (Unit Tests + Integration Tests + Flake8/Lint)

---

## Project Structure

```
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
│   │   ├── conftest.py       # MockSession, _execute_side_effect
│   │   └── test_*.py
│   └── integration/          # Real PostgreSQL
│       └── conftest.py       # Real DB fixtures
├── pyproject.toml
├── pytest.ini
└── .env
```

---

## Key Commands

```bash
# Run unit tests (no DB needed)
pytest tests/unit/ -v

# Run integration tests (needs DATABASE_URL)
DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/ -v

# Run all tests except integration
pytest tests/ -m "not integration" -v

# Lint (E9, F63, F7, F82 only — what pre-push hook uses)
flake8 src/ --select=E9,F63,F7,F82

# Type check
mypy src/

# Format
black src/

# Full check pipeline
black src/ && flake8 src/ && mypy src/

# Set PYTHONPATH before everything
export PYTHONPATH=src
```

---

## Conventions

### Pydantic Schemas & ApiResponse

All service methods return `ApiResponse[T]`:

```python
from models.response import ApiResponse, ResponseStatus

result = await customer_svc.create_customer(...)
if result.status == ResponseStatus.SUCCESS:
    data = result.data      # T type
else:
    message = result.message  # error string
```

### Service Pattern

- One service class per domain (e.g. `CustomerService`, `SalesService`)
- Constructor takes **required** `session: AsyncSession` — caller provides it
- All methods accept `tenant_id: int` and include it in every SQL `WHERE` clause

```python
class MyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_entity(self, data: dict, tenant_id: int) -> ApiResponse:
        self.session.execute(...)
        ...
```

### SQLAlchemy Async

- Use `asyncpg` driver: `postgresql+asyncpg://user:pass@host:5432/db`
- All DB ops are async (`async def`, `await`)
- Use `text()` for raw SQL when needed

### Multi-Tenancy

Every SQL query **must** filter by `tenant_id`:

```sql
WHERE tenant_id = :tenant_id
```

### Unit Test SQL Mocks

`conftest.py` uses `MockSession` + `_execute_side_effect` to simulate SQL:

| SQL pattern | Mock behavior |
|---|---|
| `INSERT ... VALUES` | Insert fixed rows |
| `SELECT ... FROM X WHERE id = Y` | Return fixed row |
| `SELECT ... FROM X` (no WHERE) | Return paginated data |
| `UPDATE ... RETURNING *` | Return updated row |
| `DELETE ... RETURNING *` | Return deleted row |

**Gotcha:** `RETURNING *` must be handled separately in `_execute_side_effect`. If a SQL mock fails, check if the pattern is covered there.

### Integration Test Fixtures

| Fixture | Purpose |
|---|---|
| `db_schema` | Auto-creates/drops all tables per function |
| `tenant_id` | Current tenant ID |
| `async_session` | Function-scoped session, shared across services in one test |

---

## Gotchas & Tips

1. **PYTHONPATH is required** — always `export PYTHONPATH=src` before running anything.
2. **DATABASE_URL must use `postgresql+asyncpg`** — the `asyncpg` driver, not `psycopg2`.
3. **Unit tests mock at SQL string level** — `_execute_side_effect` parses raw SQL strings; the mock must exactly match what the code generates (whitespace, clause order, etc.).
4. **No `RETURNING *` in unit mock?** → Test silently returns wrong data. Check `conftest.py` first.
5. **pre-push hook blocks on mypy** — use `git push --no-verify` as a temporary bypass, or fix the type error.
6. **Integration test TRUNCATE CASCADE** — schema fixture truncates all tables between tests; don't rely on data persisting within a test file.
7. **Cross-service seeds** — use `_seed_customer` / `_seed_user` helpers to set up dependencies (e.g. ticket needs a customer first).
8. **black + flake8 order** — run black first, then flake8. Black reformats; flake8 checks the formatted output.

---

## Adding New Features

### New unit test

1. Create/edit `tests/unit/test_XXX.py`
2. If new SQL pattern needed → edit `tests/unit/conftest.py`'s `_execute_side_effect`

### New integration test

1. Create `tests/integration/test_XXX_integration.py`
2. Use fixtures: `db_schema`, `tenant_id`, `async_session`
3. Seed cross-service data with helpers if needed

```python
@pytest.mark.integration
class TestMyFeature:
    async def test_something(self, db_schema, tenant_id, async_session):
        svc = MyService(async_session)
        result = await svc.my_method(...)
        assert result.status == ResponseStatus.SUCCESS
```

### New API router

```python
from fastapi import APIRouter, Depends
from dependencies import get_db, require_auth
from models.auth import AuthContext

router = APIRouter(prefix="/my", tags=["My"])

@router.get("/")
async def list_things(
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    svc = MyService(session)
    return await svc.list_things(tenant_id=ctx.tenant_id)

@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    svc = UserService(session)
    return await svc.update_user(user_id, body, tenant_id=ctx.tenant_id)
```

---

## Resources

- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.x: https://docs.sqlalchemy.org/en/20/
- Pytest: https://docs.pytest.org/
- Project root: `/home/node/.openclaw/workspace/dev-agent-system/`