# WorkflowService · 实现超时检测与重试机制

| 元数据 | 值 |
|---|---|
| Issue | #655 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [0654-implement-workflowstep-model-and-router](00-foundations/0654-implement-workflowstep-model-and-router.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Currently `WorkflowService` has no mechanism to detect steps that have exceeded their deadline, nor any retry capability for steps configured as automatic. Without `_check_timeouts()`, a step that becomes overdue will sit indefinitely — no escalation is triggered, no automatic failure is recorded. Without retry logic, transient errors on auto steps (e.g. downstream service hiccup) cause immediate workflow failure even when the step definition specifies `max_retries > 0`. Both gaps must be closed to make workflow execution reliable.

### 1.2 做完后

- **用户视角**: When an auto step fails and `max_retries` is defined, the system automatically re-queues it up to the configured cap. Overdue steps are transparently escalated or marked failed without manual intervention. Administrators calling `POST /workflows/instances/{id}/retry/{step_id}` can manually re-trigger a failed step. No user-visible changes if the workflow completes normally.
- **开发者视角**: A new `POST /workflows/instances/{id}/retry/{step_id}` endpoint is available on the router. `WorkflowService` exposes `_check_timeouts()` for background polling (or caller-driven invocation) and `_process_auto_step()` as an async helper callable by the task queue. Services can import and call these new public-ish methods on `WorkflowService`.

### 1.3 不做什么（剔除）

- [ ] Do NOT implement the background scheduler/worker infrastructure itself — only provide the methods and the endpoint; how they get scheduled is out of scope.
- [ ] Do NOT add email/Slack escalation notifications inside `_check_timeouts()`. The escalation is limited to recording an escalation event on the step record.
- [ ] Do NOT modify `WorkflowInstance` ORM model unless a new column is genuinely needed for this feature.

### 1.4 关键 KPI

