# 自动化 · 添加工作流 API 路由

| 元数据 | 值 |
|---|---|
| Issue | #521 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | TBD - 待验证：工作流数据层文档路径 |
| 启用后赋能 | TBD - 待验证：自动化规则执行引擎文档路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #520 establishes the data layer (ORM models + service classes) for workflows. Issue #73 tracks the broader automation work. Without API routers, the workflow service is inaccessible — no frontend page, no chain of downstream automation features can call it. The routers are the glue between the service layer and any consumer (frontend, webhooks, internal automation triggers).

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯后端 API layer
- **开发者视角**：可 call `GET /workflows/`, `POST /workflows/`, `GET /workflows/{id}`, `DELETE /workflows/{id}`, `POST /workflows/{id}/publish`, `POST /workflows/{id}/trigger-test`, `GET /workflow-executions/`, `GET /workflow-executions/{id}`, `GET /workflow-executions/{id}/logs`, `POST /workflow-executions/{id}/retry`, `POST /workflow-executions/{id}/retry/{node_id}` from any HTTP client, all filtered by `tenant_id`

### 1.3 不做什么（剔除）

- [ ] Service class implementation — handled in #520
- [ ] ORM model definitions — handled in #520
- [ ] Database migrations — handled in #520
- [ ] Frontend integration — belongs in a separate frontend issue

### 1.4 关键 KPI

- [`ruff check src/api/routers/workflows.py src/api/routers/workflow_executions.py` → 0 errors](./../README.md#lints)
- `PYTHONPATH=src pytest tests/unit/test_workflows.py tests/unit/test_workflow_executions.py -v` → ≥ 8 passed
- All 10 endpoints return `{"success": true, "data": {...}}` envelope on success
- Every SQL query in services includes `tenant_id` filter (verified by unit tests)

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/` 目录结构 — 需确认现有 router 文件列表和命名约定

TBD - 待验证：`src/services/workflow_service.py` 和 `src/services/workflow_execution_service.py` 是否已在 #520 中创建（`src/services/` 下是否有 `workflow` 开头的文件）

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/__init__.py` — 注册两个新 router
  - `src/main.py` — include_router 调用（如果 router 未在 __init__.py 中统一注册）
- 要建：
  - `src/api/routers/workflows.py` — workflow CRUD + publish + trigger-test router
  - `src/api/routers/workflow_executions.py` — execution logs + retry router
  - `tests/unit/test_workflows.py` — unit tests for workflows router
  - `tests/unit/test_workflow_executions.py` — unit tests for workflow_executions router

### 2.3 缺什么

- [ ] `src/api/routers/workflows.py` — workflow list/create/get/delete/publish/trigger-test endpoints
- [ ] `src/api/routers/workflow_executions.py` — execution logs + retry endpoints
- [ ] Router registration in `__init__.py` or `main.py`
- [ ] Unit tests for both routers
- [ ] Unit test `mock_db_session` fixtures wired to workflow handlers

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/workflows.py` | Workflow CRUD + publish + trigger-test HTTP endpoints |
| `src/api/routers/workflow_executions.py` | Execution logs + retry-from-node HTTP endpoints |
| `tests/unit/test_workflows.py` | Unit tests for workflows router |
| `tests/unit/test_workflow_executions.py` | Unit tests for workflow_executions router |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/api/routers/__init__.py` | Import + include both new routers |
| `src/main.py` | `app.include_router(workflows.router)` + `workflow_executions.router` (if not done in __init__.py) |

### 3.3 新增能力

- **API endpoint**：`GET /workflows/?page=1&page_size=20` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`POST /workflows/` body `{name, trigger_type, ...}` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /workflows/{workflow_id}` → `{"success": true, "data": {...}}`
- **API endpoint**：`DELETE /workflows/{workflow_id}` → `{"success": true, "data": null}`
- **API endpoint**：`POST /workflows/{workflow_id}/publish` → `{"success": true, "data": {...}}`
- **API endpoint**：`POST /workflows/{workflow_id}/trigger-test` body `{mock_payload}` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /workflow-executions/?workflow_id=&page=1&page_size=20` → paginated list
- **API endpoint**：`GET /workflow-executions/{execution_id}` → single execution
- **API endpoint**：`GET /workflow-executions/{execution_id}/logs` → node-by-node status/input/output
- **API endpoint**：`POST /workflow-executions/{execution_id}/retry` → full retry
- **API endpoint**：`POST /workflow-executions/{execution_id}/retry/{node_id}` → retry from specific node

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **All endpoints use query/path `tenant_id` from AuthContext, not from request body** — `tenant_id` is a server-side concept derived from the JWT token via `require_auth` dependency; it is never accepted from the client
- **Trigger-test uses mock payload, not a real event** — a dedicated `trigger_test` service method accepts a `dict` payload and simulates execution without persisting a real `WorkflowExecution` record (or persists a special `status=test` record if the service requires it)
- **Retry has two forms: full retry and node-specific retry** — node-specific retry passes `from_node_id: int | None` to the service so it can skip already-succeeded nodes

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- Multi-tenant: every service call passes `tenant_id` from `ctx.tenant_id` (AuthContext)
- Router injects session via `session: AsyncSession = Depends(get_db)` — never `async with get_db()`
- Router calls service, receives ORM objects, serializes via `.to_dict()`, wraps in `{"success": True, "data": ...}`
- Service raises `AppException` subclasses on error; router has no try/catch (global handler covers it)
- Router imports use `from api.routers.xxx` not `from src.api.routers.xxx`

### 4.4 已知坑

1. **Alembic autogenerate emits `sa.JSON()` instead of `sa.JSONB()` for JSON columns** — #520 migration may contain JSON columns; if so, verify they are `JSONB` before committing
2. **Session injection pattern** — `async with get_db() as session:` in router methods crashes at runtime; must use `session: AsyncSession = Depends(get_db)`
3. **Workflow execution logs may contain large JSON blobs** — paginate logs endpoint by node, not by character offset

---

## 5. 实现步骤（按顺序）

### Step 1: Read #520 service layer output

Read `src/services/workflow_service.py` and `src/services/workflow_execution_service.py` (or their paths after #520 lands) to confirm method names and signatures before writing routers.

操作：
- a) 确定 `WorkflowService` 的公开方法列表（list/create/get/delete/publish/trigger_test）
- b) 确定 `WorkflowExecutionService` 的公开方法列表（list/get/logs/retry）
- c) 确定 ORM model names（`WorkflowModel`, `WorkflowExecutionModel`）及其 `.to_dict()` shape

