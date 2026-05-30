# Automation · Wire up agent_tasks router and add timeout/error handling

| 元数据 | 值 |
|---|---|
| Issue | #624 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [#623 Wire up Task model/service/router](.), [#42 (parent)] |
| 启用后赋能 | All automation-triggering features |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The `AgentTasksService` and its router (`agent_tasks.py`) are implemented by #623, but they are not yet wired into `src/main.py`, so the API endpoints are unreachable. Additionally, background tasks dispatched to agents can stall indefinitely — there is no mechanism to surface a stale task as failed. Dispatch infrastructure also lacks a structured500 response with a `Retry-After` header that clients can honour on retryable failures. Without these integrations the automation platform cannot be operated reliably in production.

### 1.2 做完后

- **用户视角**：Automation administrators querying `/agents/tasks/{task_id}` will receive a task object that reflects current state; stalled tasks (> 5 min inactivity) are returned as `failed` instead of `submitted`. Failed dispatches return HTTP 503 with a `Retry-After` header.
- **开发者视角**：`src/main.py` mounts `agent_tasks` router under `/agents`. `AgentTasksService` exposes `mark_stale_tasks_failed(session)` called on every fetch. Dispatch errors raise `ConflictException` for duplicates and propagate to a global handler that sets the `Retry-After` header.

### 1.3 不做什么（剔除）

- [ ] Do not add a dedicated background heartbeat daemon (cron / Celery beat) — timeout detection is pull-based, triggered on fetch.
- [ ] Do not modify the `AgentTask` ORM model schema (add new columns to an existing model requires a separate migration issue).
- [ ] Do not implement retry logic in the service layer — the `Retry-After` header only informs the caller; client manages retry strategy.

### 1.4 关键 KPI

- `grep -r "agent_tasks" src/main.py | grep "router" | wc -l` → `1` (router registered)
- `grep "ConflictException" src/main.py | grep "Retry-After" | wc -l` → `1` (handler branch present)
- `PYTHONPATH=src ruff check src/main.py src/services/agent_tasks_service.py src/api/routers/agent_tasks.py` → `0 errors`
- `PYTHONPATH=src pytest tests/unit/test_agent_tasks_service.py -v` → ≥ current N passed

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/main.py` L? — 主入口文件，需确认 router注入位置和全局异常处理注册位置  
TBD - 待验证：`src/api/routers/agent_tasks.py` L? — 由 #623 新建，需确认是否存在TBD - 待验证：`src/services/agent_tasks_service.py` L? — 由 #623 新建，需确认是否存在

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — 注册 agent_tasks router，挂载到 /agents；全局 AppException handler 新增 ConflictException 分支
  - `src/services/agent_tasks_service.py` — 新增 `mark_stale_tasks_failed()` 方法（由 #623 建初版）
  - `src/api/routers/agent_tasks.py` — GET /{task_id} 在返回前调用 `mark_stale_tasks_failed()`
- 要建：
  - `tests/unit/test_agent_tasks_service.py` — 单元测试（含 stale-timeout 场景）
  - `tests/integration/test_agent_tasks_integration.py` —集成测试（如 #623 已建则补充）

### 2.3 缺什么

- [ ] `src/main.py` 没有 `agent_tasks` router 的 `include_router` 调用 — endpoints unreachable。
- [ ] 没有 timeout 检测逻辑 — stale tasks remain `submitted` indefinitely.
- [ ] 全局 AppException handler 没有 ConflictException 分支 — duplicate `task_id` returns generic 500 instead of 409 or a Retry-After 500.
- [ ] Dispatch failures do not return `Retry-After` header — client cannot back-off predictably.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_agent_tasks_service.py` |覆盖 router 注册、timeout 检测、ConflictException 分支的单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | include_router(agent_tasks_router, prefix="/agents")；AppException handler 新增 ConflictException → 500 + Retry-After |
| TBD - 待验证：`src/services/agent_tasks_service.py` | 新增 `mark_stale_tasks_failed(session, tenant_id)` → 更新超时 stale任务状态 |
| TBD - 待验证：`src/api/routers/agent_tasks.py` | GET /{task_id} 调用 `mark_stale_tasks_failed()` 后返回；在 dispatch error 时抛出 ConflictException |

