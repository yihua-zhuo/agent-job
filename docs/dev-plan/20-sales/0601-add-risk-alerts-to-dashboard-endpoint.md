# Sales · Add risk-alerts dashboard endpoint

| 元数据 | 值 |
|---|---|
| Issue | #601 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | TBD - 待验证：关联 issue #600 文件路径 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The current CRM exposes opportunities through `/api/v1/sales/opportunities` but provides no dedicated channel to surface at-risk deals. Sales managers must manually scan the full pipeline to identify deals that are overdue, stalled, or flagged as high/medium risk. Issue #600 adds a `risk_level` column to the `opportunities` table; this board wires the new column to a first-class `GET /sales/dashboard/risk-alerts` endpoint that returns only non-low-risk opportunities, grouped by owner, so managers can act immediately without additional filtering.

### 1.2 做完后

- **用户视角**：Sales managers call `GET /api/v1/sales/dashboard/risk-alerts` and receive a JSON list of all opportunities with `risk_level != 'low'`, plus a per-sales-rep count of high-risk items. No UI is included — the endpoint is the data contract.
- **开发者视角**：`SalesService.get_risk_alerts(tenant_id, owner_id?)` returns a `dict` with `alerts: list[dict]` and `by_owner: dict[int, int]`. The new `dashboard.py` router follows the same `{"success": true, "data": {...}}` envelope as the existing sales router.

### 1.3 不做什么（剔除）

- [ ] Adding the `risk_level` column to `OpportunityModel` — this is the subject of issue #600, not this board
- [ ] Building a multi-widget dashboard — only the `risk-alerts` endpoint is in scope
- [ ] Automated alert/notification triggers on risk changes
- [ ] ML-based risk scoring — `risk_level` is written by other services (e.g. `ChurnPredictionService`); this board only reads it

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_dashboard_router.py -v` → ≥ 3 passed
- `ruff check src/api/routers/dashboard.py src/services/sales_service.py` → 0 errors
- Endpoint `GET /api/v1/sales/dashboard/risk-alerts` returns `{"success": true, "data": {"alerts": [...], "by_owner": {...}}}` for an authenticated tenant

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/api/routers/sales.py`](../../../src/api/routers/sales.py) L{1}-L{15}

```python:src/api/routers/sales.py
from services.sales_service import SalesService, _opp_to_dict

sales_router = APIRouter(prefix="/api/v1/sales", tags=["sales"])
```

The sales service at [`src/services/sales_service.py`](../../../src/services/sales_service.py) L{1}-L{45} shows the existing opportunity query pattern using `select(OpportunityModel).where(OpportunityModel.tenant_id == tenant_id)` — no `risk_level` filter exists yet. No dashboard router exists in `src/api/routers/`.

### 2.2 涉及文件清单

- 要改：
  - [`src/services/sales_service.py`](../../../src/services/sales_service.py) — add `get_risk_alerts` method
  - TBD - 待验证：`tests/unit/test_dashboard_router.py` 文件位置（board 将创建此文件）
- 要建：
  - `src/api/routers/dashboard.py` — new router with `GET /sales/dashboard/risk-alerts`
  - `src/services/__init__.py` — add `SalesService` export if not already exported

### 2.3 缺什么

- [ ] `SalesService.get_risk_alerts` — SQL query filtering `risk_level != 'low'` grouped by `owner_id`; does not exist
- [ ] `src/api/routers/dashboard.py` — new router; file does not exist
- [ ] `GET /api/v1/sales/dashboard/risk-alerts` endpoint — not registered in any router
- [ ] Unit tests for risk-alert filtering (high/medium returned, low excluded) — no test file yet
- [ ] `OpportunityModel.risk_level` column — added by #600; this board assumes it exists

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/dashboard.py` | New router: `GET /api/v1/sales/dashboard/risk-alerts` |
| `tests/unit/test_dashboard_router.py` | Unit tests: high/medium returned, low excluded, empty tenant |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/sales_service.py`](../../../src/services/sales_service.py) | Add `get_risk_alerts(self, tenant_id, owner_id?)` method; SQL: `select OpportunityModel` filtered `risk_level != 'low'`, also returns `by_owner` count dict |
| [`src/main.py`](../../../src/main.py) | Register `dashboard_router` with `app.include_router(dashboard_router, prefix="/api/v1")` |

### 3.3 新增能力

