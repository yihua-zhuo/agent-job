# Enrichment 路由 · 新增 3 个 API端点

| 元数据 | 值 |
|---|---|
| Issue | #755 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | TBD - 待验证：#754 交付物路径 |
| 启用后赋能 | TBD - 待验证：赋能板块路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #755 是 #513 的子任务，依赖于前置板块 #754（EnrichmentAnalyticsService 实现）。#754 已完成 service层的 `get_stats`、`list_stale`、`bulk_refresh` 三个方法，本板块需要通过 FastAPI router 将其暴露为 HTTP 端点，供前端或下游服务调用。缺少 router 层则 service 能力无法被消费，属于必要的最后一公里工作。

### 1.2 做完后

- **用户视角**：前端或 API消费者可通过 `GET /api/v1/enrichment/stats`、`GET /api/v1/enrichment/stale`、`POST /api/v1/enrichment/bulk-refresh` 三个端点查询数据，无需直接调用 service。
- **开发者视角**：三个端点均通过 `AuthContext` 注入 tenant上下文，返回符合 `{"success": true, "data": {...}}` 规范的 JSON 响应，与仓库内其他 router行为一致。开发者可参照现有 router（如 `customer.py`、`opportunity.py`）的模式快速上手。

### 1.3 不做什么（剔除）

- [ ] EnrichmentAnalyticsService本身的业务逻辑实现（已在 #754 完成）
- [ ] 新增数据库表或 migration（router 仅调用已有 service）
- [ ] 权限细粒度控制（所有端点统一使用 `require_auth`，不做 role-based gate）
- [ ] 响应数据的分页 metadata 封装（返回 `{items: [...], total: N}` 结构即可）

### 1.4 关键 KPI

- `ruff check src/api/routers/enrichment.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_enrichment_router.py -v` → 全 passed
- `grep -c "def " src/api/routers/enrichment.py` →3（三个端点方法全部存在）
- `grep "router = APIRouter" src/api/routers/enrichment.py` → 1（router 实例唯一）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/enrichment_analytics_service.py` L? — #754 交付物，应包含 `get_stats`、`list_stale`、`bulk_refresh` 三个 async 方法

涉及的其他已有实现（参考模式）：

TBD - 待验证：customer router 路径 L{1}-L{50}

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth

router = APIRouter(prefix="/customers", tags=["Customer"])

@router.get("/")
async def list_customers(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CustomerService(session)
    items, total = await svc.list_customers(tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total}}
```

[`src/main.py`](../../../src/main.py) L{1}-L{80}

```python
from api.routers import customer, opportunity# router 注册示例app.include_router(customer.router, prefix="/api/v1")
```

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../../src/main.py) — 在 `include_router` 列表中添加 `enrichment.router`
- 要建：
  - `src/api/routers/enrichment.py` —三个端点的 router 定义  - `tests/unit/test_enrichment_router.py` — 单元测试（mock EnrichmentAnalyticsService）

### 2.3 缺什么