**完成判定**：文件 `src/services/workflow_service.py` 和 `src/services/workflow_execution_service.py` 存在且可读

---

### Step 2: Create workflows router

创建 `src/api/routers/workflows.py` with all workflow endpoints.

操作：
- a) Write `from api.routers import APIRouter, Depends, require_auth` + imports for service and session
- b) Implement `GET /` — `svc.list_workflows(tenant_id=ctx.tenant_id, page=page, page_size=page_size)` → paginated list
- c) Implement `POST /` — `svc.create_workflow(tenant_id=ctx.tenant_id, **body)` → ORM object → `.to_dict()`
- d) Implement `GET /{workflow_id}` — `svc.get_workflow(workflow_id, tenant_id=ctx.tenant_id)` → single object
- e) Implement `DELETE /{workflow_id}` — `svc.delete_workflow(workflow_id, tenant_id=ctx.tenant_id)` → null data
- f) Implement `POST /{workflow_id}/publish` — `svc.publish_workflow(workflow_id, tenant_id=ctx.tenant_id)` → result
- g) Implement `POST /{workflow_id}/trigger-test` — `svc.trigger_test(workflow_id, tenant_id=ctx.tenant_id, payload=body.get("payload"))` → test result

```python
router = APIRouter(prefix="/workflows", tags=["Workflows"])

@router.get("/")
async def list_workflows(
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = WorkflowService(session)
    items, total = await svc.list_workflows(tenant_id=ctx.tenant_id, page=page, page_size=page_size)
    return {
        "success": True,
        "data": {"items": [i.to_dict() for i in items], "total": total, "page": page, "page_size": page_size},
    }
```

**完成判定**：`ruff check src/api/routers/workflows.py` exit 0

---

### Step 3: Create workflow_executions router

创建 `src/api/routers/workflow_executions.py` with execution log and retry endpoints.

操作：
- a) Write router with prefix `/workflow-executions` and tag `["Workflow Executions"]`
- b) Implement `GET /` — filter by `workflow_id` query param + tenant_id → paginated list
- c) Implement `GET /{execution_id}` — single execution with status
- d) Implement `GET /{execution_id}/logs` — node-by-node status/input/output list
- e) Implement `POST /{execution_id}/retry` — `svc.retry_execution(execution_id, tenant_id=ctx.tenant_id)`
- f) Implement `POST /{execution_id}/retry/{node_id}` — `svc.retry_execution(execution_id, from_node_id=node_id, tenant_id=ctx.tenant_id)`

