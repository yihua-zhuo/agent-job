# Sales · Wire GET /sales/opportunities/{id}/recommendations endpoint

| 元数据 | 值 |
|---|---|
| Issue | #599 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待验证：关联自动化规则引擎板块, TBD - 待验证：关联推荐服务板块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `GET /sales/opportunities/{id}/recommendations` 端点不存在，销售团队和下游自动化规则（#687）均无法通过 API 获取商机的推荐结果。商机成交概率、相似商机、下一步行动等智能推荐数据只能在服务内部使用，未暴露为 HTTP 接口。

### 1.2 做完后

- **用户视角**：`GET /api/v1/sales/opportunities/{id}/recommendations` 返回该商机的完整推荐结果，包括成交概率、相似商机和最优下一步行动。
- **开发者视角**：`src/api/routers/recommendations.py` 提供 `GET /sales/opportunities/{id}/recommendations` 端点，调用 `RecommendationService(session).get_recommendations(id, tenant_id)`，返回 `{"success": true, "data": {...}}`。下游规则引擎（#687）和 AI 层可直接依赖此端点。

### 1.3 不做什么（剔除）

- [ ] 不实现 `POST /sales/opportunities/{id}/recommendations`（由其他板块负责）
- [ ] 不为推荐结果单独建 ORM model 和 migration — `RecommendationService` 基于已有商机数据和内存计算，返回 dict/list，不写 DB
- [ ] 不实现推荐缓存层（#598 若有涉及则在其板块处理）

### 1.4 关键 KPI

- `ruff check src/api/routers/recommendations.py src/services/sales_recommendation.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_recommendations_router.py -v` → 4 passed（200 + 404 + 500 + auth-required）
- 端到端：`curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/sales/opportunities/1/recommendations -H "Authorization: Bearer $TOKEN"` → 200

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py) L{43}-L{63}

```python:src/services/sales_recommendation.py
class SalesRecommendationService:
    """销售推荐服务"""

    def __init__(self):
        """初始化服务"""
        self._customer_cache: dict[int, dict] = {}

    def predict_conversion_probability(self, opportunity_id: int) -> float:
        """预测商机成交概率（增强版）"""
        import hashlib
        seed = int(hashlib.sha256(str(opportunity_id).encode()).hexdigest()[:8], 16)
        base_prob = 0.3 + (seed % 50) / 100.0
        market_sentiment = 0.8 + (seed % 40) / 100.0
        competition_factor = 0.7 + (seed % 60) / 100.0
        conversion_prob = base_prob * market_sentiment * competition_factor
        return round(min(max(conversion_prob, 0.0), 1.0), 2)
```

现有路由（无 recommendations 端点）：[`src/api/routers/sales.py`](../../../src/api/routers/sales.py) L{1}-L{10}

路由发现（自动注册新 router）：[`src/api/__init__.py`](../../../src/api/__init__.py) L{19}-L{26}

```python:src/api/__init__.py
def iter_routers() -> Iterator[APIRouter]:
    for info in sorted(pkgutil.iter_modules(routers.__path__, prefix=f"{routers.__name__}."), key=lambda item: item.name):
        module = importlib.import_module(info.name)
        for name in sorted(dir(module)):
            value = getattr(module, name)
            if isinstance(value, APIRouter):
                yield value
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py) — 添加 `get_recommendations` 异步方法，改造 `__init__` 接受 `AsyncSession` 参数
  - [`tests/unit/test_sales_router.py`](../../../tests/unit/test_sales_router.py) — 无改动
- 要建：
  - `src/api/routers/recommendations.py` — 新建：推荐端点 router
  - `tests/unit/test_recommendations_router.py` — 新建：单元测试

### 2.3 缺什么

- [ ] `src/api/routers/recommendations.py` 文件不存在，无 `GET /sales/opportunities/{id}/recommendations` 端点
- [ ] `SalesRecommendationService` 缺少 `get_recommendations(id, tenant_id)` 方法（现有方法均为同步且不接受 session）
- [ ] `SalesRecommendationService.__init__` 无 `AsyncSession` 参数，无法在 router 层共用同一 session
- [ ] 无 `tests/unit/test_recommendations_router.py` 单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/api/routers/recommendations.py` | 新建：GET /sales/opportunities/{id}/recommendations 端点 |
| `tests/unit/test_recommendations_router.py` | 新建：recommendations router 的单元测试（200/404/500/auth） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py) | 1) `__init__` 接受 `AsyncSession` 参数；2) 新增 `async get_recommendations(opportunity_id, tenant_id)` 方法调用 `predict_conversion_probability` 等现有方法 |

