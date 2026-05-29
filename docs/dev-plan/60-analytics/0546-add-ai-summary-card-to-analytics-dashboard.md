# AI Summary Card · 为 Analytics Dashboard 添加 AI 摘要卡

| 元数据 | 值 |
|---|---|
| Issue | #546 |
| 分类 | 60-analytics |
| 优先级 | 推荐 |
| 工作量 | 1 工作日 |
| 依赖 | [0546-ai-insights-api](0546-ai-insights-api.md) (#545 的前置依赖), #41 (AI Agent Framework) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `/analytics` 路由仅渲染时间序列图表，用户需要自行解读图表趋势，缺少 AI驱动的文字摘要。业务方要求在图表区上方显示一行自然语言摘要，帮助用户快速理解关键指标变化（如"本季度营收环比增长 23%，线索转化率下降 5%"）。

### 1.2 做完后

- **用户视角**：`/analytics` 页面顶部新增 AI Summary Card，卡片内显示自然语言摘要；若 AI 后端未就绪或请求失败，卡片降级为占位文案（如"AI摘要暂不可用"），不阻塞页面渲染。
- **开发者视角**：
  - 新增 `analytics_insights` Service + Router，若 #41 已完成则接入真实 AI 端点；若 #41 未完成则返回硬编码占位响应。
  - 前端 `AiSummaryCard`组件以 React TSX 实现，通过 `useEffect` 调用 `/analytics/insights` GET 端点。

### 1.3 不做什么（剔除）

- [ ] **不要**实现 #41 AI Agent Framework 本身（仅调用其端点或返回占位）
- [ ] **不要**修改现有图表组件或 `/analytics` 路由的返回结构
- [ ] **不要**引入新的数据库模型或 Migration（本功能为只读调用）
- [ ] **不要**在 AI 后端不可用时阻塞页面渲染

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → ≥ 3 passed（stub 模式下至少3 条 case：正常、降级、异常）
- `PYTHONPATH=src ruff check src/api/routers/analytics_insights.py` → 0 errors
- `PYTHONPATH=src ruff check frontend/components/analytics/AiSummaryCard.tsx` → 0 errors（若存在 TSX lint 配置）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/analytics.py` L? — 现有 `/analytics` 路由实现，返回图表数据

TBD - 待验证：`frontend/components/analytics/` L? —现有 Analytics页面组件文件夹结构

TBD - 待验证：是否存在前端 TSX 文件需要读取以了解现有组件模式### 2.2 涉及文件清单

- 要改：
  - `frontend/components/analytics/AiSummaryCard.tsx` — 新增 AI 摘要卡片组件，渲染于图表区上方
  - `frontend/components/analytics/AnalyticsPage.tsx`（TBD - 待确认文件名）—引入并挂载 `AiSummaryCard`
- 要建：
  - `src/api/routers/analytics_insights.py` — 新增 router，提供 GET `/analytics/insights` 端点
  - `src/services/analytics_insights_service.py` — 新增 service，含 `get_summary` 方法（#41 完成前返回占位）
  - `tests/unit/test_analytics_insights.py` —单元测试（含占位路径和降级 case）

### 2.3 缺什么

- [ ] `/analytics/insights` 端点不存在，调用方无数据来源
- [ ] 前端 `AiSummaryCard` 组件不存在，页面无法渲染 AI 摘要卡
- [ ] 缺少降级机制：AI 后端不可用时需让卡片优雅降级（而非报错白屏）
- [ ] 缺少 `#41`（AI Agent Framework）是否已完成的检测逻辑，或桩代码占位路径

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/analytics_insights.py` | GET `/analytics/insights` 端点，根据 #41 完成状态返回 AI摘要或占位 |
| `src/services/analytics_insights_service.py` | `AnalyticsInsightsService`，含 `get_summary(tenant_id)` 方法 |
| `tests/unit/test_analytics_insights.py` | 单元测试：覆盖占位响应、降级逻辑 |
| `frontend/components/analytics/AiSummaryCard.tsx` | React TSX 卡片组件，调用 `/analytics/insights` 并渲染摘要文本 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待确认：`frontend/components/analytics/AnalyticsPage.tsx` | 在现有图表组件上方导入并渲染 `<AiSummaryCard />` |

### 3.3 新增能力

- **API endpoint**：`GET /analytics/insights` → `{"success": true, "data": {"summary": "...", "degraded": false}}`
- **Service method**：`AnalyticsInsightsService.get_summary(session: AsyncSession, tenant_id: int, period: str) -> dict`
- **前端组件**：`AiSummaryCard.tsx`，挂载于 `/analytics` 页面顶部；若 `degraded: true` 或请求异常，渲染占位文案

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **路由路径选 `/analytics/insights` 而非独立 prefix**：Analytics 相关能力统一在同一路径下，符合本repo路由约定
- **在 service 层做 #41 可用检测，而非 router 层**：将 #41 依赖封装在 service `get_summary` 内部，router 只调用 service，保持接口稳定
- **降级信号通过 response body `degraded: bool` 传递，而非 HTTP 4xx**：避免让"AI不可用"变成异常，允许多次重试而不触发告警

### 4.2 版本约束

<!-- 无新引入第三方依赖| 依赖 | 版本 | 理由 |
|------|------|------|
| `<pkg>` | `1.2.3` | [为什么这个版本] |

-->

### 4.3 兼容性约束

- 多租户：`get_summary` 每次调用必须以 `tenant_id`过滤数据（即使当前为只读桩代码）
- Service `__init__`签名为 `def __init__(self, session: AsyncSession)` — **无默认值**
- Service **不调用** `.to_dict()`，返回 Python `dict` 或 ORM 对象
- Service 出错时抛 `AppException`，**不返回** `ApiResponse.error()`
- Router 层注入 session：`session: AsyncSession = Depends(get_db)`，**不使用** `async with get_db()`

### 4.4 已知坑

1. **前端组件若在 SSR/SSG 环境中运行，`window` / `fetch` 未定义** → 规避：使用 `useEffect` 确保在客户端才发起请求，且添加 `if (!mounted) return placeholder`
2. **桩代码与真实 AI 后端并行维护，存在功能漂移风险** → 规避：桩代码使用 `TO_BE_REPLACED` 常量标记，README.md §2.12 要求每次真实端点就绪时同步删除占位分支
3. **Alembic 本板块不涉及 migration**，但若后续 AI 结果存储引入新表，需注意 `sa.JSON()` vs `sa.JSONB()`差异及 `DateTime` 列的 `timezone=True`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `AnalyticsInsightsService`（桩代码）

创建 `src/services/analytics_insights_service.py`，实现 `get_summary` 方法：

- 当前阶段：直接返回硬编码占位结果 `{"summary": "AI insights are being trained — check back soon.", "degraded": true}`
- 检测机制留待 #41 就绪后改为检测 `AI_AGENT_ENDPOINT` 环境变量并调用真实接口

操作：
- a) 创建 `src/services/analytics_insights_service.py`
- b) 写入 `AnalyticsInsightsService` 类，方法签名：`async def get_summary(self, tenant_id: int, period: str = "current") -> dict`
- c) 当前实现返回桩数据含 `degraded: True` 标志

```python
# src/services/analytics_insights_service.py
from sqlalchemy.ext.asyncio import AsyncSessionSTUB_SUMMARY = "AI insights are being trained — check back soon."
ENV_AI_ENDPOINT = "AI_AGENT_ENDPOINT"  # set by #41


class AnalyticsInsightsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_summary(self, tenant_id: int, period: str = "current") -> dict:
        # TODO(#41): replace stub with real call when AI_AGENT_ENDPOINT is set
        return {"summary": STUB_SUMMARY, "degraded": True}
```

**完成判定**：`PYTHONPATH=src python -c "from services.analytics_insights_service import AnalyticsInsightsService; print('import ok')"` → exit 0

---

### Step 2: 创建 `GET /analytics/insights` Router

创建 `src/api/routers/analytics_insights.py`：

- `GET /analytics/insights` 端点，接受 query param `period`（默认 "current"）
- 调用 `AnalyticsInsightsService(session).get_summary(tenant_id, period)`
- 返回 envelope：`{"success": True, "data": {...}}`

操作：
- a) 创建 `src/api/routers/analytics_insights.py`
- b)写入 router，注入 `session: AsyncSession = Depends(get_db)`、auth context
- c) 注册到 `src/main.py` APIRouter 树中（在 `analytics` router附近）

```python
# src/api/routers/analytics_insights.py
from fastapi import APIRouter, Depends, Queryfrom sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from dependencies import require_auth, AuthContext
from services.analytics_insights_service import AnalyticsInsightsService

router = APIRouter(prefix="/analytics", tags=["Analytics Insights"])


@router.get("/insights")
async def get_analytics_insights(
    period: str = Query(default="current"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsInsightsService(session)
    result = await svc.get_summary(tenant_id=ctx.tenant_id, period=period)
    return {"success": True, "data": result}
```

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/analytics_insights.py` →0 errors

---

### Step 3: 编写单元测试（桩代码阶段）

创建 `tests/unit/test_analytics_insights.py`：

- `MockState` + `MockRow` + `make_mock_session` 来自 `tests/unit/conftest.py`
- 测试用例：
  1. `test_get_summary_returns_degraded_stub`：验证 service 在桩模式下返回 `degraded: True`
  2. `test_get_summary_includes_tenant_id`：验证 service接收并处理 `tenant_id`
  3. `test_router_returns_envelope`：验证 router 返回 `{"success": true, "data": {...}}`

操作：
- a) 创建 `tests/unit/test_analytics_insights.py`
- b) 定义 `mock_db_session` fixture- c)编写 3 条以上 `async def test_...` 函数，用 `pytest.raises`验证错误路径

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → ≥ 3 passed

