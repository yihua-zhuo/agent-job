# AgentTaskService · Implement CRUD service with create/get/list methods

| 元数据 | 值 |
|---|---|
| Issue | #621 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [0620-implement-agenttaskmodel-and-orm](../0620-implement-agenttaskmodel-and-orm.md) |
| 启用后赋能 | [板块名](../板块名.md), ... |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #620 will define the `AgentTaskModel` ORM model. With that model in place, the `AgentTaskService` is the next foundational layer — it encapsulates all DB access for the `agent_tasks` table behind a single, testable service class. Without it, every router that needs task data must construct raw SQL or use the session directly, scattering multi-tenancy enforcement and exception handling across the API layer.

### 1.2 做完后

- **用户视角**：无用户可见变化 — this is a pure backend service layer.
- **开发者视角**：Callers can use `AgentTaskService(session)` with three methods: `create_task`, `get_task`, and `list_tasks`. The session is required (no default). Methods return `AgentTaskModel` ORM objects and raise `AppException` subclasses on error.

### 1.3 不做什么（剔除）

- [ ] No API router endpoints — those belong in a separate board (e.g. the router board that depends on this service).
- [ ] No background task execution / queue dispatch logic — that belongs in a later board.
- [ ] No auth or permission checks — those are the router's responsibility; the service trusts the caller.

### 1.4 关键 KPI

- `PYTHONPATH=src ruff check src/services/agent_task_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v` → all tests passed
- `alembic upgrade head` → exit 0 (if migration is needed; depends on whether #620's model already has one)

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/` 中是否已有任何 `agent_task` 相关文件（#620 尚未合并时无法确认）。若 #620 已合并，应存在 `src/db/models/agent_task.py` 定义 `AgentTaskModel`，参考同目录下的 `customer.py` 或 `pipeline.py` 的结构。

同类参考实现（确认存在的服务）：
[`src/services/customer_service.py`](../../../src/services/customer_service.py) — 标准 service 模式：`__init__(self, session: AsyncSession)` + raise `NotFoundException` / `ValidationException`

### 2.2 涉及文件清单

- 要改：
  - TBD — 若 #620 已合并并导出了 `AgentTaskModel`，可能需要更新 `__init__.py` 导出
- 要建：
  - `src/services/agent_task_service.py` — CRUD service（核心交付物）
  - `tests/unit/test_agent_task_service.py` — 单元测试
  - `alembic/versions/<id>_create_agent_tasks_table.py` — 迁移（若 #620 未包含迁移，或遗漏了索引）

### 2.3 缺什么

- [ ] `AgentTaskService` class with `create_task`, `get_task`, `list_tasks` methods
- [ ] Unit tests covering happy path and error cases for each method
- [ ] Multi-tenancy enforcement (all queries filter by `tenant_id`)
- [ ] Proper exception raising (`NotFoundException` when task not found, `ValidationException` on bad input)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/agent_task_service.py` | AgentTaskService: create_task / get_task / list_tasks |
| `tests/unit/test_agent_task_service.py` | Unit tests for AgentTaskService |
| `alembic/versions/<id>_create_agent_tasks_table.py` | 创建 agent_tasks 表（含 tenant_id 索引），如 #620 尚未包含 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/__init__.py` | 新增 `AgentTaskService` 导出（如当前无导出则新增） |
| `tests/unit/conftest.py` | 新增 `make_agent_task_handler(state)` — 测试用 mock handler（参考 `make_customer_handler` 的模式） |

### 3.3 新增能力

- **Service class**：`AgentTaskService(session: AsyncSession)` — session is required, no default
- **Service method**：`AgentTaskService.create_task(description: str, tenant_id: int) -> AgentTaskModel`
- **Service method**：`AgentTaskService.get_task(task_id: int, tenant_id: int) -> AgentTaskModel` — raises `NotFoundException` if not found
- **Service method**：`AgentTaskService.list_tasks(tenant_id: int, status: str | None, date_from: datetime | None, date_to: datetime | None, page: int, page_size: int) -> tuple[list[AgentTaskModel], int]`
- **Exceptions raised**：`NotFoundException`（get_task, task missing）, `ValidationException`（create_task, empty description）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Follow existing service pattern** over inventing a new one: constructor takes `session: AsyncSession` (no default), methods raise `AppException` subclasses, return ORM objects, never dicts. This matches `CustomerService` and all other services in the repo.
- **Pagination for list_tasks**: use `(items, total)` return tuple — consistent with other list methods in the codebase.
- **Optional filters on list_tasks**: `status`, `date_from`, `date_to` are keyword arguments with `None` defaults; the SQL only adds `WHERE` clauses for non-None values.

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- Multi-tenancy：every SQL query must include `WHERE tenant_id = :tenant_id`.
- Service returns ORM objects; router is responsible for `.to_dict()` serialization. Do **not** call `.to_dict()` inside the service.
- Service raises `AppException` subclasses — `NotFoundException`, `ValidationException`. Do **not** return `ApiResponse.error()`.
- Session is injected by the caller (router); do **not** use `async with get_db() as session:` inside the service.
- `AgentTaskModel` must be imported from `db.models.agent_task` (not `src.db.models...`), consistent with `PYTHONPATH=src` convention.

### 4.4 已知坑

1. **Alembic autogen emits `sa.JSON()` instead of `sa.JSONB()`** → If the migration is generated, manually change any JSON column to `JSONB()` for PostgreSQL performance. Check all datetime columns have `timezone=True`.
2. **Test mock handler must be stateful** → Follow `make_customer_handler(state)` pattern from `tests/unit/conftest.py`; use `MockState()` for auto-increment IDs. Do not use module-level state.

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 AgentTaskService 类骨架

在 `src/services/agent_task_service.py` 创建文件，按以下结构：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime

from db.models.agent_task import AgentTaskModel  # 确认 #620 导出路径
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class AgentTaskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, description: str, tenant_id: int) -> AgentTaskModel:
        if not description or not description.strip():
            raise ValidationException("description cannot be empty")
        task = AgentTaskModel(
            description=description.strip(),
            tenant_id=tenant_id,
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
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
        tasks = list(result.scalars().all())
        return tasks, total
```

在 `src/services/__init__.py` 添加导出（若文件中尚无导出，新增一行）：
```python
from src.services.agent_task_service import AgentTaskService
```

**完成判定**：`PYTHONPATH=src ruff check src/services/agent_task_service.py` → 0 errors

---

### Step 2: 在 tests/unit/conftest.py 添加 make_agent_task_handler

参考 `make_customer_handler` 的实现模式，添加：

```python
def make_agent_task_handler(state: MockState):
    """Stateful handler for agent_tasks table operations in unit tests."""
    def handle(method: str, stmt, state):
        table = state.agent_tasks or []
        if method == "execute" and "INSERT" in str(stmt):
            # simulate auto-increment id
            new_id = len(table) + 1
            task = type('obj', (object,), {
                'id': new_id,
                'tenant_id': stmt._values_by_column.get(...) or 0,
                'description': ...,
                'status': 'pending',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            })()
            table.append(task)
            state.agent_tasks = table
            return MockResult([MockRow(task)])
        # ... handle SELECT / COUNT similarly
    return handle
```

（完整实现参照 `make_customer_handler` 的分支逻辑，覆盖 INSERT / SELECT by id / SELECT list / COUNT）

**完成判定**：`PYTHONPATH=src ruff check tests/unit/conftest.py` → 0 errors

---

### Step 3: 编写 AgentTaskService 单元测试

创建 `tests/unit/test_agent_task_service.py`，测试用例：

```python
import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from tests.unit.conftest import make_mock_session, make_agent_task_handler, MockState, MockRow, MockResult
from src.services.agent_task_service import AgentTaskService
from pkg.errors.app_exceptions import NotFoundException, ValidationException


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_agent_task_handler(state)])


