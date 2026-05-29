# 0686-add-automation-rules-router · Add CRUD REST endpoints for automation rules

| 元数据 | 值 |
|---|---|
| 周次 | W13.1 |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0687-build-rule-execution-engine-and-trigger-dispatch](../issues/0687-build-rule-execution-engine-and-trigger-dispatch.md), [0688-add-integration-tests-for-full-rule-lifecycle](../issues/0688-add-integration-tests-for-full-rule-lifecycle.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #686 wires up the REST API layer for automation rules. The `AutomationService` (CRUD + trigger dispatch) was built in the ORM integration phase; without a router, those capabilities are inaccessible to API clients. This board adds all required CRUD endpoints following the project's FastAPI router pattern, enabling the front-end and downstream services to manage automation rules programmatically.

### 1.2 做完后

- **用户视角**：API clients can create, list, retrieve, update, delete, and activate/deactivate automation rules via standard REST verbs at `/api/v1/automation/rules`.
- **开发者视角**：New `automation_rules_router` is auto-discovered by `iter_routers()` in `src/api/__init__.py` and registered with FastAPI — no `main.py` changes required. Each endpoint calls `AutomationService`, serializes with `.to_dict()`, and wraps in `ApiResponse` envelope.

### 1.3 不做什么（剔除）

- [ ] No execution engine wiring — `RuleEngine` dispatch integration is covered by #687.
- [ ] No new ORM models — `AutomationRuleModel` / `AutomationLogModel` are handled by the ORM integration board.
- [ ] No webhook trigger endpoint beyond the existing `POST /automation/trigger`.

### 1.4 关键 KPI

- `ruff check src/api/routers/automation_rules.py` → zero warnings/errors.
- `ruff check tests/unit/test_automation_rules_router.py` → zero warnings/errors.
- `PYTHONPATH=src pytest tests/unit/test_automation_rules_router.py -v` → ≥ 10 passed.
- All 6 endpoints respond with correct HTTP status codes (201 create, 200 ok, 404 not found, 204 delete).
- Every endpoint enforces `tenant_id` isolation via `require_auth`.

---

## 2. 当前现状（起点）

### 2.1 现有实现

The automation rules REST surface partially exists at [`src/api/routers/automation.py`](../../src/api/routers/automation.py) L1-L210. However, the file is named `automation.py` and uses `POST /rules/{rule_id}/toggle` (PATCH is required by the issue spec). All service-layer logic (`AutomationService`) is complete and tested.

主入口：[`src/api/routers/automation.py`](../../src/api/routers/automation.py) L1-L210

```startLine:76:src/api/routers/automation.py
@automation_router.post("/rules", status_code=201)
async def create_automation_rule(
    rule: AutomationRuleCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a new automation rule."""
    service = AutomationService(session)
    result = await service.create_rule(
        tenant_id=ctx.tenant_id,
        name=rule.name,
        description=rule.description,
        trigger_event=rule.trigger_event,
        conditions=[c.model_dump() for c in rule.conditions],
        actions=[a.model_dump() for a in rule.actions],
        enabled=rule.enabled,
        created_by=ctx.user_id,
    )
    return {"success": True, "data": result.to_dict(), "message": "自动化规则创建成功"}
```

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/automation.py`](../../src/api/routers/automation.py) — 重命名为 `automation_rules.py`；修正 toggle 为 `PATCH`；移除已在本板块覆盖的端点（保留 `/trigger` 和 `/logs` 端点不迁移）
- 要建：
  - `src/api/routers/automation_rules.py` — 全新模块，包含 POST/GET/PUT/DELETE/PATCH 端点（迁移自 `automation.py` 并修正 toggle 方法）
  - `tests/unit/test_automation_rules_router.py` — 路由层单元测试

### 2.3 缺什么

- [ ] `automation_rules.py` router does not exist (only `automation.py`).
- [ ] Toggle endpoint uses `POST` instead of `PATCH` — PATCH is the correct HTTP verb for partial activate/deactivate.
- [ ] No unit tests for the router layer (`test_automation_rules_router.py`).
- [ ] Router auto-discovery (`src/api/__init__.py`) will pick up `automation_rules.py` automatically; `main.py` needs no changes.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|-------|
| `src/api/routers/automation_rules.py` | CRUD router for automation rules: POST (create), GET / (list), GET /{rule_id}, PUT /{rule_id}, DELETE /{rule_id}, PATCH /{rule_id}/activate |
| `tests/unit/test_automation_rules_router.py` | Router-layer unit tests using mock DB session |
| `docs/dev-plan/issues/0686_verify.sh` | Acceptance script: ruff check + pytest |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/automation.py`](../../src/api/routers/automation.py) | 重命名为 `automation_rules.py`（文件系统 rename）；`POST /rules/{rule_id}/toggle` 改为 `PATCH /rules/{rule_id}/activate` |