---

### Step 4: 创建前端 `AiSummaryCard.tsx` 组件创建 `frontend/components/analytics/AiSummaryCard.tsx`：

- 使用 React `useState` + `useEffect`
- 挂载时 `fetch(/analytics/insights?period=current)`，捕获异常并降级
- 渲染 `<div class="ai-summary-card">` 含摘要文字；若 `degraded` 或 fetch失败，渲染占位文案

操作：
- a) 创建 `frontend/components/analytics/AiSummaryCard.tsx`
- b) 实现 fetch逻辑 + error boundary（`try/catch`）
- c)导出 `AiSummaryCard`命名组件

```tsx
// frontend/components/analytics/AiSummaryCard.tsx
import { useEffect, useState } from "react";

interface InsightsResponse {
  summary: string;
  degraded: boolean;
}

export function AiSummaryCard() {
  const [text, setText] = useState<string | null>(null);
  const [degraded, setDegraded] = useState(false);

  useEffect(() => {
    fetch("/analytics/insights?period=current", { credentials: FETCHCredentials })
      .then((r) => r.json())
      .then((j: { data: InsightsResponse }) => {
        setText(j.data.summary);
        setDegraded(j.data.degraded);
      })
      .catch(() => {
        setText("AI摘要暂不可用，请稍后再试。");
        setDegraded(true);
      });
  }, []);

  return (
    <div className={`ai-summary-card${degraded ? " degraded" : ""}`}>
      {text ?? "加载中…"}
    </div>
  );
}
```