- **Service method**：`SalesService.get_risk_alerts(self, tenant_id: int, owner_id: int | None = None) -> dict`
- **API endpoint**：`GET /api/v1/sales/dashboard/risk-alerts` → `{"success": true, "data": {"alerts": [...], "by_owner": {owner_id: count}}}` where each alert is a serialized opportunity dict and `by_owner` maps `owner_id -> high_risk_count`
- **Router**：`dashboard_router` in `src/api/routers/dashboard.py`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Add `get_risk_alerts` to `SalesService` rather than a new `RiskAlertService`**：The risk-alerts query is a filtered view of `opportunities` — the same table that `SalesService` already queries. Co-locating the method avoids duplicating the session/tenant setup and keeps the service count bounded.
- **Return `by_owner` as a plain `dict[int, int]` rather than a list of `{owner_id, count}` objects**：Direct integer mapping is easier for a frontend to consume (e.g. `byOwner[userId]` lookup) and matches the "count of high-risk items per sales rep" requirement in the issue.
- **New `dashboard.py` router rather than adding to `sales.py`**：`sales.py` handles pipeline/opportunity CRUD; a separate `dashboard.py` keeps the namespace clean and makes it easy to add more dashboard widgets (forecast, pipeline stats) without growing the sales router.

### 4.2 版本约束

N/A — no new dependencies introduced.

### 4.3 兼容性约束

- 多租户：all SQL filters must include `WHERE tenant_id = :tenant_id` — mandatory for every query
- `SalesService` methods accept `tenant_id: int` as the first positional argument
- Service returns raw dicts (already the convention in `sales_service.py`); router calls `{"success": True, "data": ...}` envelope
- Service errors raise `AppException` subclasses caught by the global handler in `main.py`; no `try/except` in the router

### 4.4 已知坑

1. **If `OpportunityModel` has no `risk_level` column, the query will raise `AttributeError`** → Mitigation: This board depends on #600 completing first; `alembic upgrade head` from #600 must be run before running tests for this board.
2. **`risk_level` values are free-form strings with no DB enum** → Mitigation: the SQL filter uses `OpportunityModel.risk_level != 'low'` (string literal); no assumption is made about the values for `high` vs `medium` — both are included by excluding only `low`.
3. **Async session injection: do NOT use `async with get_db()`** → Use `session: AsyncSession = Depends(get_db)` in the router endpoint; `get_db` is a generator but FastAPI resolves it correctly via the dependency injection system.

---

## 5. 实现步骤（按顺序）

### Step 1: Add `get_risk_alerts` to `SalesService`

在 `src/services/sales_service.py` 末尾（`get_forecast` 方法之后）插入：

```python
async def get_risk_alerts(self, tenant_id: int = 0, owner_id: int | None = None) -> dict:
    """Return all opportunities with risk_level != 'low', grouped by owner."""
    conditions = [
        OpportunityModel.tenant_id == tenant_id,
        OpportunityModel.risk_level.isnot(None),
        OpportunityModel.risk_level != "low",
    ]
    if owner_id is not None:
        conditions.append(OpportunityModel.owner_id == owner_id)

    result = await self.session.execute(
        select(OpportunityModel)
        .where(and_(*conditions))
        .order_by(OpportunityModel.updated_at.desc())
    )
    opportunities = result.scalars().all()

    alerts = [_opp_to_dict(o) for o in opportunities]

    # Count high-risk per owner (severity of 'high' only)
    high_counts_result = await self.session.execute(
        select(
            OpportunityModel.owner_id,
            func.count(OpportunityModel.id),
        )
        .where(
            and_(
                OpportunityModel.tenant_id == tenant_id,
                OpportunityModel.risk_level == "high",
            )
        )
        .group_by(OpportunityModel.owner_id)
    )
    by_owner = {owner_id_: count for owner_id_, count in high_counts_result.all()}

    return {"alerts": alerts, "by_owner": by_owner}
```

在文件顶部确认 `and_` 和 `func` 已导入（见第 11 行的 `from sqlalchemy import and_, func, select`）。

**完成判定**：`ruff check src/services/sales_service.py` → 0 errors

---

### Step 2: Create `src/api/routers/dashboard.py`

新建文件：

```python
"""Dashboard router — /api/v1/sales/dashboard/*."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.sales_service import SalesService

dashboard_router = APIRouter(prefix="/api/v1/sales/dashboard", tags=["dashboard"])


@dashboard_router.get("/risk-alerts")
async def get_risk_alerts(
    owner_id: int | None = Query(None, ge=1, description="Filter by sales rep"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesService(session)
    data = await service.get_risk_alerts(ctx.tenant_id, owner_id=owner_id)
    return {"success": True, "data": data}
```

