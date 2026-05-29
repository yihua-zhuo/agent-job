# CRM 全局仪表盘 · 关键指标仪表盘 UI

| 元数据 | 值 |
|---|---|
| Issue | #52 |
| 分类 | 10-framework |
| 优先级 | 必做 |
| 工作量 | 3-5 工作日 |
| 依赖 | [新建前端项目骨架](无，已由 #60 提供基础结构) |
| 启用后赋能 | 所有前端业务模块（侧边导航 + 布局组件） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前系统无前端界面，用户无法查看 CRM 数据。CRM Dashboard 是用户登录后的第一个页面，承担全局概览的核心职责。缺乏仪表盘意味着用户无法快速了解业务状态，必须手动跳转至各个模块拼凑信息，大幅降低使用效率。

### 1.2 做完后

- **用户视角**：用户访问 `/dashboard` 可看到收入概览卡片、 Pipeline 阶段漏斗、最近 10 条动态、待处理工单摘要等关键指标，数据每 5 分钟自动刷新，支持手动刷新和周期切换。
- **开发者视角**：新建 `DashboardService` 提供数据聚合；新增 `GET /dashboard/*` 系列 API；新增 `DashboardOverview`, `PipelineStage`, `ActivityFeed` 等 Pydantic model；前端新增 `@/pages/Dashboard` 路由和复用布局组件（侧边栏、顶栏）。

### 1.3 不做什么（剔除）

- [ ] 不实现权限粒控（admin vs. user 视图差异）—— 属于独立 issue
- [ ] 不实现自定义仪表盘（拖拽、用户自定义 widget 布局）—— 属于独立 issue
- [ ] 不实现指标下钻（点击卡片跳转详情）—— 属于独立 issue
- [ ] 不实现工单 SLA 计算引擎本身（仅调用已有 service / model 接口）

### 1.4 关键 KPI

- [KPI 1：Dashboard 页面加载时间 < 2s（骨架屏 + 并行 API 请求）]
- [KPI 2：所有 acceptance 清单项前端完成，E2E 测试覆盖]
- [KPI 3：`ruff check src/services/dashboard_service.py` → 0 errors]
- [KPI 4：`PYTHONPATH=src pytest tests/unit/test_dashboard_service.py -v` → ≥ 8 passed]
- [KPI 5：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及 migration）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块（前端骨架由 #60 提供，但 dashboard 页面及后端聚合 API 均尚未实现）

### 2.2 涉及文件清单

- 要改：
  - `src/services/sales_service.py` — 补充 Pipeline 阶段聚合查询方法
  - `src/services/activity_service.py` — 补充最近 N 条动态查询方法
  - `src/services/ticket_service.py` — 补充工单状态汇总查询方法
  - `src/api/routers/dashboard.py` — 新建 router 挂载 dashboard API
  - `src/main.py` — 注册 dashboard router
  - `tests/unit/domain_handlers/dashboard.py` — 新增 mock handler 供单元测试复用（导出 `get_handlers(state)`）
- 要建：
  - `src/services/dashboard_service.py` — 聚合收入、Pipeline、工单、动态的 service
  - `src/models/response.py` — 补充 DashboardOverviewResponse 等 schema（如当前 response.py 无）
  - `alembic/versions/<id>_add_dashboard_indexes.py` — 如需新增索引
  - `tests/unit/test_dashboard_service.py` — dashboard service 单元测试
  - `tests/integration/test_dashboard_integration.py` — dashboard API 集成测试
  - 前端文件（由 #60 确定路径，如 `frontend/src/pages/Dashboard/` 下各组件）

### 2.3 缺什么

- [ ] 无 Dashboard 页面前端路由和组件（Skeleton、EmptyState、ResponsiveGrid）
- [ ] 无后端 `/dashboard/revenue`、`/dashboard/pipeline`、`/dashboard/activities`、`/dashboard/tickets` API endpoint
- [ ] 无 `DashboardService` 聚合层（需联调 sales / activity / ticket / revenue service）
- [ ] 无 Pipeline 漏斗可视化组件（前端）
- [ ] 无收入趋势折线图组件（前端，支持 period 参数）
- [ ] 无 Auto-refresh 机制（前端轮询或 SSE）
- [ ] 无后端 `Activity` model 或表（用于最近动态 feed）— 待确认现有实现
- [ ] 无 SLA ticket 计数（需 ticket service 暴露统计接口）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/dashboard_service.py` | 聚合各域 service 数据，提供收入概览、Pipeline、工单摘要、动态 feed |
| `src/api/routers/dashboard.py` | Dashboard API router，暴露 `/dashboard/*` 端点 |
| `tests/unit/test_dashboard_service.py` | DashboardService 单元测试 |
| `tests/integration/test_dashboard_integration.py` | Dashboard API 集成测试（真实 PostgreSQL） |
| `frontend/src/pages/Dashboard/index.tsx` | Dashboard 页面入口，路由绑定 |
| `frontend/src/pages/Dashboard/components/RevenueCards.tsx` | 收入概览卡片组件 |
| `frontend/src/pages/Dashboard/components/PipelineFunnel.tsx` | Pipeline 阶段漏斗可视化 |
| `frontend/src/pages/Dashboard/components/TopOpportunities.tsx` | Top 5 机会列表组件 |
| `frontend/src/pages/Dashboard/components/ActivityFeed.tsx` | 最近动态 feed 组件 |
| `frontend/src/pages/Dashboard/components/TicketQueue.tsx` | 工单队列摘要组件 |
| `frontend/src/components/Layout/Sidebar.tsx` | 侧边导航组件（可复用） |
| `frontend/src/components/Layout/Header.tsx` | 顶栏组件，含用户菜单（可复用） |
| `frontend/src/components/common/LoadingSkeleton.tsx` | 通用骨架屏组件 |
| `frontend/src/components/common/EmptyState.tsx` | 通用空状态组件 |
| `frontend/src/hooks/useDashboardData.ts` | Dashboard 数据获取 hook（含轮询逻辑） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/sales_service.py` | 新增 `get_pipeline_stages(tenant_id)` 方法，返回各阶段金额汇总 |
| `src/services/activity_service.py` | 新增 `get_recent_activities(tenant_id, limit=10)` 方法 |
| `src/services/ticket_service.py` | 新增 `get_ticket_summary(tenant_id)` 方法，返回 open/in-progress/resolved/SLA_at_risk 计数 |
| `src/main.py` | 引入并注册 `dashboard_router` |
| `tests/unit/domain_handlers/dashboard.py` | 新增 `get_handlers(state)` mock handler 供单元测试复用 |

### 3.3 新增能力

- **Service method**：`DashboardService.get_overview(self, tenant_id: int, period: str) -> DashboardOverview`
- **API endpoint**：`GET /dashboard/overview?period=today|week|month|quarter` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /dashboard/pipeline` → `{"success": true, "data": {"stages": [...]}}`
- **API endpoint**：`GET /dashboard/activities` → `{"success": true, "data": {"items": [...], "total": 10}}`
- **API endpoint**：`GET /dashboard/tickets` → `{"success": true, "data": {"open": N, "in_progress": N, "resolved_today": N, "sla_at_risk": N}}`
- **API endpoint**：`GET /dashboard/opportunities/top?limit=5` → `{"success": true, "data": {"items": [...]}}`
- **ORM model**：`TBD - 待验证：src/db/models/ 目录下是否存在 Activity model — 如无则新建 activity 表 migration`
- **Migration**：`alembic upgrade head` 确保 pipeline_stages 索引存在

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Dashboard 数据聚合放在 service 层而非 router 层** → 各域 service（sales/activity/ticket）职责单一，DashboardService 组合调用，避免 router 直接跨域查询 DB
- **前端 auto-refresh 用轮询而非 SSE/WebSocket** → 仪表盘数据更新频率低（5 分钟），轮询简单可靠；避免引入 WebSocket 基础设施复杂度
- **骨架屏 + 独立 API 并行请求** → 各 widget 数据独立返回，前端并行 fetch，任一失败不影响其他 widget 渲染
- **选 Recharts 不选 D3.js** → Recharts 上手快、TS 支持好、组件化程度高，适合 Dashboard 可视化场景

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `recharts` | `^2.12.0` | 稳定版，支持 React 18，有 TypeScript 类型 |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- 前端 API 路径统一以 `/dashboard/` 为前缀，返回 `{success: true, data: {...}}` envelope
- 所有新增 API 必须携带 `tenant_id` 鉴权（`require_auth` dependency）

### 4.4 已知坑

1. **Alembic autogenerate 将 JSONB 写成 JSON，将 TIMESTAMPTZ 写成 DateTime** → 手动改回：JSONB 用 `sa.JSONB().with_variant(...)` 或直接 `postgresql.JSONB()`，DateTime 加 `timezone=True`
2. **SQLAlchemy Base 子类列名不能用 `metadata`**（与 `Base.metadata` 冲突）→ 如 activity 表有 metadata 字段，命名为 `event_metadata` 或 `payload`
3. **PYTHONPATH=src**，import 写 `from db.models...` 而不是 `from src.db.models...`
4. **Async session 不要用 `async with get_db()`**，用 `session: AsyncSession = Depends(get_db)`
5. **前端并行 API 请求需处理 partial failure** → 骨架屏升成实际数据时，失败的 widget 显示错误提示而非整体白屏
6. **DashboardService 不能新建 session**（`__init__` 必须接受 AsyncSession 无默认值）→ 注入已存在的 session，组合调用各子 service

---

## 5. 实现步骤（按顺序）

### Step 1: 补充各域 service 统计方法

在 `sales_service.py`、`activity_service.py`、`ticket_service.py` 中补充 Dashboard 需要的聚合查询方法。

操作：
- a) 在 `SalesService` 新增 `get_pipeline_stages(self, tenant_id: int) -> list[PipelineStage]`
- b) 在 `ActivityService` 新增 `get_recent_activities(self, tenant_id: int, limit: int = 10) -> list[ActivityModel]`
- c) 在 `TicketService` 新增 `get_ticket_summary(self, tenant_id: int) -> TicketSummary` dataclass
- d) 在 `tests/unit/domain_handlers/dashboard.py` 新增 `get_handlers(state)` 用于后续 mock

```python
# src/services/ticket_service.py 新增
@dataclass
class TicketSummary:
    open: int
    in_progress: int
    resolved_today: int
    sla_at_risk: int

async def get_ticket_summary(self, tenant_id: int) -> TicketSummary:
    # COUNT WHERE status = 'open' AND tenant_id = :tenant_id
    # COUNT WHERE status = 'in_progress' AND tenant_id = :tenant_id
    # COUNT WHERE resolved_date = TODAY AND tenant_id = :tenant_id
    # COUNT WHERE sla_breach < NOW() AND status != 'resolved' AND tenant_id = :tenant_id
```

**完成判定**：`PYTHONPATH=src ruff check src/services/sales_service.py src/services/ticket_service.py src/services/activity_service.py` → 0 errors

### Step 2: 新建 DashboardService 聚合层

创建 `src/services/dashboard_service.py`，组合调用 sales / activity / ticket service。

操作：
- a) 创建 `src/services/dashboard_service.py`
- b) 实现 `DashboardService.__init__(self, session: AsyncSession)` — 注入 session，实例化子 service
- c) 实现 `get_revenue_overview(tenant_id, period)` — 调用 revenue 相关查询
- d) 实现 `get_pipeline(tenant_id)` — 委托 SalesService
- e) 实现 `get_activities(tenant_id, limit)` — 委托 ActivityService
- f) 实现 `get_ticket_summary(tenant_id)` — 委托 TicketService
- g) 实现 `get_top_opportunities(tenant_id, limit)` — 委托 SalesService

```python
# src/services/dashboard_service.py
import asyncio
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from services.sales_service import SalesService
from services.activity_service import ActivityService
from services.ticket_service import TicketService, TicketSummary

@dataclass
class DashboardOverview:
    revenue_today: float
    revenue_week: float
    revenue_month: float
    revenue_quarter: float
    pipeline: list
    activities: list
    ticket_summary: TicketSummary
    top_opportunities: list

class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sales = SalesService(session)
        self.activity = ActivityService(session)
        self.ticket = TicketService(session)

    async def get_overview(self, tenant_id: int, period: str = "month") -> DashboardOverview:
        # parallel gather — 各子查询可并发
        revenue_future = asyncio.create_task(self._get_revenue(tenant_id, period))
        pipeline_future = asyncio.create_task(self.sales.get_pipeline_stages(tenant_id))
        activities_future = asyncio.create_task(self.activity.get_recent_activities(tenant_id, 10))
        ticket_future = asyncio.create_task(self.ticket.get_ticket_summary(tenant_id))
        opp_future = asyncio.create_task(self.sales.get_top_opportunities(tenant_id, 5))
        # asyncio.gather all futures
        ...
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_dashboard_service.py -v` → ≥ 8 passed

### Step 3: 新建 Dashboard API Router

创建 `src/api/routers/dashboard.py`，挂载所有 `/dashboard/*` 端点。

操作：
- a) 创建 `src/api/routers/dashboard.py`
- b) 注册路由：
  - `GET /dashboard/overview?period=today|week|month|quarter`
  - `GET /dashboard/pipeline`
  - `GET /dashboard/activities`
  - `GET /dashboard/tickets`
  - `GET /dashboard/opportunities/top?limit=5`
- c) 在 `src/main.py` 添加 `app.include_router(dashboard_router, prefix="/dashboard")`

```python
# src/api/routers/dashboard.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.dashboard_service import DashboardService

router = APIRouter(tags=["Dashboard"])

@router.get("/overview")
async def get_dashboard_overview(
    period: str = Query("month", regex="^(today|week|month|quarter)$"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = DashboardService(session)
    overview = await svc.get_overview(tenant_id=ctx.tenant_id, period=period)
    return {"success": True, "data": overview}
```

**完成判定**：`ruff check src/api/routers/dashboard.py` → 0 errors；`PYTHONPATH=src pytest tests/integration/test_dashboard_integration.py -v` → 全 passed

### Step 4: 新增单元测试和集成测试

为 DashboardService 和各子 service 方法补充测试覆盖。

操作：
- a) 创建 `tests/unit/test_dashboard_service.py`，mock 所有子 service handler
- b) 在 `tests/unit/domain_handlers/dashboard.py` 添加 `get_handlers(state)`（如尚未添加）
- c) 创建 `tests/integration/test_dashboard_integration.py`，使用 `db_schema`、`tenant_id`、`async_session` fixture

```python
# tests/unit/test_dashboard_service.py 关键测试用例
import pytest
from services.dashboard_service import DashboardService

@pytest.fixture
def dashboard_service(mock_db_session):
    return DashboardService(mock_db_session)

async def test_get_overview_returns_all_sections(dashboard_service, mock_tenant_id):
    result = await dashboard_service.get_overview(tenant_id=mock_tenant_id, period="month")
    assert hasattr(result, "revenue_today")
    assert hasattr(result, "pipeline")
    assert hasattr(result, "activities")
    assert hasattr(result, "ticket_summary")
    assert hasattr(result, "top_opportunities")

async def test_get_ticket_summary_counts(dashboard_service, mock_tenant_id):
    result = await dashboard_service.get_ticket_summary(tenant_id=mock_tenant_id)
    assert result.open >= 0
    assert result.in_progress >= 0
    assert result.resolved_today >= 0
    assert result.sla_at_risk >= 0
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_dashboard_service.py tests/unit/test_dashboard_service.py -v` → ≥ 8 passed；`PYTHONPATH=src pytest tests/integration/test_dashboard_integration.py -v` → 全 passed

### Step 5: 新建前端 Dashboard 页面和布局组件

根据 #60 确定的路径创建前端组件。

操作：
- a) 创建 `frontend/src/pages/Dashboard/index.tsx` — 页面入口，含路由注册
- b) 创建 `Sidebar.tsx` 和 `Header.tsx` 布局组件（如 #60 未提供复用结构）
- c) 创建 `RevenueCards.tsx`、`PipelineFunnel.tsx`、`TopOpportunities.tsx`、`ActivityFeed.tsx`、`TicketQueue.tsx`
- d) 创建 `LoadingSkeleton.tsx` 和 `EmptyState.tsx` 通用组件
- e) 创建 `useDashboardData.ts` hook，含 5 分钟轮询逻辑
- f) 在路由配置中注册 `/dashboard`

```typescript
// frontend/src/hooks/useDashboardData.ts
import { useState, useEffect, useCallback } from "react";

const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

export function useDashboardData(endpoint: string) {
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(endpoint);
      const json = await res.json();
      if (json.success) {
        setData(json.data);
        setLastUpdated(new Date());
        setError(null);
      }
    } catch (e) {
      setError("Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchData]);

  return { data, loading, error, lastUpdated, refresh: fetchData };
}
```

**完成判定**：前端构建成功，无 TypeScript 错误；E2E 测试（Cypress/Playwright）Dashboard 页面 `/dashboard` HTTP 200

### Step 6: 前端 Dashboard 可视化组件开发

实现收入趋势折线图、Pipeline 漏斗、各 widget 空状态。

操作：
- a) 实现 `RevenueCards.tsx`：4 张卡片（今日/本周/本月/本季度），支持 loading skeleton 和空状态
- b) 实现收入趋势折线图（`recharts` LineChart，支持 day/week/month/quarter 周期切换）
- c) 实现 `PipelineFunnel.tsx`：漏斗图，每阶段显示金额和机会数
- d) 实现 `TopOpportunities.tsx`：Top 5 机会表格，含金额和预计成交日期
- e) 实现 `ActivityFeed.tsx`：最近 10 条动态列表，含时间戳和类型图标
- f) 实现 `TicketQueue.tsx`：工单队列摘要，含 at-risk 警告高亮
- g) 实现手动刷新按钮（调用 `refresh` from `useDashboardData`）
- h) 实现响应式 grid 布局（CSS Grid，desktop/tablet/mobile 三档）

**完成判定**：前端 dev server 启动，`/dashboard` 页面各 widget 渲染正常；`lastUpdated` 时间戳显示；手动刷新触发数据更新

---

## 6. 验收

- [ ] `ruff check src/services/dashboard_service.py src/api/routers/dashboard.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_dashboard_service.py -v` → ≥ 8 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_dashboard_integration.py -v` → 全 passed（如有集成测试）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及新 migration）
- [ ] 端到端：`curl -s -H "Authorization: Bearer <token>" http://localhost:8000/dashboard/overview?period=month` 返回 `{"success": true, "data": {...}}`
- [ ] 端到端：`curl -s -H "Authorization: Bearer <token>" http://localhost:8000/dashboard/pipeline` 返回 `{"success": true, "data": {"stages": [...]}}`
- [ ] 前端：访问 `http://localhost:3000/dashboard` → HTTP 200，各 widget 渲染成功，无 console error

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 后端各域 service 统计方法实现与 DashboardService 预期接口不匹配（返回字段名/类型不一致） | 中 | 高 | DashboardService 兼容适配层（`getattr` 兜底 + warning log）；不阻塞 dashboard 页面，先出 skeleton 后填充 |
| 前端依赖 #60 提供的基础布局组件（Sidebar/Header）未就绪 | 中 | 高 | 先独立实现最小 Sidebar + Header，保证 dashboard 独立可测试；#60 合并后替换为复用版本 |
| Auto-refresh 轮询与手动刷新竞态导致 UI 闪烁 | 低 | 低 | 使用 React SWR 或 React Query，deduplicate 请求；或加 mutex flag 防止并发刷新 |
| Pipeline 漏斗数据量大导致 DB 查询慢（无索引） | 低 | 中 | 为 `tenant_id` + `stage` 组合加联合索引；如迁移复杂则在验收阶段加监控，单独建 issue 优化 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/dashboard_service.py src/api/routers/dashboard.py \
       src/services/sales_service.py src/services/activity_service.py src/services/ticket_service.py \
       tests/unit/test_dashboard_service.py tests/integration/test_dashboard_integration.py \
       tests/unit/domain_handlers/dashboard.py
git commit -m "feat(dashboard): add CRM overview dashboard with key metrics UI

- Add DashboardService aggregation layer combining sales/activity/ticket services
- Add GET /dashboard/overview|pipeline|activities|tickets|opportunities/top endpoints
- Add RevenueCards, PipelineFunnel, TopOpportunities, ActivityFeed, TicketQueue components
- Add auto-refresh every 5 minutes + manual refresh button
- Add unit and integration tests for dashboard service and API

Closes #52"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(dashboard): CRM overview dashboard with key metrics UI" --body "## Summary
- New DashboardService aggregation layer
- New /dashboard/* API endpoints (revenue, pipeline, activities, tickets, top opportunities)
- New frontend dashboard page with responsive grid layout
- New revenue trend line chart, pipeline funnel, activity feed, ticket queue widgets

## Test plan
- [ ] pytest tests/unit/test_dashboard_service.py -v → ≥ 8 passed
- [ ] pytest tests/integration/test_dashboard_integration.py -v → all passed
- [ ] ruff check src/services/dashboard_service.py src/api/routers/dashboard.py → 0 errors
- [ ] Manual: GET /dashboard/overview → {\"success\": true, \"data\": {...}}
- [ ] Manual: /dashboard page renders all widgets in browser

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：src/services/sales_service.py L? — 现有 Pipeline 查询参考
- 第三方文档：[Recharts](https://recharts.org/en-US/) — Dashboard 可视化组件库
- 父 issue / 关联：#52（本文档）, #60（前置依赖：前端项目骨架）