**完成判定**：`ls frontend/components/analytics/AiSummaryCard.tsx` → 文件存在 / 前端构建 `tsc --noEmit` exit 0

---

### Step 5: 将 `AiSummaryCard` 挂载到 Analytics 页面

TBD - 待确认：`frontend/components/analytics/` 中的 Analytics 主页面文件名（如 `AnalyticsPage.tsx` 或 `index.tsx`）

操作：
- a) 在 Analytics 主页面组件顶部 import `AiSummaryCard`
- b) 在现有图表渲染之前插入 `<AiSummaryCard />`
- c) 确保 import path 使用相对于文件的相对路径

**完成判定**：`ls frontend/components/analytics/AiSummaryCard.tsx` → exists / `git diff frontend/components/analytics/AnalyticsPage.tsx` 含新增组件引用

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/api/routers/analytics_insights.py src/services/analytics_insights_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → ≥ 3 passed
- [ ] `PYTHONPATH=src python -c "from services.analytics_insights_service import AnalyticsInsightsService; from api.routers.analytics_insights import router; print('routes:', [r.path for r in router.routes])"` → 含 `/insights`
- [ ] `ls frontend/components/analytics/AiSummaryCard.tsx` → 文件存在
- [ ] `cat frontend/components/analytics/AiSummaryCard.tsx | grep -E "AiSummaryCard|fetch|/analytics/insights"` → 3+ matches

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #41 AI Agent Framework迟迟不就绪，桩代码长期在生产跑 | 中 | 低 |桩代码已返回 `degraded: true`，前端降级文案已覆盖，不影响业务核心功能；建立 TODO追踪 #41 完成节点 |
| 前端 fetch `/analytics/insights` 因网络抖动失败，卡片显示加载中并最终超时 | 低 | 低 | `useEffect` 中 `catch` 块捕获异常并显示占位文案 `"AI 摘要暂不可用"`，不阻塞页面 |
| 多租户数据泄露：未传 `tenant_id` 或 mock session验证不充分 | 低 | 高 | `AnalyticsInsightsService` 方法签名强制要求 `tenant_id`；单元测试覆盖 tenant_id 传导路径 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/analytics_insights.py src/services/analytics_insights_service.py tests/unit/test_analytics_insights.py frontend/components/analytics/AiSummaryCard.tsx
git commit -m "feat(analytics): add AI summary card to dashboard (#546)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): add AI summary card to dashboard (#546)" --body "Closes #546"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/api/routers/analytics.py` L? — 现有 analytics router模式
- 父 issue /关联：#546, #56, #545
- 依赖 AI 功能：#41 (AI Agent Framework)