- [ ] `src/api/routers/enrichment.py` 文件不存在，无 HTTP 入口暴露 service能力
- [ ] `src/main.py` 未注册 enrichment router，端点不可访问
- [ ] 无针对 enrichment router 的单元测试，无法验证端点行为

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/enrichment.py` | Enrichment 路由：/stats、/stale、/bulk-refresh 三个端点 |
| `tests/unit/test_enrichment_router.py` | enrichment router 单元测试（mock service） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | 新增 `from api.routers.enrichment import router as enrichment_router` 并 `app.include_router(enrichment_router, prefix="/api/v1/enrichment")` |

### 3.3 新增能力

- **API endpoint**：`GET /api/v1/enrichment/stats` → `{"success": true, "data": <EnrichmentAnalyticsService.get_stats 返回值>}`
- **API endpoint**：`GET /api/v1/enrichment/stale?page=1&page_size=20&stale_after_days=30` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`POST /api/v1/enrichment/bulk-refresh` → `{"success": true, "data":<EnrichmentAnalyticsService.bulk_refresh 返回值>}`
- **Router**：`enrichment.router` 在 `src/main.py` 注册，前缀 `/api/v1/enrichment`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 FastAPI router 而非独立 Flask/Aiohttp**：项目已全量迁移至 FastAPI，保持技术栈统一，减少维护负担。
- **选 `Depends(get_db)` 而非 `async with get_db()`**：遵循 CLAUDE.md 规范，保证 session生命周期由 FastAPI DI 管理，避免 close 后继续使用的问题。
- **选 `AuthContext = Depends(require_auth)` 而非手动解析 header**：统一认证中间件已在 `internal.middleware.fastapi_auth` 实现，直接复用保证 tenant隔离一致。

### 4.2 版本约束

无新增依赖。

### 4.3 兼容性约束

- 多租户：三个端点均通过 `ctx.tenant_id` 注入，service 调用时透传
- Router 返回格式：`{"success": true, "data": <payload>}`，错误由 `main.py` 全局 `AppException` handler 统一处理
- Service 返回 ORM 对象，`to_dict()` 在 router 层调用（不在 service 内）
- Pagination：GET /stale 返回 `{items: [item.to_dict() for item in items], "total": total}`，符合现有分页约定### 4.4 已知坑

1. **Router 方法名与 service 方法名重叠导致 confusion** → 规避：router 方法命名为 `get_stats_endpoint`、`list_stale_endpoint`、`bulk_refresh_endpoint`，与 service 方法名明确区分
2. **查询参数 `stale_after_days` 未传或传0 导致全量扫描** → 规避：`stale_after_days: int = 30` 提供默认值，且 service侧已有防御3. **POST /bulk-refresh 无 request body 时 service抛异常** → 规避：router捕获参数缺失场景，必要时返回422（由全局 AppException handler统一处理）

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 src/api/routers/enrichment.py骨架

从现有 router复制结构，定义 `APIRouter`，导入 `EnrichmentAnalyticsService`（来自 #754 交付物）。

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.enrichment_analytics_service import EnrichmentAnalyticsService

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])

@router.get("/stats")
async def get_stats(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = EnrichmentAnalyticsService(session)
    result = await svc.get_stats(tenant_id=ctx.tenant_id)
    return {"success": True, "data": result}

@router.get("/stale")
async def list_stale(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    stale_after_days: int = Query(30, ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = EnrichmentAnalyticsService(session)
    items, total = await svc.list_stale(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        stale_after_days=stale_after_days,
    )
    return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total}}

@router.post("/bulk-refresh")
async def bulk_refresh(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = EnrichmentAnalyticsService(session)
    result = await svc.bulk_refresh(tenant_id=ctx.tenant_id)
    return {"success": True, "data": result}
```

**完成判定**：`ruff check src/api/routers/enrichment.py` → 0 errors

---

### Step 2: 在 src/main.py 注册 enrichment router

在 `src/main.py` 中新增 import 和 `include_router` 调用。

操作：
- a) 在 `from api.routers import ...` 附近添加 `from api.routers.enrichment import router as enrichment_router`
- b) 在现有 `app.include_router(...)` 调用列表中添加 `app.include_router(enrichment_router, prefix="/api/v1/enrichment")`

**完成判定**：`grep "enrichment" src/main.py` 输出包含 `enrichment_router` 和 `/api/v1/enrichment`

---

### Step 3: 编写 tests/unit/test_enrichment_router.py

使用 `tests/unit/conftest.py` 中的 `make_mock_session` 框架，为三个端点各写 2-3 个测试用例（正常返回、异常场景的 mock）。

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from main import app
from internal.middleware.fastapi_auth import AuthContext@pytest.fixture
def mock_service(mocker):
    svc = MagicMock(spec=EnrichmentAnalyticsService)
    svc.get_stats = AsyncMock(return_value={"total_enrichments": 10, "stale_count": 2})
    svc.list_stale = AsyncMock(return_value=([], 0))
    svc.bulk_refresh = AsyncMock(return_value={"refreshed": 5})
    return svc

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_count_handler(state)])

# ... 三个端点的 async test methods
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_router.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/enrichment.py` → 0 errors
- [ ] `ruff check src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_router.py -v` → 全 passed
- [ ] `grep "enrichment_router" src/main.py` 输出包含 `include_router(enrichment_router`
- [ ] `grep 'prefix="/api/v1/enrichment"' src/main.py` → 1 match- [ ] `grep -E "@router\.(get|post)" src/api/routers/enrichment.py` → 3 matches（stats、stale、bulk-refresh）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| EnrichmentAnalyticsService 方法签名与 router 调用不匹配（参数名/类型） | 低 | 中 | 参照 #754 交付物确认签名后修正 router；#754 若未完成则阻塞本板块，先行通知 |
| main.py 注册顺序导致路由冲突（如已有 /enrichment 前缀） | 低 | 中 | 检查 `grep -r "enrichment" src/api/routers/` 无其他 router 使用同一前缀后注册 |
| mock 测试覆盖不足，上线后真实 DB session 行为异常 | 低 | 中 | 补充 integration test（依赖 #754 完成后在集成测试层验证） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/enrichment.py src/main.py tests/unit/test_enrichment_router.py
git commit -m "feat(enrichment): add router with /stats, /stale, /bulk-refresh endpoints"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#755): add enrichment router with 3 endpoints" --body "Closes #755"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：customer router 路径 — 标准 router模式（认证注入、分页返回）
- 同类参考实现：TBD - 待验证：opportunity router 路径 — POST端点参考-父 issue /关联：#513- 前置依赖：#754

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
