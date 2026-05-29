# Analytics Insights · New router + GET /analytics/{report_type}/insights stub endpoint

| 元数据 | 值 |
|---|---|
| Issue | #588 |
| 分类 | 60-analytics |
| 优先级 | 推荐 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | AI insights consumer (future) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Analytics 板块缺少一个统一的 insights入口点。下游（AI 驱动的 recommendations、trend 分析）需要一个稳定的 REST endpoint 路由框架，在 AI逻辑落地之前需要一个 stub 版本来支撑前端集成和联调节奏。#588 本身是 #48 的子任务，#41 是其前置依赖。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 stub。
- **开发者视角**：`GET /analytics/{report_type}/insights` 可被调用并返回 `{success: true, data: {summary, trends, recommendations}}`。Router 已有 AuthContext 鉴权，Service 层骨架已就位，后续直接填充 AI逻辑即可。

### 1.3 不做什么（剔除）

- [ ] AI / ML推断逻辑（指标计算、趋势分析、推荐生成）
- [ ] POST /analytics/insights（仅实现 GET）
- [ ] 独立的 `AnalyticsInsightsService`（当前阶段不需要 service 层，直接在 router 中返回 stub dict）
- [ ] 在 [#41](https://github.com/.../issues/41) 完成之前不要开始联调或端到端验证

### 1.4 关键 KPI

- `ruff check src/api/routers/analytics_insights.py src/api/routers/analytics.py` →0 errors
- `PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → ≥ 1 passed
- `alembic upgrade head` → exit 0（如有 migration改动）
- `ruff format --check src/api/routers/analytics_insights.py` → pass（无格式差异）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/` 目录下是否有 `analytics` 相关文件 — 请确认现有 analytics router 是否存在及其中是否已有 `/analytics/` 前缀注册```{note}
如 main.py 中已存在 `include_router(analytics_router, prefix="/analytics")`，则新 router 应挂在该 router 下作为子路由；如不存在，则新建顶级 `/analytics/` 前缀路由。
```

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../src/main.py) — 在 `app` 上注册新 router- 要建：
  - `src/api/routers/analytics_insights.py` — GET /analytics/{report_type}/insights stub router
  - `tests/unit/test_analytics_insights.py` —单元测试（mock session）

### 2.3 缺什么

- [ ] `src/api/routers/analytics_insights.py` — 新路由文件- [ ] `main.py` 中新 router 的 `include_router` 注册
- [ ] 鉴权中间件 `require_auth` + `AuthContext` 的引用注入
- [ ] `get_db` session 注入的标准写法
- [ ] 返回结构 `{success: true, data: {summary, trends, recommendations}}` 的 schema
- [ ] `tests/unit/test_analytics_insights.py` — 保证 router.handler 可被 mock 测试覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/analytics_insights.py` | GET /analytics/{report_type}/insights stub endpoint |
| `tests/unit/test_analytics_insights.py` | 单元测试（MockRow/MockResult + mock session） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../src/main.py) | 添加 `include_router(analytics_insights_router, prefix="/analytics")` |

### 3.3 新增能力

- **API endpoint**：`GET /analytics/{report_type}/insights` → `{"success": true, "data": {"summary": {}, "trends": [], "recommendations": []}}`
- **Router**：`AnalyticsInsightsRouter` in `src/api/routers/analytics_insights.py`
- **Auth**：请求携带 AuthContext（`require_auth` 鉴权）
- **Session**：`AsyncSession = Depends(get_db)` 标准注入

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 router → 直接返回 stub dict，不新建 Service** — stub阶段无需业务逻辑，新建 service徒增文件量；后续 AI 逻辑落地时可重构提取 Service，当前保持最小工作量。

### 4.2 版本约束

N/A — 无新增依赖。

### 4.3 兼容性约束

- 新 endpoint 必须路由到 `/analytics/{report_type}/insights` — `report_type` 作为 `Path[str]` 参数后续可扩展（如 `revenue`、`tickets`、`campaigns`）
- JSON响应结构固定为 `{"success": true, "data": {"summary": <dict>, "trends": <list>, "recommendations": <list>}}`，各字段初始值均为空容器- 多租户：endpoint鉴权通过 AuthContext 携带 tenant_id，stub阶段暂不在 DB 操作中使用### 4.4 已知坑

1. **SQLAlchemy Base 子类列名冲突** → 当前 stub 无 ORM model，但未来若加 model须避免使用 `metadata` 作为列名，改用 `event_metadata` / `payload`
2. **Router 中不要误用 `async with get_db()`** → 标准注入方式：`session: AsyncSession = Depends(get_db)`
3. **Alembic 无 migration** → 本 issue 不涉及 DB schema 改动，无需 `alembic revision`，无需在 §6 中列 alembic 验证命令

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/api/routers/analytics_insights.py`