### 3.3 新增能力

- **Service method**：`AgentTasksService.mark_stale_tasks_failed(self, session: AsyncSession, tenant_id: int) -> list[AgentTask]`
- **API endpoint**：已由 #623 定义；GET handler 副作用：过期任务自动标记为 failed 返回
- **Router registration**：`app.include_router(agent_tasks_router, prefix="/agents")` in `src/main.py`
- **HTTP behaviour**：dispatch failure → HTTP 503 + `Retry-After: 30` header；duplicate task_id → HTTP 409 Conflict (via existing ConflictException) 或包装为 503---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **拉取式 timeout 而非心跳 daemon**：CRM 环境无 Celery / Redis；轮询每个 fetch触发被动检测，无需额外基础设施，成本 O(bypassers) ≈ 0。
- **Retry-After 放在500 而非独立的 retry endpoint**：保持 REST语义，调度失败的调用方按标准 header 自动退避。
- **ConflictException 用于 task_id 重复**：符合 CLAUDE.md 约定（409 Conflict =约束冲突），重复 task_id 是合法的业务冲突场景。

### 4.2 版本约束

（无新增依赖）

### 4.3 兼容性约束

- 多租户：`mark_stale_tasks_failed` 必须 `WHERE tenant_id = :tenant_id`，避免跨租户误标。
- Service错误抛 `AppException` 子类；序列化由 router ✅，服务层不调用 `.to_dict()` ✅。
- Session注入：router 用 `session: AsyncSession = Depends(get_db)`，**禁止** `async with get_db()`。

### 4.4 已知坑

1. **Alembic autogen 把 `last_updated_at` 写成 naive DateTime** →规避：检查 migration 文件，手动将 `DateTime`改为 `DateTime(timezone=True)`；在 `alembic/env.py`确认 `render_as_batch=True` 用于 future migration兼容性。
2. **SQLAlchemy Base 子类列名不能用 `metadata`**（见 CLAUDE.md 已知坑）→规避：`AgentTask` 模型如需元数据字段，用 `event_metadata` / `payload`，不用 `task_metadata`。
3. **全局异常 handler 不能在 `app.add_exception_handler`之后被 `app.include_router` 遮蔽** → 规避：确认 `agent_tasks` router 的 path operation 函数**不**有自己的 `@router.exception_handler`，否则会 bypass 全局 handler。

---

## 5. 实现步骤（按顺序）

### Step 1: Confirm #623 outputs before continuing

[Verify that #623 has produced `src/api/routers/agent_tasks.py` and `src/services/agent_tasks_service.py`. This step prevents downstream edits from referencing non-existent symbols.]

操作：
- a) Inspect git diff / uncommitted files for router and service file existence.
- b) Note the exported symbols (function names, class names) for use in Step 2-3.

**完成判定**：`ls src/api/routers/agent_tasks.py src/services/agent_tasks_service.py` → both files exist / `git status` does not show them as deleted or staged pending #623

### Step 2: Register agent_tasks router in src/main.py

[Add `include_router(agent_tasks_router, prefix="/agents")` to the FastAPI app instance. Order matters: register this after static-file middleware (if any) and before any catch-all routes.]

操作：
- a) 在 `src/main.py`顶部添加导入：
  ```python
  from api.routers import agent_tasks
  ```
- b) 在 `app = FastAPI(...)` 初始化后、`app.add_exception_handler` 之前插入：
  ```python
  app.include_router(agent_tasks.router, prefix="/agents", tags=["Agents"])
  ```

示例代码：

```python
# src/main.py
from api.routers import agent_tasks  # 新增

app = FastAPI(title="dev-agent-system")

# 全局异常 handler必须在 router 注册之后立即注册（避免被 router-level handler bypass）
app = FastAPI(...)
app.add_exception_handler(AppException, app_exception_handler)
app.include_router(agent_tasks.router, prefix="/agents", tags=["Agents"])  # 本板块新增
```