**完成判定**：文件 `src/api/routers/dashboard.py` 存在 / `ruff check src/api/routers/dashboard.py` → 0 errors

---

### Step 3: Register `dashboard_router` in `main.py`

在 `main.py` 中找到 `app.include_router(sales_router, ...)` 一行，在其后插入：

```python
from api.routers.dashboard import dashboard_router
# ...
app.include_router(dashboard_router)
```

确保 `include_router` 调用位于 `app = FastAPI()` 之后。

**完成判定**：`grep -n "dashboard_router" src/main.py` 返回 ≥ 1 行

---

### Step 4: Write unit tests in `tests/unit/test_dashboard_router.py`

新建文件：

```python
"""Unit tests for src/api/routers/dashboard.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routers.dashboard import dashboard_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException


def _auth_ctx(tenant_id=1):
    return AuthContext(user_id=99, tenant_id=tenant_id, roles=[])


@pytest.fixture
def client(monkeypatch):
    mock_svc = MagicMock()
    monkeypatch.setattr(
        "api.routers.dashboard.SalesService",
        lambda session: mock_svc,
    )
    app = FastAPI()
    app.include_router(dashboard_router)
    app.dependency_overrides[require_auth] = _auth_ctx
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app), mock_svc


# Happy path: returns high and medium risk opportunities
def test_risk_alerts_returns_high_and_medium(client):
    c, svc = client
    svc.get_risk_alerts = AsyncMock(
        return_value={
            "alerts": [
                {"id": 1, "name": "Risky Deal A", "risk_level": "high", "owner_id": 10},
                {"id": 2, "name": "Risky Deal B", "risk_level": "medium", "owner_id": 11},
            ],
            "by_owner": {10: 1, 11: 0},
        }
    )
    resp = c.get("/api/v1/sales/dashboard/risk-alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]["alerts"]) == 2
    assert body["data"]["by_owner"][10] == 1


# Boundary: low-risk opportunities are excluded by the service
def test_low_risk_excluded(client):
    c, svc = client
    svc.get_risk_alerts = AsyncMock(
        return_value={"alerts": [], "by_owner": {}}
    )
    resp = c.get("/api/v1/sales/dashboard/risk-alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["alerts"] == []


# Error case: service raises, global handler returns 4xx
def test_service_error_returns_4xx(client):
    c, svc = client
    from pkg.errors.app_exceptions import NotFoundException

    svc.get_risk_alerts = AsyncMock(side_effect=NotFoundException("Tenant"))
    resp = c.get("/api/v1/sales/dashboard/risk-alerts")
    assert resp.status_code == 404
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_dashboard_router.py -v` → `3 passed`

---

## 6. 验收

- [ ] `ruff check src/services/sales_service.py src/api/routers/dashboard.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_dashboard_router.py -v` → `3 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_sales_router.py -v` → 全 passed（regression check）
- [ ] `grep -n "dashboard_router" src/main.py` 返回 ≥ 1 行
- [ ] `PYTHONPATH=src mypy src/api/routers/dashboard.py src/services/sales_service.py` → 0 errors（如 mypy 已配置）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#600` 尚未合并，`OpportunityModel.risk_level` 列不存在，SQL 执行时 `AttributeError` | 中 | 高 | 阻塞验收；等 #600 的 migration 应用后再测；本 PR 不回退（列缺失是依赖问题，不是代码 bug） |
| `by_owner` 计数逻辑与前端期望不一致（前端期望每 rep 的 high+medium 总数而非仅 high） | 低 | 中 | 在路由层或 service 层调整 filter：`OpportunityModel.risk_level.in_(["high", "medium"])`；不阻塞其他端点 |
| 新 `dashboard.py` router 未被 `main.py` 导入导致 404 | 低 | 高 | 确保 `from api.routers.dashboard import dashboard_router` 已在 `main.py` 中；CI 会捕获 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/dashboard.py src/services/sales_service.py src/main.py tests/unit/test_dashboard_router.py
git commit -m "feat(sales): add GET /sales/dashboard/risk-alerts endpoint (#601)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(sales): risk-alerts dashboard endpoint (#601)" --body "Closes #601"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/sales.py`](../../../src/api/routers/sales.py) — existing sales router pattern (same envelope, auth, session injection)
- 同类参考实现：[`src/services/sales_service.py`](../../../src/services/sales_service.py) — `get_forecast` method as structural template for `get_risk_alerts`
- 父 issue / 关联：TBD - 待验证：#46 (parent epic), #600 (prerequisite — adds `risk_level` column to `opportunities`)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
