# TaskService · Verify and test all 5 TaskService methods

| 元数据 | 值 |
|---|---|
| Issue | #454 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | TBD - 待验证：0451-taskservice设计与实现.md（对应实现板块尚未创建）, TBD - 待验证：0453-task-orm-model-and-migration.md（对应迁移板块尚未创建） |
| 启用后赋能 | TBD - 待验证：关联板块路径（尚未规划） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #454 is a verification and testing gate for the TaskService subsystem. Before this work, the 5 core TaskService methods (create_task, get_task, update_task, complete_task, list_tasks) exist in an unverified state — their correctness against the ORM model, multi-tenancy isolation, and error handling have not been exercised in unit or integration tests. Gaps in test coverage leave the door open for regressions as future work builds on the service layer.

### 1.2 做完后

- **用户视角**：No user-visible changes — this is a pure quality-assurance gate.
- **开发者视角**：Every TaskService method has passing unit tests (mock DB) and integration tests (real PostgreSQL). Code linting passes clean. The service layer is confirmed to handle NotFoundException, ValidationException, and multi-tenant row isolation correctly.

### 1.3 不做什么（剔除）

- [ ] Do not implement new TaskService methods beyond the 5 listed (create_task, get_task, update_task, complete_task, list_tasks)
- [ ] Do not add new ORM fields to the Task model — that belongs to #451 / #453
- [ ] Do not modify the CustomerService or OpportunityService to add task-awareness

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_task_service.py -v` → ≥ 5 passed (one per method)
- `PYTHONPATH=src pytest tests/integration/test_task_service_integration.py -v` → ≥ 5 passed (one per method)
- `ruff check src/services/task_service.py src/api/routers/task_router.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/task_service.py` L?-L? — TaskService class with 5 methods (create_task, get_task, update_task, complete_task, list_tasks)

TBD - 待验证：`src/api/routers/task_router.py` L?-L? — FastAPI router wiring TaskService methods to endpoints

TBD - 待验证：`src/db/models/task.py` (or `task_model.py`) L?-L? — Task ORM model with statuses PENDING, IN_PROGRESS, COMPLETED, CANCELLED; foreign keys to customer and opportunity

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/test_task_service.py` — add missing unit test cases
  - `tests/integration/test_task_service_integration.py` — add missing integration test cases
- 要建：
  - `tests/unit/test_task_service.py` — if file does not yet exist, create it
  - `tests/integration/test_task_service_integration.py` — if file does not yet exist, create it

### 2.3 缺什么

- [ ] Unit tests for create_task: success path + ValidationException on invalid status transition
- [ ] Unit tests for get_task: success path + NotFoundException on missing task
- [ ] Unit tests for update_task: success path + NotFoundException
- [ ] Unit tests for complete_task: success path + NotFoundException + forbidden on non-PENDING/CANCELLED transition
- [ ] Unit tests for list_tasks: pagination correctness + tenant isolation (wrong tenant returns empty)
- [ ] Integration tests for all 5 methods against real PostgreSQL
- [ ] Multi-tenant isolation verified in list_tasks (tasks from other tenants must not be returned)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_task_service.py` | Unit tests for all 5 TaskService methods using mock DB |
| `tests/integration/test_task_service_integration.py` | Integration tests for all 5 TaskService methods against real PostgreSQL |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/test_task_service.py` | Add any missing test cases if file already exists |
| `tests/integration/test_task_service_integration.py` | Add any missing test cases if file already exists |

### 3.3 新增能力

- **Unit tests**：`test_create_task`, `test_get_task`, `test_update_task`, `test_complete_task`, `test_list_tasks` — all in `tests/unit/test_task_service.py`
- **Integration tests**：`test_create_task_integration`, `test_get_task_integration`, `test_update_task_integration`, `test_complete_task_integration`, `test_list_tasks_integration` — all in `tests/integration/test_task_service_integration.py`
- **Linting**：Both files pass `ruff check` with 0 errors

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Mock session via `make_mock_session` helpers** rather than pytest-asyncio + real DB in unit tests — keeps unit tests fast (<5 s) and avoids shared state between test cases
- **Integration tests use `db_schema` fixture** (auto create/drop per function) — avoids cross-test contamination and TRUNCATE CASCADE complexity