### 3.3 新增能力

- **API endpoint**：`GET /api/v1/sales/opportunities/{id}/recommendations` → `{"success": true, "data": {"opportunity_id": ..., "conversion_probability": ..., "similar_opportunities": [...], "next_best_action": {...}}}`
- **Service method**：`SalesRecommendationService.get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict`
- **Router**：`src/api/routers/recommendations.py` — `recommendations_router`，由 `api/__init__.py` 的 `iter_routers()` 自动发现注册

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用 `SalesRecommendationService` 而非新建 service**：`predict_conversion_probability` 等核心逻辑已在 `sales_recommendation.py` 中实现，在其上扩展 `get_recommendations` 方法，避免逻辑重复。
- **`recommendations.py` 作为独立 router 而非挂在 `sales.py` 下**：`recommendations` 是独立资源域（子 issue #598 单独定义 service），独立 router 便于后续扩展 `POST /recommendations/generate` 等端点，也符合本仓库一个 domain 一个 router 的惯例。

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：endpoint 通过 `ctx.tenant_id`（从 `require_auth` 得到）传入 service；`get_recommendations` 内部不使用 SQL 故无需额外 `WHERE tenant_id` 过滤，但 `tenant_id` 参与 hash seed 保证多租户数据隔离。
- Router 使用 `Depends(get_db)` 注入 session，不使用 `async with get_db()`。
- Service 错误抛 `AppException` 子类，由 `main.py` 全局 handler 转为 JSON 响应 — 不在 router 层 try/catch。
- `recommendations.py` 导出 `recommendations_router`（小写 + 下划线），`iter_routers()` 依赖此命名约定。

### 4.4 已知坑

1. **SalesRecommendationService 现有 `__init__` 无参数** → 规避：改造为 `def __init__(self, session: AsyncSession | None = None):`，兼容无 session 调用（内部逻辑不依赖 DB）。
2. **`iter_routers()` 自动发现** 依赖 router 模块顶级作用域导出 `APIRouter` 实例，变量名必须以 `recommendations_router` 形式出现，小写 + 下划线。

---

## 5. 实现步骤（按顺序）

### Step 1: 修改 `SalesRecommendationService` 支持 async 入口

在 `src/services/sales_recommendation.py` 中：
- 将 `__init__` 签名改为 `def __init__(self, session: AsyncSession | None = None):`，存储 session。
- 新增 `async def get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict:` 方法，调用 `predict_conversion_probability`、`get_similar_customers`、`get_next_best_action`，返回结构化 dict。

操作：
- a) 编辑 `src/services/sales_recommendation.py`，在顶部 import 添加 `from sqlalchemy.ext.asyncio import AsyncSession`
- b) 将 `def __init__(self):` 改为 `def __init__(self, session: AsyncSession | None = None):`
- c) 在 `__init__` 体内添加 `self.session = session`
- d) 在类末尾（第 270 行后）插入 `get_recommendations` 方法

示例代码：

```python
async def get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict:
    """获取商机完整推荐结果。"""
    conversion_prob = self.predict_conversion_probability(opportunity_id)
    similar = self.get_similar_customers(tenant_id, opportunity_id)
    next_action = self.get_next_best_action(tenant_id, opportunity_id)
    return {
        "opportunity_id": opportunity_id,
        "conversion_probability": conversion_prob,
        "similar_opportunities": [
            {
                "customer_id": s.customer_id,
                "current_tier": s.current_tier,
                "monthly_revenue": s.monthly_revenue,
            }
            for s in similar
        ],
        "next_best_action": {
            "action": next_action.action,
            "target": next_action.target,
            "reason": next_action.reason,
            "confidence": next_action.confidence,
        },
    }
```

**完成判定**：`ruff check src/services/sales_recommendation.py` → 0 errors

### Step 2: 创建 `src/api/routers/recommendations.py`

新建文件，定义 `recommendations_router`：

操作：
- a) 创建 `src/api/routers/recommendations.py`

示例代码：

