# 自动化 · WorkflowService 定义 CRUD 与实例生命周期

| 元数据 | 值 |
|---|---|
| Issue | #652 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | TBD - 待验证：0651 工作流模型与枚举定义对应文件路径 |
| 启用后赋能 | TBD - 待验证：0686 自动化规则路由端点对应文件路径, TBD - 待验证：0687 规则执行引擎与触发调度对应文件路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM currently has no workflow execution layer. Issue #651 established the ORM models (`WorkflowDefinition`, `WorkflowStepDefinition`, `WorkflowInstance`, `WorkflowStepInstance`) and enums. Issue #652 implements the service layer that drives those models — the CRUD for definitions and the full lifecycle (start → advance → complete) for instances. Without this, downstream rule-execution and router work has no foundation to build on.

### 1.2 做完后

- **用户视角**：无用户可见 changes — this is a pure backend service layer.
- **开发者视角**：`WorkflowService` is available in `src/services/workflow_service.py`. Other services and routers can call `create_definition`, `get_definition`, `list_definitions`, `start_instance`, `get_instance`, `list_instances`. The `_advance_instance` helper is private and handles auto-step transitions internally.

### 1.3 不做什么（剔除）

- [ ] Timeouts or retry logic for instance execution — handled in a future subtask.
- [ ] Workflow execution triggers (event-driven, cron, webhook) — handled by #687.
- [ ] API router for workflow endpoints — handled by #686.
- [ ] Persistence of execution logs / audit trail beyond `WorkflowStepInstance` records.

### 1.4 关键 KPI

- `ruff check src/services/workflow_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 6 passed (≥ 1 per method + helper)
- `PYTHONPATH=src mypy src/services/workflow_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

Issue #651 produced the ORM models that this service depends on. The models are expected at:

[`src/db/models/workflow.py`](../../src/db/models/workflow.py) TBD — verify after #651 lands