**完成判定**：`grep -n "include_router.*agent_tasks" src/main.py` →1 match; `ruff check src/main.py` → 0 errors

### Step 3: Add ConflictException branch to global exception handler with Retry-After

[Extend the global AppException handler in src/main.py to detect dispatch-type ConflictException and emit HTTP 503 with `Retry-After: 30`. Other ConflictException variants (e.g. duplicate task_id on create) retain their normal409 response. A practical way to distinguish: check `request.url.path` for a dispatch-specific prefix, or inspect the exception `.detail` string for a `"dispatch"` token.]

操作：
- a) Locate the existing `app_exception_handler` function in `src/main.py`.
- b) Add a branch before the generic `ConflictException` handler:
  ```python
  if isinstance exc (ConflictException) and "dispatch" in str(exc.detail).lower():
      return JSONResponse(
          status_code=503,
          headers={"Retry-After": "30"},
          content={"success": False, "error": exc.detail},
      )
  ```
- c) Ensure the generic ConflictException handler remains for non-dispatch duplicates (→409).

示例代码：

```python
# src/main.py — excerpt from app_exception_handler
from pkg.errors.app_exceptions import (
    NotFoundException, ValidationException,
    ConflictException, ForbiddenException, UnauthorizedException
)

async def app_exception_handler(request: Request, exc: AppException):
    if isinstance(exc, ConflictException) and "dispatch" in str(exc.detail).lower():
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "30"},
            content={"success": False, "error": exc.detail},
        )
    # ... rest of handler (ConflictException →409, others unchanged)
```

**完成判定**：`grep -A5 "503.*Retry-After" src/main.py | grep -c "ConflictException"` → `1+`; `ruff check src/main.py` → 0 errors

### Step 4: Add mark_stale_tasks_failed to AgentTasksService

[Add a method that queries all `AgentTask` rows with `status = submitted` and `last_updated_at` older than 5 minutes, then updates them to `failed`. Called from GET handler before returning task list or single task.]

操作：
- a) 在 `src/services/agent_tasks_service.py` 的 `AgentTasksService` 类中添加方法：
  ```python
  from datetime import datetime, timezone, timedelta  async def mark_stale_tasks_failed(self, tenant_id: int) -> list[AgentTask]:
      cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
      result = await self.session.execute(
          select(AgentTask).where(
              AgentTask.tenant_id == tenant_id,
              AgentTask.status == AgentTaskStatus.SUBMITTED,
              AgentTask.last_updated_at < cutoff,
          )
      )
      stale = list(result.scalars().all())
      for task in stale:
          task.status = AgentTaskStatus.FAILED
          task.last_updated_at = datetime.now(timezone.utc)
 if stale:
          await self.session.commit()
      return stale
  ```
- b) 确保 `AgentTaskStatus` enum 包含 `SUBMITTED` 和 `FAILED`；如缺失则补全。

**完成判定**：`ruff check src/services/agent_tasks_service.py` → 0 errors; `PYTHONPATH=src python -c "from services.agent_tasks_service import AgentTasksService; print('import ok')"` → 1 line

### Step 5: Wire timeout check into GET /{task_id} route handler

[Modify the GET handler in `src/api/routers/agent_tasks.py` to call `mark_stale_tasks_failed` before returning the task. Use a dedicated service method execution; do not duplicate the query logic in the router.]

操作：
- a) 在 `src/api/routers/agent_tasks.py` GET /{task_id} handler 中，在 `svc.get_task(...)` 之后、`return` 之前插入：
  ```python stale = await svc.mark_stale_tasks_failed(ctx.tenant_id)
  _ = stale  # 副作用已体现到 DB；不影响本请求的返回  ```
- b) 同理在 GET `/` (list) handler 中也调用一次（复用同一次调用，减少 DB 查询）。

示例代码：

```python
# src/api/routers/agent_tasks.py — GET /{task_id}
@router.get("/{task_id}")
async def get_agent_task(
    task_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = AgentTasksService(session)
    # detect and mark stale tasks before returning result
    await svc.mark_stale_tasks_failed(ctx.tenant_id)
    task = await svc.get_task(task_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": task.to_dict()}
```