### 4.2 版本约束

<!-- 无新依赖引入 -->

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` — list_tasks and get_task must filter by tenant; a task belonging to tenant A must not be visible to tenant B
- Service returns ORM objects, never calls `.to_dict()` — serialization belongs to the router
- Service raises `AppException` subclasses on errors — unit test mock handlers must return the same exceptions as the real service
- Task status transitions: only PENDING → IN_PROGRESS → COMPLETED and PENDING → CANCELLED are valid; test the invalid transition raises `ValidationException`

### 4.4 已知坑

1. **Mock session handlers returning `None` for scalar_one_or_none** — if the mock handler returns `None` for a row that should exist, tests will pass incorrectly. The `MockRow` / `MockResult` helpers must be set up to return a real `TaskModel` instance when the query is for an existing entity. → Fix: ensure each handler `select` path is covered with an explicit fixture that populates the `MockState`.
2. **Task model column named `metadata`** — if the Task ORM model uses `metadata` as a column name, SQLAlchemy `Base.metadata` (the `MetaData` object) will conflict at class definition time, crashing the import. → Fix: rename to `task_metadata`, `payload`, or `attrs`. Flag this in the test setup: if import fails with `AttributeError: 'Task' object has no attribute 'metadata'`, the ORM model needs fixing first.

---

## 5. 实现步骤（按顺序）

### Step 1: Audit existing TaskService implementation

Inspect `src/services/task_service.py` and `src/api/routers/task_router.py`. Confirm the 5 methods exist, note their signatures (return types, parameter names), and list any deviations from the service pattern (wrong session annotation, `.to_dict()` called in service, etc.).

操作：
- a) Read `src/services/task_service.py` — enumerate methods, their `tenant_id` handling, and which exceptions they raise
- b) Read `src/db/models/task.py` (or task_model.py) — note the ORM model fields and status enum values
- c) Read `src/api/routers/task_router.py` — confirm router wires each method to a route and uses `Depends(get_db)` (not `async with get_db()`)

**完成判定**：`ruff check src/services/task_service.py src/api/routers/task_router.py` → 0 errors

### Step 2: Audit existing test files

Inspect `tests/unit/test_task_service.py` and `tests/integration/test_task_service_integration.py` if they exist.

操作：
- a) For each of the 5 methods, determine whether a unit test case already exists
- b) For each existing test, check whether it covers: success path, error path (NotFoundException / ValidationException), and multi-tenant isolation
- c) Build a gap table: method → unit test status → integration test status

**完成判定**：Gap table produced; gaps listed in §2.3 are confirmed

### Step 3: Write missing unit tests in tests/unit/test_task_service.py

操作：
- a) Create `tests/unit/test_task_service.py` if it does not exist; follow the `tests/unit/conftest.py` pattern for `mock_db_session` fixture
- b) For each missing unit test, add a test case using `make_mock_session` with the task-related SQL handlers

示例代码（如有）：

```python
import pytest
from tests.unit.conftest import make_mock_session, MockState

# Task statuses
PENDING = "PENDING"
IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_task_handler(state)])

@pytest.fixture
def task_service(mock_db_session):
    from services.task_service import TaskService
    return TaskService(mock_db_session)

async def test_create_task_success(task_service, tenant_id):
    result = await task_service.create_task(
        title="Follow up",
        status=PENDING,
        customer_id=1,
        tenant_id=tenant_id,
    )
    assert result.title == "Follow up"
    assert result.status == PENDING
    assert result.tenant_id == tenant_id

async def test_get_task_not_found(task_service, tenant_id):
    with pytest.raises(NotFoundException):
        await task_service.get_task(task_id=9999, tenant_id=tenant_id)