```python
"""Recommendations router — GET /api/v1/sales/opportunities/{id}/recommendations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import NotFoundException
from services.sales_recommendation import SalesRecommendationService

recommendations_router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


@recommendations_router.get("/opportunities/{opp_id}/recommendations")
async def get_opportunity_recommendations(
    opp_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    service = SalesRecommendationService(session)
    data = await service.get_recommendations(opp_id, ctx.tenant_id)
    return {"success": True, "data": data}
```

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/recommendations.py` → 0 errors

### Step 3: 创建 `tests/unit/test_recommendations_router.py`

操作：
- a) 创建 `tests/unit/test_recommendations_router.py`，参考 `tests/unit/test_sales_router.py` 的 fixture 模式

示例代码：

```python
"""Unit tests for src/api/routers/recommendations.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routers.recommendations import recommendations_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException, NotFoundException


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


@pytest.fixture
def client_with_service(monkeypatch):
    from internal.middleware.fastapi_auth import require_auth
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    mock_service = MagicMock()
    monkeypatch.setattr(
        "api.routers.recommendations.SalesRecommendationService",
        lambda session: mock_service,
    )
    app = FastAPI()
    app.include_router(recommendations_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"success": False, "message": exc.detail})

    return TestClient(app, raise_server_exceptions=False), mock_service


class TestGetRecommendations:
    def test_success_returns_200(self, client_with_service):
        client, svc = client_with_service
        svc.get_recommendations = AsyncMock(return_value={
            "opportunity_id": 5,
            "conversion_probability": 0.72,
            "similar_opportunities": [],
            "next_best_action": {"action": "up_sell", "target": "premium", "reason": "高使用率", "confidence": 0.85},
        })
        resp = client.get("/api/v1/sales/opportunities/5/recommendations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["opportunity_id"] == 5
        assert body["data"]["conversion_probability"] == 0.72

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_recommendations = AsyncMock(side_effect=NotFoundException("Opportunity"))
        resp = client.get("/api/v1/sales/opportunities/9999/recommendations")
        assert resp.status_code == 404

    def test_internal_error_returns_500(self, client_with_service):
        client, svc = client_with_service
        svc.get_recommendations = AsyncMock(side_effect=RuntimeError("unexpected"))
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 500

    def test_missing_auth_returns_401(self):
        from internal.middleware.fastapi_auth import require_auth
        app = FastAPI()
        app.include_router(recommendations_router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        # Do NOT override require_auth — let it reject
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/sales/opportunities/1/recommendations")
        assert resp.status_code == 401
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendations_router.py -v` → 4 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/recommendations.py src/services/sales_recommendation.py` → 0 errors
- [ ] `PYTHONPATH=src ruff format --check src/api/routers/recommendations.py src/services/sales_recommendation.py` → pass
- [ ] `PYTHONPATH=src pytest tests/unit/test_recommendations_router.py -v` → 4 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_sales_router.py -v` → 全 passed（回归检查，sales.py 未改动）
- [ ] 端到端（启动服务）：`curl -s http://localhost:8000/api/v1/sales/opportunities/1/recommendations -H "Authorization: Bearer $TOKEN"` → `{"success": true, "data": {"opportunity_id": 1, ...}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `iter_routers()` 无法发现新 router（命名不符约定） | 低 | 中 | router 变量名必须是 `recommendations_router`（已在 Step 2 明确）；手动在 `main.py` 调用 `app.include_router(recommendations_router)` 作为 fallback |
| `get_recommendations` 内部调用同步方法报错（GIL/死锁） | 低 | 中 | 现有 `predict_conversion_probability` 等均为纯计算、无 IO；如需真实 DB 查询，改用 `asyncio.to_thread` 包装 |
| service 返回不可序列化对象导致 500 | 低 | 高 | 在 router 层对 `data` 字段做 JSON 序列化保护（已知坑：dataclass 未定义 `__dict__`）→ `return {"success": True, "data": json.loads(json.dumps(data))}` 作为 fallback |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/recommendations.py src/services/sales_recommendation.py tests/unit/test_recommendations_router.py
git commit -m "feat(sales): add GET /sales/opportunities/{id}/recommendations endpoint

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(sales): wire GET /sales/opportunities/{id}/recommendations (closes #599)" --body "Closes #599

## Summary
- New router: src/api/routers/recommendations.py with GET /api/v1/sales/opportunities/{id}/recommendations
- SalesRecommendationService.get_recommendations(id, tenant_id) async method
- 4 unit tests: 200, 404, 500, 401"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/sales.py`](../../../src/api/routers/sales.py) — router 结构、序列化模式、错误处理完全复用
- 同类参考实现：[`tests/unit/test_sales_router.py`](../../../tests/unit/test_sales_router.py) — fixture 模式、mock 策略直接复用
- 父 issue / 关联：#46
- 依赖 issue / 关联：#598

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