@pytest.fixture
def service(mock_db_session):
    return AgentTaskService(mock_db_session)


class TestCreateTask:
    async def test_creates_task_with_tenant_id(self, service, mock_db_session):
        task = await service.create_task("Process inbound email", tenant_id=42)
        assert task.tenant_id == 42
        assert task.description == "Process inbound email"
        assert task.status == "pending"

    async def test_raises_validation_for_empty_description(self, service):
        with pytest.raises(ValidationException):
            await service.create_task("", tenant_id=1)

    async def test_raises_validation_for_whitespace_only(self, service):
        with pytest.raises(ValidationException):
            await service.create_task("   ", tenant_id=1)


class TestGetTask:
    async def test_returns_task(self, service):
        created = await service.create_task("Test task", tenant_id=1)
        task = await service.get_task(created.id, tenant_id=1)
        assert task.id == created.id

    async def test_raises_not_found_for_missing_task(self, service):
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
        task1 = await service.create_task("Task A", tenant_id=1)
        # update status to completed via direct attribute (mock allows it)
        tasks, total = await service.list_tasks(tenant_id=1, status="pending", page=1, page_size=20)
        # assert filtered correctly

    async def test_filters_by_date_range(self, service):
        tasks, total = await service.list_tasks(
            tenant_id=1,
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 12, 31),
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
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v` → all passed

---

### Step 4: 添加 Alembic 迁移（如 #620 未包含）

若 #620 已合并且 `AgentTaskModel` 存在但无迁移：

```bash
# 启动干净数据库
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"

cd /Users/yihuazhuo/Desktop/git/github/agent-job  # 或 repo 根目录

# 生成迁移
alembic revision --autogenerate -m "create agent_tasks table"
```

编辑生成的迁移文件：
- 确认 `tenant_id` 列有 `index=True`
- 若有 JSON 列，手动改 `sa.JSON()` → `sa.JSONB()`
- 若有 `DateTime`，加 `timezone=True`

```bash
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/services/agent_task_service.py` → 0 errors
- [ ] `PYTHONPATH=src ruff check tests/unit/test_agent_task_service.py tests/unit/conftest.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v` → all passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（若迁移步骤执行）
- [ ] `PYTHONPATH=src mypy src/services/agent_task_service.py` → 0 errors（如 mypy 配置存在）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #620 尚未合并没有 `AgentTaskModel` 定义，导致 import 失败 | 中 | 高 | 等待 #620 合并后再开始本板块；依赖链已在元数据声明 |
| Alembic 迁移与 #620 的 model 定义冲突（重复创建表） | 低 | 中 | 删除本板块迁移文件；由 #620 的迁移覆盖 |
| conftest.py 的 mock handler 实现不完整，测试假阳性 | 低 | 中 | 对照 `make_customer_handler` 逐分支补全；不影响生产代码 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/agent_task_service.py
git add src/services/__init__.py  # 若修改
git add tests/unit/test_agent_task_service.py
git add tests/unit/conftest.py  # 若修改
git add alembic/versions/  # 若生成迁移
git commit -m "feat(automation): implement AgentTaskService with CRUD methods"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): AgentTaskService CRUD (#621)" --body "Closes #621"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py)
- ORM model（父 issue）：#620
- 父 issue：#42
- 依赖：#620

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