Expected key models (verify from #651 output):
- `WorkflowDefinition` — id, tenant_id, name, description, version, status, steps (relation)
- `WorkflowStepDefinition` — id, workflow_definition_id, name, order, action_type, action_config
- `WorkflowInstance` — id, tenant_id, workflow_definition_id, status, current_step_id
- `WorkflowStepInstance` — id, tenant_id, workflow_instance_id, step_definition_id, status, started_at, completed_at

```python
# Expected skeleton (to be confirmed from #651 models)
class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[WorkflowStatus] = mapped_column(String(50), default=WorkflowStatus.DRAFT)
    steps: Mapped[list["WorkflowStepDefinition"]] = relationship(...)
```

If these models are not yet confirmed, the service implementation must be stubbed to match the expected schema and updated once #651 lands.

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/workflow.py` — verify model fields match service assumptions (post-#651)
- 要建：
  - `src/services/workflow_service.py` — WorkflowService with definition CRUD + instance lifecycle
  - `tests/unit/test_workflow_service.py` — unit tests with mock DB session

### 2.3 缺什么

- [ ] `WorkflowService` class with all 6 public methods + `_advance_instance` helper
- [ ] `create_definition` — inserts `WorkflowDefinition` + all `WorkflowStepDefinition` rows in one transaction
- [ ] `get_definition` — fetches by id, raises `NotFoundException` if missing, eager-loads steps
- [ ] `list_definitions` — paginated list filtered by tenant_id
- [ ] `start_instance` — creates `WorkflowInstance` + first `WorkflowStepInstance`; calls `_advance_instance`
- [ ] `get_instance` — fetches by id, raises `NotFoundException` if missing, returns current step
- [ ] `list_instances` — paginated list filtered by tenant_id and optionally by definition_id
- [ ] `_advance_instance` — private helper; marks current step complete, creates next step record, updates instance's current_step_id; called by `start_instance` and future step-completion calls

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/services/workflow_service.py` | WorkflowService: definition CRUD + instance lifecycle + auto-step helper |
| `tests/unit/test_workflow_service.py` | Unit tests: mock DB, ≥ 6 test cases covering all public methods + boundary |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/workflow.py` | Verify schema (post-#651); no structural change expected |
| `src/services/__init__.py` | Export `WorkflowService` (if `__all__` is defined) |

### 3.3 新增能力

- **Service class**：`WorkflowService(session: AsyncSession)` — session is required, no default
- **Service method**：`create_definition(tenant_id: int, name: str, description: str | None, steps: list[StepInput]) -> WorkflowDefinition`
- **Service method**：`get_definition(workflow_definition_id: int, tenant_id: int) -> WorkflowDefinition`
- **Service method**：`list_definitions(tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[WorkflowDefinition], int]`
- **Service method**：`start_instance(workflow_definition_id: int, tenant_id: int) -> WorkflowInstance`
- **Service method**：`get_instance(instance_id: int, tenant_id: int) -> WorkflowInstance`
- **Service method**：`list_instances(tenant_id: int, workflow_definition_id: int | None = None, page: int = 1, page_size: int = 20) -> tuple[list[WorkflowInstance], int]`
- **Service method**（private）：`_advance_instance(instance: WorkflowInstance, session: AsyncSession) -> None`
- **ORM models**：`WorkflowDefinition`, `WorkflowStepDefinition`, `WorkflowInstance`, `WorkflowStepInstance` (from #651)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Return ORM objects directly** rather than wrapping in `ApiResponse` or calling `.to_dict()` — follows the service pattern established in CLAUDE.md. Routers are responsible for serialization.
- **Steps stored as separate rows** in `WorkflowStepDefinition` (from #651), not as JSON — enables SQL-level ordering and incremental updates without re-parsing.
- **`_advance_instance` as private helper** rather than a public method — auto-step transitions are an internal implementation detail; only `start_instance` and future `complete_step` calls invoke it.
- **One transaction per method** — `create_definition` and `start_instance` both flush the session; no partial writes on failure.

### 4.2 版本约束

None — no new external dependencies introduced by this subtask.

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` (CLAUDE.md §Multi-Tenancy).
- Service returns ORM/dataclass objects, **does not** call `.to_dict()`; serialization is the router's job.
- Service errors raise `AppException` subclasses (`NotFoundException`, `ValidationException`), **do not** return `ApiResponse.error()`.
- `session: AsyncSession` is a required constructor argument with no default (CLAUDE.md §Service Pattern).
- Do not use `async with get_db()` in the service — session is injected from the router via `Depends(get_db)`.

### 4.4 已知坑

1. **SQLAlchemy `relationship` lazy-loading in async context** → `get_definition` / `get_instance` must use `selectinload` or `joinedload` for related collections (`steps`, `step_instances`) to avoid `DetachedInstanceError` outside the session scope. **Symptom**: `DetachedInstanceError: Instance <WorkflowStepDefinition> is not bound to a Session`. **Fix**: `options=[selectinload(WorkflowDefinition.steps)]` on the select statement.
2. **`WorkflowStatus` / `StepStatus` enum names** must match exactly what #651 defined — import from the models module, do not re-define locally.
3. **Instance with no steps** — `start_instance` must validate that `WorkflowDefinition.steps` is non-empty before creating an instance. **Symptom**: index error or no first step created. **Fix**: raise `ValidationException("workflow definition has no steps")` if steps list is empty.

---

## 5. 实现步骤（按顺序）

### Step 1: Confirm model schema from #651

Inspect `src/db/models/workflow.py` and verify the exact column names, types, and relationship names for all four models. If #651 has not landed, stub the expected schema based on the issue description and note the stub must be updated when #651 merges.

**完成判定**：`PYTHONPATH=src python -c "from src.db.models.workflow import WorkflowDefinition, WorkflowStepDefinition, WorkflowInstance, WorkflowStepInstance; print('import ok')"` → exit 0

### Step 2: Create `src/services/workflow_service.py` skeleton

Create the file with:
- Imports: `AsyncSession`, `select`, `selectinload`, `func` from SQLAlchemy; `NotFoundException`, `ValidationException` from `pkg.errors.app_exceptions`; all four workflow models.
- Class: `class WorkflowService` with `__init__(self, session: AsyncSession)` — no default for session.
- Stub all 6 public methods + `_advance_instance` with `raise NotImplementedError`.

```python
# src/services/workflow_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, selectinload
from src.db.models.workflow import (
    WorkflowDefinition,
    WorkflowStepDefinition,
    WorkflowInstance,
    WorkflowStepInstance,
)
from src.db.models.workflow import WorkflowStatus, StepStatus
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class WorkflowService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # stubs — implement in Step 3
    async def create_definition(...): raise NotImplementedError
    async def get_definition(...): raise NotImplementedError
    async def list_definitions(...): raise NotImplementedError
    async def start_instance(...): raise NotImplementedError
    async def get_instance(...): raise NotImplementedError
    async def list_instances(...): raise NotImplementedError
    async def _advance_instance(...): raise NotImplementedError
```

**完成判定**：`ruff check src/services/workflow_service.py` → 0 errors

### Step 3: Implement definition CRUD methods

`create_definition(tenant_id, name, description, steps)`:
- Create `WorkflowDefinition(tenant_id=tenant_id, name=name, description=description, version=1, status=WorkflowStatus.DRAFT)`.
- For each `step` in `steps`, create `WorkflowStepDefinition(workflow_definition_id=def_id, name=step.name, order=step.order, action_type=step.action_type, action_config=step.action_config)`.
- `await self.session.flush()`.
- Return the `WorkflowDefinition` with steps eager-loaded.

`get_definition(workflow_definition_id, tenant_id)`:
- `stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_definition_id, WorkflowDefinition.tenant_id == tenant_id).options(selectinload(WorkflowDefinition.steps))`.
- `result = await self.session.execute(stmt)`.
- Raise `NotFoundException("WorkflowDefinition")` if `None`.
- Return entity.

`list_definitions(tenant_id, page, page_size)`:
- Count query: `select(func.count()).select_from(WorkflowDefinition).where(WorkflowDefinition.tenant_id == tenant_id)`.
- Fetch query: same filter + `order_by(WorkflowDefinition.id.desc())` + `offset((page-1)*page_size).limit(page_size)`.
- Return `(definitions, total)`.

**完成判定**：`ruff check src/services/workflow_service.py && PYTHONPATH=src mypy src/services/workflow_service.py` → both exit 0

### Step 4: Implement instance lifecycle methods

`start_instance(workflow_definition_id, tenant_id)`:
- Fetch the definition with `selectinload(WorkflowDefinition.steps)`; raise `NotFoundException` if missing.
- Validate `len(definition.steps) > 0`; raise `ValidationException("workflow definition has no steps")` otherwise.
- Create `WorkflowInstance(tenant_id=tenant_id, workflow_definition_id=definition.id, status=WorkflowStatus.ACTIVE, current_step_id=None)`.
- `await self.session.flush()`.
- Create first `WorkflowStepInstance(tenant_id=..., workflow_instance_id=instance.id, step_definition_id=definition.steps[0].id, status=StepStatus.PENDING)`.
- `await self.session.flush()`.
- Call `await self._advance_instance(instance)`.
- Return instance.

`get_instance(instance_id, tenant_id)`:
- `stmt = select(WorkflowInstance).where(WorkflowInstance.id == instance_id, WorkflowInstance.tenant_id == tenant_id)`.
- Raise `NotFoundException("WorkflowInstance")` if `None`.
- Return entity.

`list_instances(tenant_id, workflow_definition_id=None, page=1, page_size=20)`:
- Base filter: `WorkflowInstance.tenant_id == tenant_id`.
- Add `WorkflowInstance.workflow_definition_id == workflow_definition_id` if provided.
- Count + fetch with pagination; return `(instances, total)`.

**完成判定**：`ruff check src/services/workflow_service.py && PYTHONPATH=src mypy src/services/workflow_service.py` → both exit 0

### Step 5: Implement `_advance_instance` helper

```
async def _advance_instance(instance: WorkflowInstance) -> None:
```

- Fetch all `WorkflowStepInstance` records for this instance, ordered by step definition's `order`.
- Find the last non-failed step (status != `StepStatus.FAILED`).
- If all steps are complete or no steps exist → set `instance.status = WorkflowStatus.COMPLETED`; `instance.current_step_id = None`.
- Otherwise → set `current_step_id` to the next step's `id` (first step if none started yet).
- `await self.session.flush()`.

**完成判定**：`ruff check src/services/workflow_service.py && PYTHONPATH=src mypy src/services/workflow_service.py` → both exit 0

### Step 6: Write unit tests in `tests/unit/test_workflow_service.py`

Use `MockState`, `make_mock_session` from `tests/unit/conftest.py`. Create a `workflow_handler` in conftest.py if not already present (mirroring `opportunity_handler` pattern).

Required test cases:
1. `test_create_definition` — happy path; verify ORM object returned, no `.to_dict()` called.
2. `test_get_definition_not_found` — raises `NotFoundException`.
3. `test_list_definitions_paginated` — returns (items, total).
4. `test_start_instance_happy` — instance created, first step created, status ACTIVE.
5. `test_start_instance_no_steps` — raises `ValidationException`.
6. `test_get_instance_not_found` — raises `NotFoundException`.
7. `test_list_instances` — filters by tenant_id and optionally by definition_id.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 6 passed

---

## 6. 验收

- [ ] `ruff check src/services/workflow_service.py` → 0 errors
- [ ] `PYTHONPATH=src mypy src/services/workflow_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 6 passed
- [ ] `from src.db.models.workflow import WorkflowDefinition, WorkflowInstance` → import succeeds (model existence verified after #651)
- [ ] `WorkflowService.__init__.__annotations__` confirms `session: AsyncSession` with no default

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #651 lands with different column/relationship names than expected, breaking service SQL | 低 | 高 | Re-inspect #651 output in `src/db/models/workflow.py` and update service column references before merging this PR |
| `selectinload` / lazy-loading edge cases cause `DetachedInstanceError` in async context | 中 | 中 | Add explicit `options` clauses; add integration test with real async session once `tests/integration/` fixture is available |
| Future `complete_step` caller calls `_advance_instance` on an already-completed instance | 低 | 中 | Add guard: if `instance.status == WorkflowStatus.COMPLETED`, raise `ValidationException("instance already completed")` in `start_instance` and any future step-completion method |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/workflow_service.py tests/unit/test_workflow_service.py
git commit -m "feat(automation): implement WorkflowService definition CRUD and instance lifecycle

Closes #652"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): WorkflowService definition CRUD and instance lifecycle" --body "Closes #652"

# 2. Update progress
# - In this board document §Changelog table, add a row with today's date
# - PR merge triggers docs/dev-plan/README.md §1.1 AUTO-INDEX update via generator
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — same service pattern (constructor session, returns ORM, raises AppException)
- 同类参考实现：TBD - 待验证：opportunity_service.py 分页模式对应文件路径
- 父 issue / 关联：#37
- 依赖 issue：#651

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |

---

**Fixes applied:**

| Line | Original | Fixed |
|------|----------|-------|
| 9 (依赖) | `[0651-实现工作流相关模型与枚举定义](../50-automation/0651-implement-workflow-related-models-and-enum-definitions.md)` | `TBD - 待验证：0651 工作流模型与枚举定义对应文件路径` |
| 10 (启用后赋能) | `[0686-实现 POST/GET/PUT/DELETE 自动化规则路由端点](../50-automation/0686-add-post-get-put-delete-automation-rules-router-endpoints.md)` | `TBD - 待验证：0686 自动化规则路由端点对应文件路径` |
| 10 (启用后赋能) | `[0687-构建规则执行引擎与触发调度](../50-automation/0687-build-rule-execution-engine-and-trigger-dispatch.md)` | `TBD - 待验证：0687 规则执行引擎与触发调度对应文件路径` |
| 47 (model path) | `[`src/db/models/workflow_model.py`](../../src/db/models/workflow_model.py)` | `[`src/db/models/workflow.py`](../../src/db/models/workflow.py)` |
| 312 (opportunity_service) | `[`src/services/opportunity_service.py`](../../src/services/opportunity_service.py)` | `TBD - 待验证：opportunity_service.py 分页模式对应文件路径` |

Note: the code blocks in Steps 1 and 2 that reference imports from `src.db.models.workflow_model` were also updated to `src.db.models.workflow` (to match the corrected link).