### 3.3 新增能力

- **API endpoint**: `POST /api/v1/automation/rules` → `{"success": true, "data": {...}}`
- **API endpoint**: `GET /api/v1/automation/rules` → paginated `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**: `GET /api/v1/automation/rules/{rule_id}` → `{"success": true, "data": {...}}`
- **API endpoint**: `PUT /api/v1/automation/rules/{rule_id}` → `{"success": true, "data": {...}}`
- **API endpoint**: `DELETE /api/v1/automation/rules/{rule_id}` → `{"success": true, "data": {"id": N}}`
- **API endpoint**: `PATCH /api/v1/automation/rules/{rule_id}/activate` → `{"success": true, "data": {...}}`
- **verify 脚本**: `bash docs/dev-plan/issues/0686_verify.sh`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 PATCH 而非 POST for toggle**: HTTP semantics require PATCH for partial resource modification. The existing `automation.py` used POST incorrectly; the new `automation_rules.py` corrects this to PATCH.
- **选保留 automation.py 中的 /trigger 和 /logs 端点**: These are execution-plane endpoints (rule firing, log reading) distinct from CRUD. Keeping them in the original file avoids breaking `automation.py`-based imports and maintains separation of concerns.

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pytest-asyncio` | `≥0.23` | pyproject.toml 已锁定；async router test fixtures 需要 |
| `sqlalchemy` | `2.x` | 项目已锁定 2.x async API |
| `fastapi` | `≥0.110` | pyproject.toml 已要求 |

### 4.3 兼容性约束

- `AutomationService` method signatures must not change; this board only wraps them in router endpoints.
- Tenant isolation via `require_auth` is mandatory — every endpoint must pass `tenant_id=ctx.tenant_id`.
- Response envelope `{"success": True, "data": ...}` is mandatory for all success responses.

### 4.4 已知坑

1. **`AutomationService.toggle_rule` uses `scalar_one()` but returns no row** → Symptom: `sqlalchemy.exc.NoResultFound` raised at runtime. Fix: the `AutomationService.update_rule` RETURNING query must be verified; if `toggle_rule` returns a row directly it is correct, but `get_rule` used first then update must ensure the RETURNING stmt actually returns a row.
2. **`automation.py` rename may leave stale import references** → Symptom: other files import `from api.routers.automation import automation_router`. Fix: search for all references before renaming and update them atomically.
3. **Double-binding if both `automation.py` and `automation_rules.py` are present** → Symptom: duplicate route registration. Fix: `automation.py` must be deleted (not just renamed in git, but the file content removed) before `automation_rules.py` is created.

---

## 5. 实现步骤（按顺序）

### Step 1: Create src/api/routers/automation_rules.py with all CRUD endpoints

Create the new router file based on the existing `automation.py` pattern, correcting the toggle endpoint from `POST` to `PATCH`, and including only the CRUD endpoints (not `/trigger` or `/logs`).

操作：
- a) Create `src/api/routers/automation_rules.py`
- b) Copy all Pydantic request/response schemas from `automation.py` (`ConditionItem`, `ActionItem`, `AutomationRuleCreate`, `AutomationRuleUpdate`)
- c) Implement `POST /rules` → `AutomationService.create_rule`
- d) Implement `GET /rules` → `AutomationService.list_rules` with `_paginated` helper
- e) Implement `GET /rules/{rule_id}` → `AutomationService.get_rule`
- f) Implement `PUT /rules/{rule_id}` → `AutomationService.update_rule`
- g) Implement `DELETE /rules/{rule_id}` → `AutomationService.delete_rule`
- h) Implement `PATCH /rules/{rule_id}/activate` → `AutomationService.toggle_rule`
- i) Ensure all endpoints use `ctx: AuthContext = Depends(require_auth)` and pass `tenant_id=ctx.tenant_id`
- j) Add `automation_rules_router = APIRouter(...)` as the exported router

示例代码：

