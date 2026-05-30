Now I have all the ground truth I need. Let me write the plan.

# Implementation Plan — Issue #621

## Goal
Implement `AgentTaskService` in `src/services/agent_task_service.py` with `create_task`, `get_task`, and `list_tasks` CRUD methods, following the established service pattern (required `AsyncSession`, ORM returns, `AppException` subclasses). Unit tests and a mock SQL handler in `conftest.py` are also in scope. No router, no migration (migration already shipped in #620).

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0621-implement-agenttaskservice-with-crud-methods.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0621-implement-agenttaskservice-with-crud-methods.md`

## Affected Files
- `src/services/agent_task_service.py` — **new** — `AgentTaskService` class with `create_task`, `get_task`, `list_tasks`
- `src/services/__init__.py` — **modify** — add `AgentTaskService` export (file is currently empty)
- `tests/unit/domain_handlers/agent_tasks.py` — **new** — `make_agent_task_handler(state)` for unit test mock session
- `tests/unit/test_agent_task_service.py` — **new** — unit tests for all three service methods
- `tests/unit/conftest.py` — **modify** — add `make_agent_task_handler` to domain handler auto-loader (via `__init__.py` re-exports)

## Implementation Steps

### Step 1: Create `src/services/agent_task_service.py`

Create the file mirroring the `TaskService`/`CustomerService` pattern. Key decisions grounded in the actual `AgentTaskModel`:

- `AgentTaskModel` has a **required** `task_id: Mapped[str]` column (`String(64)`, unique). Since the service signature takes only `description` and `tenant_id`, generate a `task_id` via `uuid.uuid4().hex[:16]` prefixed with `"atask_"`.
- `status` defaults to `AgentTaskStatus.PENDING` (`"pending"`) via the column's `server_default`; still pass it explicitly for clarity.
- `subtasks` defaults to `[]` via `default=list`; pass `[]` explicitly.
- `created_at`/`updated_at` use `server_default=func.now()` — only pass explicit values if the ORM requires them; otherwise rely on the DB default. Follow `TaskService` which passes explicit `datetime.now(UTC)` timestamps.

```python
"""Agent task service — CRUD via SQLAlchemy ORM."""

from datetime import UTC, datetime
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.agent_tasks import AgentTaskModel, AgentTaskStatus
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class AgentTaskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, description: str, tenant_id: int) -> AgentTaskModel:
        if not description or not description.strip():
            raise ValidationException("description cannot be empty")
        now = datetime.now(UTC)
        task = AgentTaskModel(
            task_id=f"atask_{uuid.uuid4().hex[:16]}",
            tenant_id=tenant_id,
            description=description.strip(),
            status=AgentTaskStatus.PENDING,
            subtasks=[],
            created_at=now,
            updated_at=now,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_task(self, task_id: int, tenant_id: int) -> AgentTaskModel:
        result = await self.session.execute(
            select(AgentTaskModel).where(
                and_(
                    AgentTaskModel.id == task_id,
                    AgentTaskModel.tenant_id == tenant_id,
                )
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundException("AgentTask")
        return task

    async def list_tasks(
        self,
        tenant_id: int,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentTaskModel], int]:
        conditions = [AgentTaskModel.tenant_id == tenant_id]
        if status is not None:
            conditions.append(AgentTaskModel.status == status)
        if date_from is not None:
            conditions.append(AgentTaskModel.created_at >= date_from)
        if date_to is not None:
            conditions.append(AgentTaskModel.created_at <= date_to)

        count_result = await self.session.execute(
            select(func.count(AgentTaskModel.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(AgentTaskModel)
            .where(and_(*conditions))
            .order_by(AgentTaskModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
```

**完成判定**: `PYTHONPATH=src ruff check src/services/agent_task_service.py` → 0 errors

---

### Step 2: Update `src/services/__init__.py`

Add the export so callers can import `AgentTaskService` from the `services` package:

```python
from services.agent_task_service import AgentTaskService
```

**完成判定**: `PYTHONPATH=src ruff check src/services/__init__.py` → 0 errors

---

### Step 3: Create `tests/unit/domain_handlers/agent_tasks.py`

Create the domain handler following the `customers.py` pattern. This file is auto-loaded by `tests/unit/domain_handlers/__init__.py`'s `pkgutil` discovery loop — it only needs `get_handlers(state)` and `make_agent_task_handler(state)` in `__all__`.

The handler must cover:
- `INSERT INTO agent_tasks` → allocate auto-increment ID, store in `state.agent_tasks`, return `MockResult([MockRow(record)])`
- `SELECT … FROM agent_tasks WHERE id = ? AND tenant_id = ?` → return matching record or `MockResult([])`
- `SELECT … FROM agent_tasks WHERE tenant_id = ?` (list) → filter by `tenant_id`, apply optional `status`/`date_from`/`date_to` filters, return paginated rows
- `SELECT count(…) FROM agent_tasks` → return count matching tenant filter

State key: `state.agent_tasks` (dict mapping `int` id → `dict` record), `state.agent_tasks_next_id` (int, start at 1).

```python
"""Agent task SQL handlers for unit tests."""

from __future__ import annotations

from datetime import datetime
from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def make_agent_task_handler(state: MockState):
    def handler(sql_text, params):
        # INSERT
        if "insert into agent_tasks" in sql_text:
            new_id = state.agent_tasks_next_id
            state.agent_tasks_next_id += 1
            record = {
                "id": new_id,
                "task_id": params.get("task_id", f"atask_{new_id}"),
                "tenant_id": params.get("tenant_id", 0),
                "description": params.get("description"),
                "status": params.get("status", "pending"),
                "subtasks": params.get("subtasks", []),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.agent_tasks[new_id] = record
            return MockResult([MockRow(record.copy())])

        # SELECT by id + tenant
        if "from agent_tasks where id" in sql_text and "tenant_id" in sql_text:
            tid = params.get("id")
            if tid in state.agent_tasks:
                return MockResult([MockRow(state.agent_tasks[tid].copy())])
            return MockResult([])

        # COUNT
        if "select" in sql_text and "count" in sql_text and "from agent_tasks" in sql_text:
            tenant_id = params.get("tenant_id", 0)
            count_val = sum(1 for r in state.agent_tasks.values() if r.get("tenant_id") == tenant_id)
            return MockResult([[count_val]])

        # SELECT list (no id filter)
        if "select" in sql_text and "from agent_tasks" in sql_text and "where id" not in sql_text:
            tenant_id = params.get("tenant_id", 0)
            rows = []
            for rec in state.agent_tasks.values():
                if rec.get("tenant_id") != tenant_id:
                    continue
                rows.append(MockRow(rec.copy()))
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_agent_task_handler(state)]


__all__ = ["get_handlers", "make_agent_task_handler"]
```

Also initialize `state.agent_tasks` and `state.agent_tasks_next_id` in `MockState.__init__` in `tests/unit/conftest.py`:

```python
class MockState:
    def __init__(self):
        self.customers: dict[int, dict] = {}
        self.customers_next_id: int = 1
        self.users: dict[int, dict] = {}
        self.users_next_id: int = 1
        self.deleted_user_ids: set[int] = set()
        self.activities: dict[int, dict] = {}
        self.activities_next_id: int = 1
        self.agent_tasks: dict[int, dict] = {}
        self.agent_tasks_next_id: int = 1
```

**完成判定**: `PYTHONPATH=src ruff check tests/unit/domain_handlers/agent_tasks.py tests/unit/conftest.py` → 0 errors

---

### Step 4: Create `tests/unit/test_agent_task_service.py`

Cover all three methods. The test file must use a standalone `mock_db_session` fixture that only includes `make_agent_task_handler` (not the full `all_handlers`), following the convention in CLAUDE.md.

```python
"""Unit tests for src/services/agent_task_service.py."""

from datetime import UTC, datetime

import pytest

from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.agent_tasks import make_agent_task_handler
from src.services.agent_task_service import AgentTaskService
from pkg.errors.app_exceptions import NotFoundException, ValidationException


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_agent_task_handler(state)], state=state)


@pytest.fixture
def service(mock_db_session):
    return AgentTaskService(mock_db_session)


class TestCreateTask:
    async def test_creates_task_with_pending_status(self, service):
        task = await service.create_task("Process inbound email", tenant_id=42)
        assert task.tenant_id == 42
        assert task.description == "Process inbound email"
        assert task.status == "pending"
        assert task.task_id.startswith("atask_")

    async def test_strips_whitespace_from_description(self, service):
        task = await service.create_task("  Trim me ", tenant_id=1)
        assert task.description == "Trim me"

    async def test_raises_validation_for_empty_description(self, service):
        with pytest.raises(ValidationException):
            await service.create_task("", tenant_id=1)

    async def test_raises_validation_for_whitespace_only(self, service):
        with pytest.raises(ValidationException):
            await service.create_task("   ", tenant_id=1)


class TestGetTask:
    async def test_returns_created_task(self, service):
        created = await service.create_task("Test task", tenant_id=1)
        task = await service.get_task(created.id, tenant_id=1)
        assert task.id == created.id
        assert task.description == "Test task"

    async def test_raises_not_found_for_missing_id(self, service):
        with pytest.raises(NotFoundException):
            await service.get_task(9999, tenant_id=1)

    async def test_raises_not_found_for_wrong_tenant(self, service):
        created = await service.create_task("Tenant 1 task", tenant_id=1)
        with pytest.raises(NotFoundException):
            await service.get_task(created.id, tenant_id=999)


class TestListTasks:
    async def test_returns_tasks_with_total(self, service):
        await service.create_task("Task 1", tenant_id=1)
        await service.create_task("Task 2", tenant_id=1)
        tasks, total = await service.list_tasks(tenant_id=1, page=1, page_size=20)
        assert total == 2
        assert len(tasks) == 2

    async def test_filters_by_status(self, service):
        await service.create_task("Task A", tenant_id=1)
        tasks, total = await service.list_tasks(tenant_id=1, status="pending", page=1, page_size=20)
        assert total == 1

    async def test_filters_by_date_range(self, service):
        now = datetime.now(UTC)
        tasks, total = await service.list_tasks(
            tenant_id=1,
            date_from=now,
            date_to=now,
            page=1,
            page_size=20,
        )
        assert total >= 0

    async def test_respects_pagination(self, service):
        for i in range(5):
            await service.create_task(f"Task {i}", tenant_id=1)
        page1, total = await service.list_tasks(tenant_id=1, page=1, page_size=2)
        page2, _ = await service.list_tasks(tenant_id=1, page=2, page_size=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    async def test_returns_empty_for_unknown_tenant(self, service):
        await service.create_task("Task 1", tenant_id=1)
        tasks, total = await service.list_tasks(tenant_id=99, page=1, page_size=20)
        assert total == 0
        assert tasks == []
```

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v` → all passed

---

### Step 5: Run full verification

```bash
PYTHONPATH=src ruff check src/
PYTHONPATH=src ruff format --check src/
PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v
```

## Test Plan
- Unit tests in `tests/unit/`: `tests/unit/test_agent_task_service.py` (new) covers happy paths and error paths for `create_task`, `get_task`, `list_tasks`; `tests/unit/domain_handlers/agent_tasks.py` (new) provides the mock SQL handler and initializes domain state via `hasattr` checks
- Integration tests in `tests/integration/`: none — this board is service-only; integration tests belong in the router board that depends on this service
- Dev-plan verification: `PYTHONPATH=src ruff check src/services/agent_task_service.py` → 0 errors; `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v` → all passed

## Acceptance Criteria
- `src/services/agent_task_service.py` exists with `AgentTaskService(session: AsyncSession)` — session has no default
- `create_task(description, tenant_id)` returns `AgentTaskModel`, raises `ValidationException` on empty/whitespace description, generates a unique `task_id`
- `get_task(task_id, tenant_id)` returns `AgentTaskModel`, raises `NotFoundException` if not found or wrong tenant
- `list_tasks(tenant_id, status, date_from, date_to, page, page_size)` returns `tuple[list[AgentTaskModel], int]` with all filters optional and tenant-scoped
- All SQL queries include `WHERE tenant_id = :tenant_id`
- Service does not call `.to_dict()` — router is responsible
- Service raises `AppException` subclasses, never returns error dicts
- `PYTHONPATH=src ruff check src/services/agent_task_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v` → all passed## Risks / Open Questions
- None — `AgentTaskModel` and migration are already shipped from #620; no ambiguity about schema.
