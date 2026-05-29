# Webhook Router · Add webhook REST API endpoints

---

## 1. 目标与背景

### 1.1 为什么做

Issue #78 (Automation Platform) requires a public REST API surface for the webhook subsystem. Issue #496 built the service layer (`WebhookService`, `WebhookDeliveryService`). This board wires those services to HTTP endpoints, adding auth-gated CRUD and two operational endpoints (test-deliver and delivery-log). Without this, the webhook subsystem has no user-facing API and cannot be integrated by frontend or external consumers.

###1.2 做完后

- **用户视角**：无直接用户可见变化 — this board exposes an internal REST API consumed by the frontend (or external clients). The frontend automation pages gain working Create / List / Delete / Test controls.
- **开发者视角**：New `WebhookRouter` at `src/api/routers/webhook.py` provides 5 typed endpoints. All routes require `AuthContext` (JWT). Services are reused verbatim from issue #496.

### 1.3 不做什么（剔除）

- [ ] New database models (already covered by #496)
- [ ] Webhook delivery execution / HTTP outbound (event dispatcher lives in a separate board)
- [ ] Batch retry of failed deliveries
- [ ] Webhook schema validation via external registry### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_webhook_router.py -v` → all passed
- `ruff check src/api/routers/webhook.py src/main.py` → 0 errors
- All5 endpoints registered in `main.py` and return `{"success": true, "data": ...}` envelope
- `GET /webhooks/{id}/deliveries` returns only deliveries for the target webhook's `tenant_id`

---

## 2. 当前现状（起点）

### 2.1 现有实现

Issue #496 implemented `WebhookService` and `WebhookDeliveryService`. Those services are the starting point for this board — they exist at `src/services/webhook_service.py` (TBD - 待验证：confirm exact filename from #496 service layer deliverable).

AuthContext middleware exists at `TBD - 待验证：src/internal/middleware/fastapi_auth.py L? — existing JWT auth guard, confirmed from CLAUDE.md` and is already used by other routers in this codebase.

The `src/main.py` router registration pattern is well-established (candidates: `src/api/routers/webhook.py` may already be stubbed by #496; TBD - 待验证：any existing router files in src/api/routers/ for reference on registration style).

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — register `WebhookRouter`
  - `tests/unit/test_webhook_router.py` — unit tests (may be created by #496 or this board)
- 要建：
  - `src/api/routers/webhook.py` — WebhookRouter with 5 endpoints
  - `tests/unit/test_webhook_router.py` — mock service layer tests

### 2.3 缺什么

- [ ] `POST /webhooks` endpoint (create a webhook)
- [ ] `GET /webhooks` endpoint (list webhooks)
- [ ] `DELETE /webhooks/{id}` endpoint (delete a webhook)
- [ ] `GET /webhooks/{id}/deliveries` endpoint (list recent deliveries)
- [ ] `POST /webhooks/{id}/test` endpoint (dispatch sample payload)
- [ ] `WebhookRouter` registration in `mainAPIRouter`
- [ ] Auth guard (`AuthContext`) wiring on all 5 endpoints

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/webhook.py` | WebhookRouter with `POST /webhooks`, `GET /webhooks`, `DELETE /webhooks/{id}`, `GET /webhooks/{id}/deliveries`, `POST /webhooks/{id}/test` |
| `tests/unit/test_webhook_router.py` | Unit tests via pytest; mocks `WebhookService` / `WebhookDeliveryService` at service layer using `make_mock_session` from `tests/unit/conftest.py` |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| `src/main.py` | Import `WebhookRouter`, include it in `api_router` with prefix `/webhooks` |

### 3.3 新增能力

- **API endpoint**: `POST /webhooks` → create (requires body: `url`, `event_types[]`, optional `headers`)
- **API endpoint**: `GET /webhooks` → paginated list filtered by `tenant_id`
- **API endpoint**: `DELETE /webhooks/{id}` → hard-delete; returns 404 on not found or wrong tenant
- **API endpoint**: `GET /webhooks/{id}/deliveries` → recent deliveries for the webhook- **API endpoint**: `POST /webhooks/{id}/test` → dispatch a sample payload immediately- **Router**: `WebhookRouter` registered in `main.py`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Reuse services from #496, not re-implementing** — avoids duplicating business logic; router only provides HTTP serialization and auth wiring. Services are the source of truth for tenant scoping.
- **Mock at service layer in unit tests** — `WebhookService` / `WebhookDeliveryService` are mocked so tests are fast (<5 s) without a real DB. Integration tests (if any) use real Postgres fixtures.
- **Auth via existing `AuthContext` dependency** — `require_auth` already exists; no new auth code needed.

### 4.2 版本约束

<!-- 没有新依赖时整段删掉。如有，按下表填：-->

No new package dependencies introduced by this board.

### 4.3 兼容性约束

- Every SQL query filters by `tenant_id` via `ctx.tenant_id` (services handle this per CLAUDE.md §Multi-Tenancy)
- `WebhookService` / `WebhookDeliveryService` raise `AppException` subclasses; the global handler in `main.py` converts them. Router does NOT wrap `try/catch`.
- Router NEVER instantiates a service without an injected `AsyncSession` — use `session: AsyncSession = Depends(get_db)`, NOT `async with get_db() as session:`.
- Response envelope: `{"success": true, "data": <payload>}` for2xx; errors are handled by the global `AppException` handler.

### 4.4 已知坑

1. **SQLAlchemy `Base.metadata` naming conflict** → column on ORM models MUST NOT be named `metadata`. Webhook delivery payload columns should use `event_metadata` or `payload`. (N/A if #496 already resolved this; flag here for safety.)
2. **Alembic may emit `sa.JSON()` instead of `sa.JSONB()`** for payload/delivery columns → if migration autogenerates, inspect and correct. (This board does not create migrations, but downstream boards inheriting this schema should check.)
3. **`PYTHONPATH=src`** must be set before every `pytest` / `ruff` invocation in CI and locally.

---

## 5. 实现步骤（按顺序）

### Step 1: Create WebhookRouter skeleton

Create `src/api/routers/webhook.py`. Import `APIRouter`, `Depends`, `AuthContext`, `require_auth`, `get_db`, `WebhookService`, `WebhookDeliveryService`. Define `router = APIRouter(prefix="/webhooks", tags=["Webhook"])`.

Stub all 5 endpoints with `pass` or `return {"success": True, "data": {}}` — enough to verify imports resolve and the file passes `ruff check`.

**完成判定**：`ruff check src/api/routers/webhook.py` → exit 0

### Step 2: Implement POST /webhooks

```python
@router.post("")
async def create_webhook(
    body: CreateWebhookRequest,   # TBD - 待验证：confirm schema exists in src/models/ — may be defined in #496 ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = WebhookService(session)
    webhook = await svc.create(
        url=body.url,
        event_types=body.event_types,
        headers=body.headers,
        tenant_id=ctx.tenant_id,
    )
    return {"success": True, "data": webhook.to_dict()}
```

Raise `ValidationException` for missing URL; return created `webhook.to_dict()`.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_router.py::test_create_webhook -v` → passed

### Step 3: Implement GET /webhooks (list)

```python
@router.get("")
async def list_webhooks(
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = WebhookService(session)
    items, total = await svc.list_webhooks(tenant_id=ctx.tenant_id, page=page, page_size=page_size)
    return {"success": True, "data": {"items": [w.to_dict() for w in items], "total": total, "page": page, "page_size": page_size}}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_router.py::test_list_webhooks -v` → passed

### Step 4: Implement DELETE /webhooks/{id}

```python
@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = WebhookService(session)
    await svc.delete_webhook(webhook_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": None}
```

Service raises `NotFoundException` if `webhook_id` not found or belongs to another `tenant_id`.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_router.py::test_delete_webhook -v` → passed

### Step 5: Implement GET /webhooks/{id}/deliveries

```python
@router.get("/{webhook_id}/deliveries")
async def list_webhook_deliveries(
    webhook_id: int,
    limit: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = WebhookDeliveryService(session)
    items = await svc.list_for_webhook(webhook_id, tenant_id=ctx.tenant_id, limit=limit)
    return {"success": True, "data": {"items": [d.to_dict() for d in items], "limit": limit}}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_router.py::test_list_deliveries -v` → passed

### Step 6: Implement POST /webhooks/{id}/test

```python
@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = WebhookService(session)
    delivery = await svc.send_test_payload(webhook_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": delivery.to_dict()}
```

`send_test_payload` dispatches a sample payload to the webhook URL and records the delivery. Service raises `NotFoundException` if webhook not found.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_router.py::test_test_webhook -v` → passed

### Step 7: Register WebhookRouter in main.py

In `src/main.py`, add import and mount:

```python
from api.routers.webhook import router as webhook_router# ...
api_router.include_router(webhook_router)
```

Ensure `AuthContext` and `require_auth` continue to gate all paths.

**完成判定**：`ruff check src/main.py` → exit 0; the FastAPI app starts without import errors (`PYTHONPATH=src uvicorn src.main:app --check`)

### Step 8: Write remaining unit tests

Write tests covering the full test matrix using the existing `tests/unit/conftest.py` mock helpers: happy-path CRUD, `tenant_id` mismatch returns 404, service raises `NotFoundException` → HTTP 404, service raises `ValidationException` → HTTP 422.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_router.py -v` → all passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/webhook.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_webhook_router.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_webhook_router_integration.py -v` → all passed (real Postgres via docker compose; only if integration test file is created)
- [ ] All 5 endpoints present with correct HTTP verbs and paths in auto-generated OpenAPI schema at `/docs`
- [ ] `POST /webhooks/{id}/test` returns 404 for non-existent webhook (cross-tenant; service raises `NotFoundException` → global handler returns 404)
- [ ] `ruff format --check src/api/routers/webhook.py` → 0 diff (formatted)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#496` service layer not merged before this board closes — router imports fail | 低 | 高 | Gate on waiting for #496; do not merge until #496 is merged |
| `AuthContext` interface changes (e.g., new fields added) | 低 | 中 | Router only reads `ctx.tenant_id`; stable contract per existing routers |
| Tenant isolation bug — delivery list leaks cross-tenant deliveries | 低 | 高 | `WebhookDeliveryService.list_for_webhook` must include `tenant_id` in its SQL WHERE clause; add integration test asserting403 on cross-tenant access |
| New fields added to webhook model (e.g., `is_active`) not wired in router | 中 | 中 | Add a new integration test when model grows; no schema freeze required for API versioning |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/webhook.py src/main.py tests/unit/test_webhook_router.py
git commit -m "feat(webhook): add WebhookRouter with5 REST endpoints"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#497): add webhook router endpoints" --body "Closes #497"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- Parent issue: #78 (Automation Platform)
- Dependency (service layer): #496 (WebhookService + WebhookDeliveryService)
- Auth middleware (existing): TBD - 待验证：src/internal/middleware/fastapi_auth.py — `AuthContext`, `require_auth`
- FastAPI router pattern: TBD - 待验证：src/api/routers/ 下现有 router 文件，注册于 main.py 的参考实现
- SQLAlchemy async session: `src/db/connection.py` — `get_db` dependency

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
