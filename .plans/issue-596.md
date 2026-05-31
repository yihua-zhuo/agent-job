Now I have all the information needed. Let me write the implementation plan grounded in the actual codebase.

# Implementation Plan — Issue #596

## Goal

Add notification analytics tracking to the CRM: an `NotificationAnalytics` ORM model in `src/db/models/notification.py`, an `NotificationAnalyticsService` with `track_open` and `get_open_rate` methods, and a `PATCH /notifications/{id}/open` endpoint wired in `src/api/routers/notifications.py`, backed by unit tests.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0596-add-notification-analytics-tracking.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0596-add-notification-analytics-tracking.md`

## Affected Files

- `src/db/models/notification.py` — Add `NotificationAnalytics` ORM model class
- `src/services/notification_analytics_service.py` — New: `NotificationAnalyticsService` with `track_open` and `get_open_rate`
- `src/api/routers/notifications.py` — Add `PATCH /notifications/{notification_id}/open` endpoint
- `tests/unit/domain_handlers/notification.py` — Add `make_notification_analytics_handler` for mock DB
- `tests/unit/test_notification_analytics.py` — New: unit tests for `NotificationAnalyticsService`

## Implementation Steps

### Step 1: Add `NotificationAnalytics` ORM model

Add the class at the bottom of `src/db/models/notification.py` (after `NotificationModel`, which ends at line 104). Use `DateTime(timezone=True)`, `Mapped`, `mapped_column`, and inherit from `db.base.Base` — same pattern as `NotificationModel`.

```python
class NotificationAnalytics(Base):
    """Analytics record for a notification open/click event."""

    __tablename__ = "notification_analytics"
    __table_args__ = (
        Index("ix_notification_analytics_notification_tenant", "notification_id", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
```

Add required imports at the top of the file if not already present: `Index` to the existing `from sqlalchemy import ...` line.

**Completion check**: `ruff check src/db/models/notification.py` → 0 errors

---

### Step 2: Add domain handler for mock DB

In `tests/unit/domain_handlers/notification.py`, add `make_notification_analytics_handler(state)` and expose it via `get_handlers`. The handler manages `state._notification_analytics` dict keyed by `(notification_id, tenant_id)` (unique), handles `insert into notification_analytics` (upsert-on-notification+tenant), `select from notification_analytics where notification_id` (with `opened_at IS NOT NULL` filter for count), and `count(id)` from `notification_analytics where opened_at IS NOT NULL`.

Also add `make_notification_analytics_handler` to `__all__`.

**Completion check**: `ruff check tests/unit/domain_handlers/notification.py` → 0 errors

---

### Step 3: Create `NotificationAnalyticsService`

Create `src/services/notification_analytics_service.py` with:

- Constructor: `def __init__(self, session: AsyncSession)` — no default, typed `AsyncSession`
- `track_open(self, notification_id: int, tenant_id: int, channel: str = "email") -> NotificationAnalytics` — upsert semantics: `SELECT` by `(notification_id, tenant_id)`, update `opened_at` if found, otherwise `INSERT`. Calls `session.flush()` then returns the ORM object.
- `get_open_rate(self, notification_id: int, tenant_id: int) -> float` — `SELECT COUNT(id) FROM notification_analytics WHERE notification_id=:id AND tenant_id=:tid AND opened_at IS NOT NULL`. Returns `0.0` when count is 0, otherwise returns `float(count)`.

Both methods follow the multi-tenancy contract (always filter by `tenant_id`). Service raises `NotFoundException("Notification")` when the notification does not exist (SELECT returns nothing).

Imports from `db.models.notification import NotificationAnalytics`, `sqlalchemy.ext.asyncio.AsyncSession`, `sqlalchemy.select`, `sqlalchemy.func`, `datetime`/`timezone`, and `pkg.errors.app_exceptions.NotFoundException`.

**Completion check**: `ruff check src/services/notification_analytics_service.py` → 0 errors

---

### Step 4: Wire `PATCH /notifications/{notification_id}/open` in router

In `src/api/routers/notifications.py` (which already has `notifications_router = APIRouter(prefix="/api/v1", tags=["notifications"])`), add a new endpoint after the existing `mark_notification_read` endpoint (~line 259):

```python
from services.notification_analytics_service import NotificationAnalyticsService

@notifications_router.patch(
    "/notifications/{notification_id}/open",
    summary="Track a notification open event",
)
async def track_notification_open(
    notification_id: int = Path(..., ge=1, description="Notification ID"),
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Record that a notification was opened and return the open rate."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationAnalyticsService(session)
    analytics = await svc.track_open(notification_id, tenant_id=current_user.tenant_id)
    rate = await svc.get_open_rate(notification_id, tenant_id=current_user.tenant_id)
    return {
        "success": True,
        "data": {
            "notification_id": notification_id,
            "opened_at": analytics.opened_at.isoformat() if analytics.opened_at else None,
            "open_rate": rate,
        },
    }
```

Add the `Path` import if not already imported (it is — line 7). Add `Depends` import (already there).

**Completion check**: `ruff check src/api/routers/notifications.py` → 0 errors

---

### Step 5: Generate Alembic migration

Run autogenerate against a clean `alembic_dev` database (per CLAUDE.md instructions):

```bash
# 1. Spin up test DB
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 2. Bring to head
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head

# 3. Autogenerate
alembic revision --autogenerate -m "create_notification_analytics"

# 4. Review and correct the migration file (fix JSON→JSONB, DateTime→TIMESTAMPTZ if needed)

# 5. Verify upgrade / downgrade / upgrade
alembic upgrade head && alembic downgrade -1 && alembic upgrade head

# 6. Drift check — second autogen must produce empty migration
alembic revision --autogenerate -m "drift_check"
# If up/down are both `pass`, delete the drift_check file
```

Note: `alembic/env.py` imports `db.models` (`import db.models  # noqa: F401`), which pulls in the full `db/models/` package. Since `notification.py` lives in that package and the new `NotificationAnalytics` is in it, the model is automatically registered in `Base.metadata` and visible to autogenerate.

**Completion check**: All three alembic commands exit 0; drift check produces empty migration (delete it).

---

### Step 6: Write unit tests

Create `tests/unit/test_notification_analytics.py` using `make_mock_session` from `conftest.py`. Add a `make_notification_analytics_handler` to the session's handler list. Test cases:

1. **`test_track_open_creates_record`** — `track_open` returns an `NotificationAnalytics` with `opened_at` set and `notification_id` / `tenant_id` matching inputs.
2. **`test_track_open_upsert`** — calling `track_open` twice for the same `(notification_id, tenant_id)` does not create two rows; second call updates `opened_at` (idempotent).
3. **`test_track_open_not_found`** — `track_open` with unknown `notification_id` raises `NotFoundException("Notification")`.
4. **`test_get_open_rate_no_records`** — `get_open_rate` returns `0.0` when no analytics exist.
5. **`test_get_open_rate_with_records`** — `get_open_rate` returns a positive `float` when at least one analytics row with `opened_at` exists.
6. **`test_cross_tenant_isolation`** — `track_open` for `tenant_id=1` does not affect `get_open_rate` for `tenant_id=2` (returns 0.0).

Fixture setup:
```python
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.notification import make_notification_analytics_handler

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_notification_analytics_handler(state)], state=state)

@pytest.fixture
def service(mock_db_session):
    return NotificationAnalyticsService(mock_db_session)
```

**Completion check**: `PYTHONPATH=src pytest tests/unit/test_notification_analytics.py -v` → ≥ 6 passed

---

### Step 7: Final lint + format

Run the full lint pipeline:

```bash
export PYTHONPATH=src
ruff check src/db/models/notification.py src/services/notification_analytics_service.py src/api/routers/notifications.py
ruff format --check src/db/models/notification.py src/services/notification_analytics_service.py src/api/routers/notifications.py
```

Fix any errors before considering the issue complete.

**Completion check**: both commands exit 0 with no output.

---

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_notification_analytics.py` (new) — covers `track_open` create, upsert, not-found, `get_open_rate` 0.0, `get_open_rate` positive, cross-tenant isolation.
- **Integration tests in `tests/integration/`**: none required per dev-plan scope.
- **Dev-plan verification**:
  - `ruff check src/db/models/notification.py src/services/notification_analytics_service.py src/api/routers/notifications.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_notification_analytics.py -v` → ≥ 6 passed
  - `ruff format --check src/db/models/notification.py src/services/notification_analytics_service.py src/api/routers/notifications.py` → 0 differences
  - `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 3× exit 0

## Acceptance Criteria

- `NotificationAnalytics` ORM model exists in `src/db/models/notification.py` with fields `id`, `notification_id`, `tenant_id`, `opened_at`, `clicked_at`, `channel`
- `NotificationAnalyticsService.track_open(notification_id, tenant_id)` returns an ORM object and follows upsert semantics
- `NotificationAnalyticsService.get_open_rate(notification_id, tenant_id)` returns `float`, returning `0.0` when no records exist
- `PATCH /api/v1/notifications/{notification_id}/open` endpoint exists in `src/api/routers/notifications.py` and calls both service methods, returning `{"success": true, "data": {"opened_at": "...", "open_rate": float}}`
- All SQL queries filter by `tenant_id` (multi-tenancy contract)
- Unit tests: ≥ 6 passed covering create, upsert, not-found, rate 0.0, rate positive, cross-tenant isolation
- `ruff check` + `ruff format --check` pass on all modified/new files