创建新路由文件，导出 `router`（`APIRouter` 实例），前缀 `/`。

- a) 新建文件 `src/api/routers/analytics_insights.py`
- b) `from fastapi import APIRouter, Depends, Path` — 标准 imports
- c) `from dependencies import require_auth` — 鉴权依赖（如路径不确定，查 `src/dependencies/`目录）
- d) `from db.connection import get_db`
- e) `from internal.middleware.fastapi_auth import AuthContext`
- f) `router = APIRouter(prefix="/analytics", tags=["Analytics Insights"])`
- g) 定义 `GET /{report_type}/insights` handler，签名为：

```python
@router.get("/{report_type}/insights")
async def get_analytics_insights(
    report_type: str = Path(..., description="Report type: revenue, tickets, campaigns"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    return {
        "success": True,
        "data": {
            "summary": {},
            "trends": [],
            "recommendations": [],
        },
    }
```

**完成判定**：`ruff check src/api/routers/analytics_insights.py` →0 errors

---

### Step 2: 注册 router 到 `main.py`

在 `src/main.py` 中添加新 router 的 include_router 调用。

- a) 在 `main.py` 中添加 `from api.routers.analytics_insights import router as analytics_insights_router`
- b) 在 `app = FastAPI(...)` 的 `include_router` 列表中新增一行：`app.include_router(analytics_insights_router)`
- c) 确保路由顺序正确（`/analytics/{report_type}/insights` 不会被其他路由先匹配）

**完成判定**：`ruff check src/main.py` → 0 errors

---

### Step 3: 编写单元测试 `tests/unit/test_analytics_insights.py`

使用 `tests/unit/conftest.py` 中的 `make_mock_session` + `MockRow` / `MockResult` 等构建 mock session，对 router handler 进行覆盖测试。

- a) 新建 `tests/unit/test_analytics_insights.py`
- b) Fixture `mock_db_session`：调用 `make_mock_session([...])`
- c) Fixture `auth_context`：返回 `AuthContext(tenant_id=1, user_id=1, scopes=[])`
- d) 测试 `GET /analytics/revenue/insights`：用 `AsyncClient`（`httpx.AsyncClient`）或 `app.dependency_overrides`注入 mock，返回 `{"success": true, "data": {...}}`
- e) 测试 `report_type` 路径参数可填写不同值（`revenue`、`tickets`）
- f) 添加 `pytest.mark.asyncio` 标记

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient# 使用 dependency_overrides 进行测试（无需完整 ASGI 测试）
def test_analytics_insights_stub(client, auth_context, mock_db_session):
    client.app.dependency_overrides[require_auth] = lambda: auth_context
    client.app.dependency_overrides[get_db] = lambda: mock_db_session
    response = client.get("/analytics/revenue/insights")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "summary" in data["data"]
    assert "trends" in data["data"]
    assert "recommendations" in data["data"]
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → 1 passed（或 `N passed`，以实际用例数为准）

---

### Step 4: 格式化和 lint 自查

对新建文件执行 ruff 检查和格式校验。

- a) `ruff check src/api/routers/analytics_insights.py tests/unit/test_analytics_insights.py`
- b) `ruff format --check src/api/routers/analytics_insights.py` — 如有 diff，`ruff format src/api/routers/analytics_insights.py`修复

**完成判定**：两条命令均 exit 0，无输出

---

## 6. 验收

- [ ] `ruff check src/api/routers/analytics_insights.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → 全 passed
- [ ] `ruff format --check src/api/routers/analytics_insights.py` → pass（无格式差异）
- [ ] `PYTHONPATH=src mypy src/api/routers/analytics_insights.py --ignore-missing-imports` →0 type errors（如 mypy 未配置则跳过该项）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| main.py 中 router 注册顺序导致其他已有路由（如 `/analytics/foo`）被新路由错误拦截 | 低 | 中 | 将 `analytics_insights_router` 注册在 `analytics_router` 之后；review app.include_router 调用顺序 |
| `require_auth` / `get_db` import路径变更导致 CI失败 | 低 | 低 | 在 `src/dependencies/` 和 `src/db/connection.py` 确认路径不变；测试 fixture 用 `pytest.importorskip` 容错 |
| httpx / AsyncClient 端到端测试在 CI 环境网络隔离下超时 | 低 | 低 | 单元测试已覆盖核心逻辑，CI 环境跳过端到端手动 curl 验证 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/analytics_insights.py src/main.py tests/unit/test_analytics_insights.py
git commit -m "feat(analytics): add GET /analytics/{report_type}/insights stub endpoint"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): stub endpoint for #588" --body "Closes #588"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/api/routers/` 目录下已有 router 的写法（如 `customers.py` 或 `tickets.py`），参照其 AuthContext + get_db 注入模式
- 父 issue / 关联：#48, #41