- [KPI 1: `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 8 passed covering timeout, retry cap, manual retry, and `_process_auto_step` paths]
- [KPI 2: `ruff check src/services/workflow_service.py` → 0 errors]
- [KPI 3: `ruff check src/api/routers/workflow_router.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证: `src/services/workflow_service.py` — 现有 `WorkflowService` class, 需确认是否已有 `_check_timeouts` 或 `_process_auto_step` 方法，以及当前 `WorkflowStep` model 是否已有 `attempt_count`, `max_retries`, `deadline`字段

TBD - 待验证: `src/api/routers/workflow_router.py` — 现有 router 文件，查看现有 endpoint签名### 2.2 涉及文件清单

- 要改:
  - `src/services/workflow_service.py` — 添加 `_check_timeouts()`, `_process_auto_step()`,扩展 `execute_step()` / 相关方法以支持 retry
  - `src/api/routers/workflow_router.py` — 添加 `POST /workflows/instances/{id}/retry/{step_id}` endpoint
  - `tests/unit/test_workflow_service.py` — 新增超时、重试上限、手动重试的测试用例
- 要建:
  - `tests/integration/test_workflow_service_integration.py` —端到端超时与重试集成测试
  - `alembic/versions/<id>_add_workflow_step_timeout_retry_cols.py` — 如 `WorkflowStep` 需新增列 (见 §4.4 已知坑)

### 2.3 缺什么

- [ ] `WorkflowService`缺少 `_check_timeouts()` 方法 — 无法检测和处理超过 deadline 的 step
- [ ] `WorkflowStep` model缺少 `attempt_count` 列 — 无法跟踪自动 step 重试次数
- [ ] `WorkflowStep` model 缺少 `max_retries` 列或等价字段 — 无法从 step 定义读取重试上限
- [ ] 缺少 retry cap 逻辑 —超出 `max_retries` 后不应再重试，需标记 failure- [ ] 缺少 `_process_auto_step` async helper — 自动 step 无法被后台任务调用- [ ] router 缺少 `POST /workflows/instances/{id}/retry/{step_id}` endpoint — 无法手动触发重试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/integration/test_workflow_service_integration.py` | 端到端超时 + 重试 cap集成测试，带 real Postgres fixture |
| `alembic/versions/<auto_id>_add_workflow_step_timeout_retry_cols.py` | 如需新增列则创建 migration；否则填 N/A |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/workflow_service.py` | 新增 `_check_timeouts()`, `_process_auto_step()`, retry logic in execute path, attempt tracking |
| `src/api/routers/workflow_router.py` | 新增 `POST /workflows/instances/{id}/retry/{step_id}` handler |
| `tests/unit/test_workflow_service.py` | 新增 5+ 测试用例覆盖超时升级路径、重试 cap、手动retry、attempt_count |

### 3.3 新增能力

- **Service method**: `WorkflowService._check_timeouts(self, tenant_id: int) -> None` — 查询所有 overdue steps 并触发 escalation/failure
- **Service method**: `WorkflowService._process_auto_step(self, step_id: int, tenant_id: int) -> None` — async helper 处理自动 step，带 attempt_count 递增与 cap 检查
- **Service method**: `WorkflowService.retry_step(self, instance_id: int, step_id: int, tenant_id: int) -> WorkflowStep` —手动重试接口，抛异常若 cap 已满
- **API endpoint**: `POST /workflows/instances/{instance_id}/retry/{step_id}` → `{"success": true, "data": {...}}`
- **ORM model扩展**: `WorkflowStep` 新增/确认存在 `attempt_count` (int, default 0), `max_retries` (int, nullable), `deadline` (datetime, nullable) — 列名需避免 `metadata` (见 §4.4)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Retry in-process vs async queue**: `_process_auto_step` runs as an async helper callable by a task queue (e.g. the existing background infra, not added here). This avoids shipping a new queue in this issue while still making the method available. Calling code is responsible for scheduling it — this is the right seam because different environments will use different task systems.
- **Retry cap enforcement at call-site vs inside helper**: Cap check lives inside `_process_auto_step` and `retry_step()` — if `attempt_count >= max_retries`, raise `ForbiddenException` / `ValidationException`. This centralises the rule so callers cannot accidentally bypass it.
- **No new ORM columns without migration**: If the existing `WorkflowStep` model lacks the needed columns, the migration is created carefully by hand (never trust autogen for the column types — see §4.4).

### 4.2 版本约束

|依赖 | 版本 | 理由 |
|------|------|------|
| SQLAlchemy | 2.x | 本项目已有 async + SQLAlchemy 2.x，不升级 |
| `asyncio` | stdlib | async helpers 使用标准库，无需新依赖 |

### 4.3 兼容性约束

- Multi-tenant: every SQL query in `_check_timeouts()` and `retry_step()` must include `WHERE tenant_id = :tenant_id`
- `WorkflowService.__init__(self, session: AsyncSession)` — session is required, no default
- `WorkflowService` methods return ORM objects; **do not** call `.to_dict()` in service methods — router handles serialization
- Service methods raise `AppException` subclasses (e.g. `NotFoundException`, `ValidationException`, `ForbiddenException`) — do **not** return `ApiResponse.error()`
- Routers inject session via `session: AsyncSession = Depends(get_db)`

### 4.4 已知坑

1. **SQLAlchemy `metadata` column name collision** → SQLAlchemy `Base.metadata` is the `MetaData` object; a column named `metadata` on any ORM model crashes at class definition. Any step/event metadata columns must use `event_metadata`, `payload`, `attrs`, etc. Check if `WorkflowStep` model tries to name a column `metadata` — if so, rename it.
2. **Alembic autogen emits `sa.JSON()` instead of `sa.JSONB()`** → When creating the new migration for step retry columns, if any column holds structured data, manually replace autogenerated `sa.JSON()` with `sa.JSONB()`.
3. **Alembic autogen drops `timezone=True`** → If `deadline` column is a `DateTime`, manually add `timezone=True` (i.e. use `DateTime(timezone=True)`) to match PostgreSQL `TIMESTAMPTZ`. Autogenerate will produce bare `DateTime` — fix it by hand.
4. **Import path pattern** → PYTHONPATH=src, use `from services.workflow_service import WorkflowService` not `from src.services.workflow_service`.

---

## 5. 实现步骤（按顺序）

### Step 1: Confirm WorkflowStep model columnsReview the current `WorkflowStep` ORM model in `src/db/models/` to identify which columns already exist (`attempt_count`, `max_retries`, `deadline`). Confirm the exact field names and types before writing any service code.

操作：
- a) Read `src/db/models/workflow_step.py` (via TBD if unverified) to list all existing columns
- b) Compare against the needs in §2.3 — determine whether a migration is needed or all columns already exist

**完成判定**: File `src/db/models/workflow_step.py` exists and contains `attempt_count`, `max_retries`, `deadline` fields — or a hand-written migration `<id>_add_workflow_step_timeout_retry_cols.py` is created and passes `alembic upgrade head`.

---

### Step 2: Add attempt-count tracking and retry-cap logic to WorkflowService

Add `_attempt_count` increment and cap-check guard inside `_process_auto_step`. Add `_check_timeouts()` async method that queries overdue steps (`WHERE deadline IS NOT NULL AND deadline < utcnow() AND status != 'failed'`). For each overdue step, record escalation/failure. Expose `retry_step()` for manual re-trigger.