```python
"""Automation rules router — /api/v1/automation/rules CRUD endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router serializes ORM objects via .to_dict().
"""

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.automation_service import AutomationService

automation_rules_router = APIRouter(prefix="/api/v1/automation", tags=["automation-rules"])


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


class ConditionItem(BaseModel):
    field: str = Field(..., min_length=1, max_length=100)
    operator: str = Field(..., min_length=1, max_length=20)
    value: str = Field(...)


class ActionItem(BaseModel):
    type: str = Field(..., min_length=1, max_length=50)
    params: dict = Field(default_factory=dict)


class AutomationRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    trigger_event: str = Field(..., min_length=1, max_length=100)
    conditions: list[ConditionItem] = Field(default_factory=list)
    actions: list[ActionItem] = Field(..., min_length=1)
    enabled: bool = Field(default=True)


class AutomationRuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=2000)
    trigger_event: str | None = Field(None, max_length=100)
    conditions: list[ConditionItem] | None = Field(None)
    actions: list[ActionItem] | None = Field(None)
    enabled: bool | None = Field(None)


@automation_rules_router.post("/rules", status_code=201)
async def create_automation_rule(
    rule: AutomationRuleCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a new automation rule."""
    service = AutomationService(session)
    result = await service.create_rule(
        tenant_id=ctx.tenant_id,
        name=rule.name,
        description=rule.description,
        trigger_event=rule.trigger_event,
        conditions=[c.model_dump() for c in rule.conditions],
        actions=[a.model_dump() for a in rule.actions],
        enabled=rule.enabled,
        created_by=ctx.user_id,
    )
    return {"success": True, "data": result.to_dict(), "message": "自动化规则创建成功"}


@automation_rules_router.get("/rules")
async def list_automation_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    trigger_event: str | None = Query(None),
    enabled: bool | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List automation rules for the tenant."""
    service = AutomationService(session)
    items, total = await service.list_rules(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        trigger_event=trigger_event,
        enabled=enabled,
    )
    return _paginated(items, total, page, page_size)


@automation_rules_router.get("/rules/{rule_id}")
async def get_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get a specific automation rule."""
    service = AutomationService(session)
    rule = await service.get_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": rule.to_dict()}


@automation_rules_router.put("/rules/{rule_id}")
async def update_automation_rule(
    rule_id: int,
    rule: AutomationRuleUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Update an automation rule."""
    service = AutomationService(session)
    update_data = rule.model_dump(exclude_unset=True)
    if "conditions" in update_data and update_data["conditions"] is not None:
        update_data["conditions"] = [dict(c) if hasattr(c, "model_dump") else c for c in update_data["conditions"]]
    if "actions" in update_data and update_data["actions"] is not None:
        update_data["actions"] = [dict(a) if hasattr(a, "model_dump") else a for a in update_data["actions"]]
    result = await service.update_rule(rule_id=rule_id, tenant_id=ctx.tenant_id, **update_data)
    return {"success": True, "data": result.to_dict(), "message": "自动化规则更新成功"}


@automation_rules_router.delete("/rules/{rule_id}")
async def delete_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete an automation rule."""
    service = AutomationService(session)
    deleted_id = await service.delete_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"id": deleted_id}, "message": "自动化规则删除成功"}


@automation_rules_router.patch("/rules/{rule_id}/activate")
async def activate_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Toggle activation state (enabled/disabled) of an automation rule."""
    service = AutomationService(session)
    rule = await service.toggle_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": rule.to_dict(), "message": "自动化规则状态已切换"}
```

**完成判定**：`ruff check src/api/routers/automation_rules.py` 输出无错误

### Step 2: Replace automation.py content with stub (keep /trigger and /logs)

The existing `automation.py` must be kept to avoid breaking any external references, but its CRUD endpoints are migrated. Replace its content so only `/trigger` and `/logs` remain.

操作：
- a) Read `src/api/routers/automation.py`
- b) Remove all CRUD endpoint functions (create, list, get, update, delete, toggle) and Pydantic schemas (ConditionItem, ActionItem, AutomationRuleCreate, AutomationRuleUpdate, TriggerEventRequest)
- c) Keep only `automation_router`, `_paginated`, `TriggerEventRequest`, `/trigger` endpoint, and `/logs` endpoint
- d) Save the modified file

在 `src/api/routers/automation.py` 中删除 L76-L174（所有 CRUD + toggle 端点），保留 `_paginated` helper 和 `/trigger`/`/logs` 端点。

**完成判定**：`ruff check src/api/routers/automation.py` 输出无错误；`grep -c "router" src/api/routers/automation.py` 显示文件中只有 `automation_router`

### Step 3: Create tests/unit/test_automation_rules_router.py

Create a router-layer unit test file. Each test mocks the service layer (`AutomationService`) directly rather than the database, using `unittest.mock.AsyncMock`.