async def test_list_tasks_tenant_isolation(task_service, tenant_id):
    other_tenant_id = tenant_id + 1
    await task_service.create_task(title="Other tenant", status=PENDING,
                                   customer_id=1, tenant_id=other_tenant_id)
    result = await task_service.list_tasks(tenant_id=tenant_id, page=1, page_size=20)
    titles = [t.title for t in result]
    assert "Other tenant" not in titles
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_task_service.py -v` → 5 passed

### Step 4: Write missing integration tests in tests/integration/test_task_service_integration.py

操作：
- a) Create `tests/integration/test_task_service_integration.py` using fixtures `db_schema`, `tenant_id`, `async_session`
- b) Seed a customer and/or opportunity before each test using `_seed_customer` / `_seed_opportunity` helpers
- c) Test all 5 methods against the real database; include a tenant-isolation assertion in list_tasks

示例代码（如有）：

```python
import pytest
from services.task_service import TaskService
from tests.integration.conftest import _seed_customer

@pytest.mark.integration
class TestTaskServiceIntegration:
    async def test_create_task(self, db_schema, tenant_id, async_session):
        _seed_customer(async_session, tenant_id)
        svc = TaskService(async_session)
        task = await svc.create_task(
            title="Demo task",
            status="PENDING",
            customer_id=1,
            tenant_id=tenant_id,
        )
        assert task.id is not None
        assert task.tenant_id == tenant_id

    async def test_list_tasks_returns_only_own_tenant(
        self, db_schema, tenant_id, async_session
    ):
        _seed_customer(async_session, tenant_id)
        svc = TaskService(async_session)
        await svc.create_task(title="Own", status="PENDING",
                              customer_id=1, tenant_id=tenant_id)
        # create a second tenant session and insert a task there
        other_tenant = tenant_id + 1
        _seed_customer(async_session, other_tenant)
        # use a second service instance scoped to the other tenant
        tasks_own = await svc.list_tasks(tenant_id=tenant_id, page=1, page_size=20)
        assert all(t.tenant_id == tenant_id for t in tasks_own)
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_task_service_integration.py -v` → 5 passed

### Step 5: Run full lint and type check

操作：
- a) `ruff check src/services/task_service.py src/api/routers/task_router.py tests/unit/test_task_service.py tests/integration/test_task_service_integration.py`
- b) Fix any reported issues

**完成判定**：`ruff check src/services/task_service.py src/api/routers/task_router.py tests/unit/test_task_service.py tests/integration/test_task_service_integration.py` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/services/task_service.py src/api/routers/task_router.py tests/unit/test_task_service.py tests/integration/test_task_service_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_task_service.py -v` → ≥ 5 passed (create_task, get_task, update_task, complete_task, list_tasks)
- [ ] `PYTHONPATH=src pytest tests/integration/test_task_service_integration.py -v` → ≥ 5 passed (one per method)
- [ ] Unit tests for get_task cover NotFoundException for missing task
- [ ] Unit tests for list_tasks include a tenant-isolation assertion (tasks from other tenant are not returned)
- [ ] Integration tests include a tenant-isolation assertion in list_tasks

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Task ORM model import fails due to `metadata` column name collision with `Base.metadata` | 中 | 高 | Revert to #453 and fix the ORM model column name before re-running tests |
| Integration tests against real DB fail due to foreign-key constraint (task references non-existent customer/opportunity) | 中 | 中 | Seed both customer and opportunity in each integration test fixture; do not assume pre-existing rows |
| Unit test mock handlers return stale/empty state across tests | 低 | 高 | Each unit test gets a fresh `MockState` via its own `mock_db_session` fixture; no shared `autouse` fixture |
| Tests pass but service is still wrong (false confidence from mock) | 低 | 中 | Integration tests on real DB are the safety net; do not skip them |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_task_service.py tests/integration/test_task_service_integration.py
git commit -m "test(task_service): add unit + integration tests for all 5 TaskService methods"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test: verify and test TaskService #454" --body "Closes #454"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — pattern for unit test fixture setup and mock session usage
- 同类参考实现：TBD - 待验证：tests/integration/test_customer_service_integration.py（对应文件尚未创建，可参考 tests/integration/ 目录下的其他集成测试文件）
- 父 issue / 关联：#451, #453