```python
@router.get("/{execution_id}/logs")
async def get_execution_logs(
    execution_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = WorkflowExecutionService(session)
    logs = await svc.get_execution_logs(execution_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": [log.to_dict() for log in logs]}
```

**完成判定**：`ruff check src/api/routers/workflow_executions.py` exit 0

---

### Step 4: Register routers in `__init__.py`

在 `src/api/routers/__init__.py` 中添加两个 router 的 import 和 include。

操作：
- a) 添加 `from api.routers.workflows import router as workflows_router`
- b) 添加 `from api.routers.workflow_executions import router as workflow_executions_router`
- c) 如果 `__init__.py` has a combined `router` object, compose both into it

示例代码：

```python
from api.routers.workflows import router as workflows_router
from api.routers.workflow_executions import router as workflow_executions_router

__all__ = [
    ...
    "workflows_router",
    "workflow_executions_router",
]
```

**完成判定**：`ruff check src/api/routers/__init__.py` exit 0

---

### Step 5: Write unit tests for workflows router

创建 `tests/unit/test_workflows.py` using `MockRow`/`MockResult`/`MockState` pattern from `tests/unit/conftest.py`.

操作：
- a) 定义 `mock_db_session` fixture with workflow service handler
- b) 测试 `GET /workflows/` 返回正确 envelope
- c) 测试 `POST /workflows/` 创建 workflow 并返回 ORM 序列化结果
- d) 测试 `GET /workflows/{id}` 找不到时抛出 `NotFoundException`
- e) 测试 `DELETE /workflows/{id}` 返回 `data: null`
- f) 测试 `POST /workflows/{id}/publish` 和 `POST /workflows/{id}/trigger-test`

```python
from tests.unit.conftest import make_mock_session, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_workflow_handler(state)])

@pytest.fixture
def client(mock_db_session):
    from api.routers.workflows import router
    # mount router in TestClient ...
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflows.py -v` → 全部 passed

---

### Step 6: Write unit tests for workflow_executions router

创建 `tests/unit/test_workflow_executions.py` following the same fixture pattern.

操作：
- a) 定义 `mock_db_session` fixture with execution service handler
- b) 测试 `GET /workflow-executions/` 分页 + 按 workflow_id 过滤
- c) 测试 `GET /workflow-executions/{id}/logs` 返回节点列表
- d) 测试 `POST /workflow-executions/{id}/retry` 全重试
- e) 测试 `POST /workflow-executions/{id}/retry/{node_id}` 节点级重试
- f) 测试 `NotFoundException` 路径

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_executions.py -v` → 全部 passed

---

### Step 7: Verify full test suite + lint

运行完整 lint + unit 测试。

操作：
- a) `ruff check src/api/routers/workflows.py src/api/routers/workflow_executions.py src/api/routers/__init__.py`
- b) `PYTHONPATH=src pytest tests/unit/test_workflows.py tests/unit/test_workflow_executions.py -v`

**完成判定**：ruff exit 0 + pytest all passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/workflows.py src/api/routers/workflow_executions.py src/api/routers/__init__.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflows.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_executions.py -v` → all passed
- [ ] All 10 endpoints have at least one unit test covering the success path
- [ ] Every service call passes `tenant_id=ctx.tenant_id`
- [ ] All responses use `{"success": true, "data": ...}` envelope (not bare dict)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #520 service layer not ready at merge time, routers import fails | 低 | 中 | Block router PR until #520 lands; rebase after #520 merge |
| Service method signatures differ from expected (e.g. `page` param missing) | 中 | 高 | Update router call sites to match actual signatures from #520 code review |
| `tenant_id` accidentally omitted from one endpoint's service call | 中 | 高 | Unit test coverage catches this; add integration test in #520 if absent |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/workflows.py src/api/routers/workflow_executions.py \
       src/api/routers/__init__.py \
       tests/unit/test_workflows.py tests/unit/test_workflow_executions.py
git commit -m "feat(automation): add workflow API routers

- GET/POST/DELETE /workflows/
- POST /workflows/{id}/publish, /trigger-test
- GET/POST /workflow-executions/ with logs and retry

Closes #521"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): add workflow API routers (#521)" --body "Closes #521"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/api/routers/customers.py` — router pattern with pagination, AuthContext, `.to_dict()` envelope
- 同类参考实现：`src/api/routers/tickets.py` — DELETE returns `data: null` pattern
- 父 issue：#73
- 关联依赖：#520
- 后续赋能：#522

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