操作：
- a) In `src/services/workflow_service.py`, add method `_check_timeouts(self, tenant_id: int) -> None`:
  ```python
  async def _check_timeouts(self, tenant_id: int) -> None:
      """Query overdue steps and escalate/fail them."""
      now = datetime.now(timezone.utc)
      result = await self.session.execute(
          select(WorkflowStep).where(
              WorkflowStep.tenant_id == tenant_id,
              WorkflowStep.deadline.isnot(None),
              WorkflowStep.deadline < now,
          )
      )
      for step in result.scalars().all():
          step.status = StepStatus.failed          step.error_message = "Deadline exceeded — escalated"
          await self._escalate_step(step, tenant_id)
      await self.session.commit()
  ```
- b) Add `_process_auto_step(self, step_id: int, tenant_id: int) -> None`
- c) Add `retry_step(self, instance_id: int, step_id: int, tenant_id: int) -> WorkflowStep`
- d) All SQL queries include `tenant_id = :tenant_id` in WHERE clause

**完成判定**: `ruff check src/services/workflow_service.py` →0 errors / `PYTHONPATH=src mypy src/services/workflow_service.py` →0 errors

---

### Step 3: Add POST /workflows/instances/{id}/retry/{step_id} endpoint

操作：
- a) In `src/api/routers/workflow_router.py`, add:
  ```python
  @router.post("/instances/{instance_id}/retry/{step_id}")
  async def retry_step(
      instance_id: int,
      step_id: int,
      ctx: AuthContext = Depends(require_auth),
      session: AsyncSession = Depends(get_db),
  ):
      svc = WorkflowService(session)
      step = await svc.retry_step(instance_id, step_id, tenant_id=ctx.tenant_id)
      return {"success": True, "data": step.to_dict()}
  ```
- b) Verify routing prefix does not conflict with existing routes

**完成判定**: `ruff check src/api/routers/workflow_router.py` → 0 errors / Server starts without import error

---

### Step 4: Write unit tests for all new paths

操作：
- a) Add to `tests/unit/test_workflow_service.py` test cases:
  - `test_check_timeouts_marks_overdue_steps_failed`
  - `test_process_auto_step_increments_attempt_count`
  - `test_process_auto_step_respects_max_retries_cap`
  - `test_retry_step_succeeds_within_cap`
  - `test_retry_step_raises_when_cap_exceeded`
  - `test_retry_step_invalid_instance_raises_not_found`
  - `test_retry_step_invalid_step_raises_not_found`
- b) Each test uses `make_mock_session` pattern as per CLAUDE.md §Unit Test SQL Mocks
- c) Verify all new tests pass**完成判定**: `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 8 passed---

### Step 5: Run alembic + ruff full check

操作：
- a) `alembic upgrade head` — if migration was created
- b) `alembic downgrade -1 && alembic upgrade head && alembic current` — verify round-trips cleanly
- c) `ruff check src/services/workflow_service.py src/api/routers/workflow_router.py src/db/models/workflow_step.py`
- d) `ruff format src/services/workflow_service.py src/api/routers/workflow_router.py`

**完成判定**: All commands exit0 with no output lines for errors

---

## 6. 验收

- [ ] `ruff check src/services/workflow_service.py src/api/routers/workflow_router.py` → 0 errors
- [ ] `ruff format --check src/services/workflow_service.py src/api/routers/workflow_router.py` → 0 diff
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 8 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_workflow_service_integration.py -v` → 全 passed（如 migration涉及 DB）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及 migration）
- [ ] 端到端：`POST /workflows/instances/{id}/retry/{step_id}` → `{"success": true, "data": {...}}` with correct step JSON

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|---|---|---|---|
| `_check_timeouts()` runs on every instance query and adds N+1 if called in a loop | 中 | 中 | Envelope `_check_timeouts()` behind a feature flag; scheduling call-site owned by caller |
| New migration adds nullable columns to large table, causes lock contention | 低 | 中 | Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pattern; set migration batch to non-peak window |
| `attempt_count` column missing from model and not caught until integration test | 低 | 高 | Step 1 of §5 explicitly verifies column existence via model inspection before Step 2 runs |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/workflow_service.py src/api/routers/workflow_router.py tests/unit/test_workflow_service.py
git commit -m "feat(workflow): add timeout detection and retry cap to WorkflowService"

# 2. Update progress
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现: TBD - 待验证: `src/services/< 同类服务名 >.py` — 查看类似 async helper pattern 的现有实现作为参照
- 第三方文档: [SQLAlchemy 2.x async documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- 父 issue / 关联: #37, #654

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