操作：
- a) Create `tests/unit/test_automation_rules_router.py`
- b) Add module docstring and `from __future__ import annotations`
- c) Import `AutomationService`, `automation_rules_router`, request-building helpers
- d) Write fixture `mock_service` that patches `AutomationService.__init__` to return a mock
- e) Write `TestCreateAutomationRule` — happy path (returns 201 + `success: true`), validation error (empty name returns 422)
- f) Write `TestListAutomationRules` — returns paginated `items` list with correct total
- g) Write `TestGetAutomationRule` — returns rule dict; raises `NotFoundException` → 404
- h) Write `TestUpdateAutomationRule` — partial update; 404 on missing rule
- i) Write `TestDeleteAutomationRule` — returns `{"id": rule_id}`; 404 on missing rule
- j) Write `TestActivateAutomationRule` — calls `toggle_rule`, returns updated rule dict

```python
"""Unit tests for automation_rules_router — HTTP layer.

Run with:
    PYTHONPATH=src pytest tests/unit/test_automation_rules_router.py -v
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routers.automation_rules import automation_rules_router
from pkg.errors.app_exceptions import NotFoundException


@pytest.fixture
def mock_service():
    """Patch AutomationService so router calls never hit the DB."""
    with patch("api.routers.automation_rules.AutomationService") as MockSvc:
        svc_instance = MagicMock()
        svc_instance.create_rule = AsyncMock()
        svc_instance.list_rules = AsyncMock()
        svc_instance.get_rule = AsyncMock()
        svc_instance.update_rule = AsyncMock()
        svc_instance.delete_rule = AsyncMock()
        svc_instance.toggle_rule = AsyncMock()
        MockSvc.return_value = svc_instance
        yield svc_instance


class TestCreateAutomationRule:
    async def test_create_returns_201_and_success_envelope(self, mock_service):
        rule_mock = MagicMock()
        rule_mock.to_dict.return_value = {"id": 1, "name": "Test Rule", "enabled": True}
        mock_service.create_rule.return_value = rule_mock

        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        # Override dependency to inject fake auth context
        from fastapi import Depends
        from internal.middleware.fastapi_auth import AuthContext

        def fake_auth():
            return AuthContext(tenant_id=1, user_id=1)

        for route in app.routes:
            if hasattr(route, "dependant"):
                for dep in route.dependant.dependencies:
                    if dep.name == "ctx":
                        dep.call = fake_auth

        response = client.post(
            "/api/v1/automation/rules",
            json={
                "name": "Test Rule",
                "trigger_event": "ticket.created",
                "actions": [{"type": "notification.send", "params": {}}],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["name"] == "Test Rule"

    async def test_create_with_empty_name_returns_422(self, mock_service):
        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/automation/rules",
            json={
                "name": "",
                "trigger_event": "ticket.created",
                "actions": [{"type": "notification.send", "params": {}}],
            },
        )
        assert response.status_code == 422


class TestListAutomationRules:
    async def test_list_returns_paginated_items(self, mock_service):
        item_a = MagicMock()
        item_a.to_dict.return_value = {"id": 1, "name": "Rule A"}
        item_b = MagicMock()
        item_b.to_dict.return_value = {"id": 2, "name": "Rule B"}
        mock_service.list_rules.return_value = ([item_a, item_b], 2)

        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/v1/automation/rules?page=1&page_size=20")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) == 2
        assert data["data"]["total"] == 2


class TestGetAutomationRule:
    async def test_get_returns_rule_dict(self, mock_service):
        rule_mock = MagicMock()
        rule_mock.to_dict.return_value = {"id": 5, "name": "Rule Five"}
        mock_service.get_rule.return_value = rule_mock

        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/v1/automation/rules/5")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == 5

    async def test_get_missing_rule_returns_404(self, mock_service):
        mock_service.get_rule.side_effect = NotFoundException("规则")

        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/v1/automation/rules/9999")
        assert response.status_code == 404


class TestUpdateAutomationRule:
    async def test_update_returns_updated_rule(self, mock_service):
        updated = MagicMock()
        updated.to_dict.return_value = {"id": 3, "name": "Updated Name"}
        mock_service.update_rule.return_value = updated

        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put("/api/v1/automation/rules/3", json={"name": "Updated Name"})
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Updated Name"


class TestDeleteAutomationRule:
    async def test_delete_returns_deleted_id(self, mock_service):
        mock_service.delete_rule.return_value = 7

        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.delete("/api/v1/automation/rules/7")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == 7

    async def test_delete_missing_rule_returns_404(self, mock_service):
        mock_service.delete_rule.side_effect = NotFoundException("规则")

        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.delete("/api/v1/automation/rules/9999")
        assert response.status_code == 404


class TestActivateAutomationRule:
    async def test_activate_toggles_enabled_state(self, mock_service):
        toggled = MagicMock()
        toggled.to_dict.return_value = {"id": 4, "name": "Toggle Test", "enabled": True}
        mock_service.toggle_rule.return_value = toggled

        from fastapi.testclient import TestClient
        from main import app

        app.include_router(automation_rules_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.patch("/api/v1/automation/rules/4/activate")
        assert response.status_code == 200
        assert response.json()["data"]["enabled"] is True
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_rules_router.py -v` 输出 ≥ 10 passed