**完成判定**：`grep -n "mark_stale_tasks_failed" src/api/routers/agent_tasks.py` → ≥1 match; `ruff check src/api/routers/agent_tasks.py` → 0 errors

### Step 6: Write unit tests

[Cover: router registered (via import smoke test), mark_stale_tasks_failed marks correct tasks, dispatch ConflictException produces retry-after 500, duplicate task_id produces409.]

操作：
- a) 创建 `tests/unit/test_agent_tasks_service.py`，使用 `tests/unit/conftest.py` 提供的 MockRow / MockResult / make_mock_session 模式。
- b) 测试用例：
  1. `test_mark_stale_tasks_failed` — mock 一个超过5 分钟的 `submitted` 任务，验证状态变为 `failed`
  2. `test_mark_stale_tasks_no_op_when_fresh` — mock 刚更新的任务，验证不变化
  3. `test_mark_stale_tasks_failed_only_affects_submitted` — mock 已是 `failed` 状态的任务，验证状态不变
 4. `test_dispatch_conflict_returns_503_with_retry_after` — patch `svc.dispatch` 抛出 conflict，验证 HTTP response 状态码和 header

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_tasks_service.py -v` → all passed; `ruff check tests/unit/test_agent_tasks_service.py` → 0 errors

---

## 6. 验收

- `ruff check src/main.py src/services/agent_tasks_service.py src/api/routers/agent_tasks.py tests/unit/test_agent_tasks_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_agent_tasks_service.py -v` → all passed
- `PYTHONPATH=src pytest tests/integration/test_agent_tasks_integration.py -v` → all passed（若文件已由 #623 创建）
- `python -c "from main import app; print([r.path for r in app.routes if 'agent' in r.path])"` → `['/agents/tasks', '/agents/tasks/{task_id}']` 或等效验证 router 注册
- 手动作弊检查：`cd /Users/yihuazhuo/Desktop/git/github/agent-job && grep -n "include_router.*agent_tasks" src/main.py` → 1 match 且在 exception handler 注册之后

---

## 7. 风险与回退

| 风险 | 概率 | 影响 |降级方案 |
|------|------|------|---------|
| #623 尚未完成，`src/api/routers/agent_tasks.py` 缺失 → Step2-3 编辑失败 | 中 | 高 | 本板块阻塞 — 等 #623 合并后再继续；Step 1 的判定可防止静默腐败 |
| `mark_stale_tasks_failed` 在 list handler 中被同时调用两次（GET / + GET /{id}）→双重 commit → 部分行锁定 | 低 | 中 | 两处调用改为同一 session 上执行一次；全局 commit 由 GET / 触发，GET /{id} 只读 |
| Retry-After header 与 CDN / nginx缓存交互被吃掉 | 低 | 低 | 在 `src/main.py` 的 `JSONResponse` 中显式加 `Cache-Control: no-store` 阻止缓存 |
| SQLAlchemy `last_updated_at` 列不存在于 `AgentTask` 模型 | 中 | 高 | 在 `AgentTask` 模型中添加 `last_updated_at: Mapped[datetime]` 列；需要对应 migration（见 §4.4 注意 JSONB vs DateTime） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/main.py src/services/agent_tasks_service.py src/api/routers/agent_tasks.py tests/unit/test_agent_tasks_service.py
git commit -m "feat(automation): wire agent_tasks router, add stale-task timeout, retry-after503 handler"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#624): wire agent_tasks router in main.py, timeout + Retry-After handling" --body "Closes #624"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/api/routers/` 下已有 router 注册方式（如 `customers.py` / `sales.py`），用于确认 `include_router`模式
- 父 issue /关联：#42, #623---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |

---

**修复说明**：第 80–81 行的两处 `[text](path)` 链接指向了文档目录树之外的错误路径，且对应的两个文件已在 §2.1 中标注为 `TBD - 待验证`（存在性未确认），因此均降级为纯文本并保留 `TBD - 待验证` 前缀。`src/main.py` 的链接路径 `../../../src/main.py` 经验证可正确解析，予以保留。