### Step 4: Write acceptance script docs/dev-plan/issues/0686_verify.sh

Create the verification shell script.

操作：
- a) Create `docs/dev-plan/issues/0686_verify.sh`
- b) Add `set -e`
- c) Run `ruff check` on the new router and test file
- d) Run `ruff format --check`
- e) Run pytest

```bash
#!/usr/bin/env bash
set -e

export PYTHONPATH=src

echo "=== ruff check ==="
ruff check src/api/routers/automation_rules.py tests/unit/test_automation_rules_router.py

echo "=== ruff format check ==="
ruff format --check src/api/routers/automation_rules.py tests/unit/test_automation_rules_router.py

echo "=== pytest ==="
pytest tests/unit/test_automation_rules_router.py -v
```

**完成判定**：`bash docs/dev-plan/issues/0686_verify.sh` exits 0

---

## 6. 验收

- [ ] `ruff check src/api/routers/automation_rules.py` 输出无错误
- [ ] `ruff format --check src/api/routers/automation_rules.py` 输出无错误
- [ ] `ruff check tests/unit/test_automation_rules_router.py` 输出无错误
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_rules_router.py -v` 输出 ≥ 10 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_rules_router.py -v` 中 Happy path test → `status_code == 201`
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_rules_router.py -v` 中 Missing rule tests → `status_code == 404`
- [ ] `grep -n "router" src/api/routers/automation_rules.py` 输出包含 `automation_rules_router = APIRouter`
- [ ] `grep -n "PATCH.*activate" src/api/routers/automation_rules.py` 输出包含 `patch`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `automation.py` 删除/修改导致已有集成断裂 | 低 | 高 | 保留 `automation.py` 仅移除 CRUD 端点，保留 `/trigger` 和 `/logs`；如断裂，先 revert `automation.py` 变更 |
| `AutomationService.toggle_rule` 使用 `scalar_one()` 且 RETURNING 语句无结果行时抛异常 | 低 | 中 | 在 `AutomationService.toggle_rule` 中捕获异常并 raise `NotFoundException("规则")` |
| TestClient fixture 共享 `app` 状态导致路由重复注册 | 低 | 低 | 每个测试类独立 `with TestClient(app)` 或使用 function-scoped app fixture |

---

## 8. 完成后必做

```bash
# 1. commit
git add src/api/routers/automation_rules.py tests/unit/test_automation_rules_router.py src/api/routers/automation.py docs/dev-plan/issues/0686_verify.sh && git commit -m "feat(automation): add automation_rules router with CRUD endpoints (#686)"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §4 全局进度表本行
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# ✅ [0686] Add automation rules router 完成 (W13.1)
# - PR/Commit: <link>
# - 关键产物: src/api/routers/automation_rules.py, tests/unit/test_automation_rules_router.py
# - 验收: pytest tests/unit/test_automation_rules_router.py 全绿 ✓ (≥10 passed)
# - 下一步赋能: #0687 build-rule-execution-engine, #0688 integration-tests

# 4. 如果加了新 stage（部署阶段）
# - 改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- 父任务：[#33 automation test coverage gap](https://github.com/YOUR_ORG/YOUR_REPO/issues/33)
- 上游（并行）：[0687-build-rule-execution-engine-and-trigger-dispatch](../issues/0687-build-rule-execution-engine-and-trigger-dispatch.md)
- 项目内：[`src/api/routers/automation.py`](../../src/api/routers/automation.py) — existing router with CRUD endpoints (source for copy)
- 项目内：[`src/services/automation_service.py`](../../src/services/automation_service.py) — AutomationService implementation
- 项目内：[`src/api/__init__.py`](../../src/api/__init__.py) — router auto-discovery (`iter_routers`)
- 项目内：[`src/main.py`](../../src/main.py) — global exception handler and app factory
- 下游：[`0687-build-rule-execution-engine-and-trigger-dispatch.md`](../../docs/dev-plan/issues/0687-build-rule-execution-engine-and-trigger-dispatch.md) — rule engine that calls router-wired services
- 下游：[`0688-add-integration-tests-for-full-rule-lifecycle.md`](../../docs/dev-plan/issues/0688-add-integration-tests-for-full-rule-lifecycle.md)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | github-actions[bot] |
