# Campaign Stats · Build campaign stats UI page

| 元数据 | 值 |
|---|---|
| Issue | #533 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [#532 Build Campaign Stats Router + Service](), 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Campaign stats are currently not visible in the UI. Issue #532 exposes a stats router endpoint (GET/POST `/marketing/campaigns/{id}/stats`) and a `CampaignStatsService` — this board wires a frontend page to that endpoint. Without this step, the backend work in #532 is unconsumed.

### 1.2 做完后

- **用户视角**：Navigate to `/marketing/campaigns/:id` and see four stat cards (Sent / Delivered / Opened / Clicked), a performance-over-time line chart, an audience preview panel, and three action buttons (Launch / Pause / Resume). Clicking an action button calls the correct API and updates the campaign status.
- **开发者视角**：`CampaignStats.tsx` exposes a reusable stats layout. The component accepts a campaign ID from the route, calls `GET /marketing/campaigns/{id}/stats` on mount, and calls `POST /marketing/campaigns/{id}/action` on button click.

### 1.3 不做什么（剔除）

- [ ] Backend stats aggregation logic (handled in #532)
- [ ] Email/notification sending (handled in separate campaign-send board)
- [ ] A/B split testing UI (out of scope)
- [ ] Multi-campaign comparison view

### 1.4 关键 KPI

- [Stat cards render with non-zero values after calling `GET /marketing/campaigns/{id}/stats`]
- [Action buttons return HTTP 200 and the UI updates the campaign status label]
- [No TypeScript errors in `CampaignStats.tsx` after running `tsc --noEmit`]
- [Unit tests for `CampaignStats.tsx` achieve ≥ 80% branch coverage]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/ui/pages/marketing/` — existing marketing pages (list/detail) for reference; likely `CampaignList.tsx` or similar exists. L{?}-L{?}

TBD - 待验证：`src/api/routers/marketing/` — does `campaigns.py` or similar exist; are there existing action endpoints for campaigns. L{?}-L{?}

TBD - 待验证：`src/services/` — does `campaign_stats_service.py` (from #532) exist. L{?}-L{?}

### 2.2 涉及文件清单

- 要改：
  - `src/ui/pages/marketing/CampaignStats.tsx` — new file but parent directory needs to be verified
  - `src/ui/router.tsx` — add route for `/marketing/campaigns/:id`
  - `src/api/routers/marketing/campaigns.py` — add POST action endpoint (from #532)
  - `src/services/campaign_stats_service.py` — add action methods (from #532)
- 要建：
  - `src/ui/pages/marketing/CampaignStats.tsx` — main stats page
  - `src/ui/components/marketing/StatCard.tsx` — reusable stat card molecule
  - `src/ui/components/marketing/PerformanceChart.tsx` — line-chart molecule
  - `src/ui/components/marketing/AudiencePreview.tsx` — audience panel molecule
  - `src/ui/components/marketing/CampaignActionButtons.tsx` — Launch/Pause/Resume buttons
  - `tests/unit/test_campaign_stats.py` — unit tests for CampaignStats component
  - `tests/unit/test_stat_card.py` — unit tests for StatCard component

### 2.3 缺什么

- [ ] Frontend route for `/marketing/campaigns/:id`
- [ ] `CampaignStats.tsx` page component consuming `GET /marketing/campaigns/{id}/stats`
- [ ] Stat card component for sent/delivered/opened/clicked
- [ ] Performance line chart component
- [ ] Audience preview panel component
- [ ] Action buttons wired to `POST /marketing/campaigns/{id}/action`
- [ ] Unit tests for the new components

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/ui/pages/marketing/CampaignStats.tsx` | Main stats page; fetches stats on mount, renders stat cards + chart + audience + actions |
| `src/ui/components/marketing/StatCard.tsx` | Molecule: icon + label + value + delta badge |
| `src/ui/components/marketing/PerformanceChart.tsx` | Molecule: line chart (using Recharts or similar) over last 14 days |
| `src/ui/components/marketing/AudiencePreview.tsx` | Molecule: audience segment count and breakdown |
| `src/ui/components/marketing/CampaignActionButtons.tsx` | Molecule: Launch / Pause / Resume buttons with API calls |
| `tests/unit/test_campaign_stats.py` | Unit tests for CampaignStats.tsx |
| `tests/unit/test_stat_card.py` | Unit tests for StatCard.tsx |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/ui/router.tsx` | Add route: `/marketing/campaigns/:id` → `CampaignStats` |
| `src/api/routers/marketing/campaigns.py` | Add `POST /{id}/action` endpoint (action: launch/pause/resume) from #532 |
| `src/services/campaign_stats_service.py` | Add `trigger_action(campaign_id, action, tenant_id)` from #532 |

### 3.3 新增能力

- **Route**: `GET /marketing/campaigns/:id` (frontend router)
- **API endpoint**: `POST /marketing/campaigns/{id}/action` → `{"success": true, "data": {"status": "paused"}}`
- **Service method**: `CampaignStatsService.trigger_action(session, campaign_id, action, tenant_id) -> CampaignModel`
- **Frontend component**: `CampaignStats` (page), `StatCard`, `PerformanceChart`, `AudiencePreview`, `CampaignActionButtons`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Recharts for line chart** (not a custom SVG) — Recharts is the de-facto standard chart library for React in this repo (verify against existing `package.json`); pick Recharts LineChart with responsive container.
- **Stat card layout via flex row** — simple flex row of 4 cards; on narrow viewports stack to 2×2 grid via CSS Grid `grid-template-columns: repeat(2, 1fr)`.
- **Action button state machine** — derive button visibility from `campaign.status` field: `draft` → show Launch; `active` → show Pause; `paused` → show Resume. Disable buttons while API call is in-flight.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `recharts` | `^2.x` | TypeScript-first, widely used; verify against existing `package.json` |
| `react-router-dom` | `^6.x` | Already in use for client-side routing |

### 4.3 兼容性约束

- Multi-tenant: every API call must include `tenant_id` in headers (set by auth interceptor). The `GET /marketing/campaigns/{id}/stats` response must include `tenant_id` validation.
- Service returns ORM/dataclass objects, **not** `.to_dict()`; router handles serialization.
- Service errors raise `AppException` subclasses; router exception handler converts to JSON.
- All components are `React.FC` with typed props; no `any` without documented justification.

### 4.4 已知坑

1. **Recharts responsive container requires explicit width** → set `width="100%"` and wrap in a `<div style={{ width: '100%' }}>`; without it the chart renders at 0px width in some layouts.
2. **React Router v6 param typing** → use `useParams<{ id: string }>()` and convert to `number` via `parseInt(id, 10)` before API calls; handle `NaN` with a redirect to the campaign list.
3. **Button loading state race** — use `useState` per action type; do NOT share a single `isLoading` boolean across all three buttons, as pausing should not block the Resume button.

---

## 5. 实现步骤（按顺序）

### Step 1: Add POST action endpoint to campaigns router

Add `POST /marketing/campaigns/{id}/action` that accepts `{ "action": "launch" | "pause" | "resume" }`, calls `CampaignStatsService.trigger_action`, and returns the updated campaign status.

Operation:
- a) In `src/api/routers/marketing/campaigns.py` — add `campaign_action_router` or add to existing router
- b) Add Pydantic request body `CampaignActionRequest(action: Literal["launch", "pause", "resume"])`
- c) Add service method `CampaignStatsService.trigger_action` in `src/services/campaign_stats_service.py`

**完成判定**：`ruff check src/api/routers/marketing/campaigns.py` → 0 errors / `ruff check src/services/campaign_stats_service.py` → 0 errors

### Step 2: Add frontend route for `/marketing/campaigns/:id`

Operation:
- a) In `src/ui/router.tsx` — add route `{ path: '/marketing/campaigns/:id', element: <CampaignStats /> }`

**完成判定**：`npx tsc --noEmit src/ui/router.tsx` → 0 errors

### Step 3: Build `StatCard.tsx` molecule

A card showing one metric (label + large value + optional delta badge).

Operation:
- a) Create `src/ui/components/marketing/StatCard.tsx`
- b) Props: `label: string`, `value: number | string`, `delta?: number`, `icon?: ReactNode`
- c) Render flex row: icon + label left, value + delta right

```tsx
interface StatCardProps {
  label: string;
  value: number;
  delta?: number; // percentage change vs prior period
  icon?: React.ReactNode;
}

export const StatCard: React.FC<StatCardProps> = ({ label, value, delta, icon }) => (
  <div className="stat-card">
    <div className="stat-card__header">
      {icon && <span className="stat-card__icon">{icon}</span>}
      <span className="stat-card__label">{label}</span>
    </div>
    <div className="stat-card__body">
      <span className="stat-card__value">{value.toLocaleString()}</span>
      {delta !== undefined && (
        <span className={`stat-card__delta ${delta >= 0 ? 'positive' : 'negative'}`}>
          {delta >= 0 ? '+' : ''}{delta}%
        </span>
      )}
    </div>
  </div>
);
```

**完成判定**：`npx tsc --noEmit src/ui/components/marketing/StatCard.tsx` → 0 errors / `ruff check src/ui/components/marketing/StatCard.tsx` → 0 errors

### Step 4: Build `PerformanceChart.tsx` molecule

Line chart showing sent/delivered/opened/clicked over the last 14 days.

Operation:
- a) Create `src/ui/components/marketing/PerformanceChart.tsx` using Recharts `LineChart`, `XAxis`, `YAxis`, `Tooltip`, `Legend`, `Line`
- b) Props: `data: Array<{ date: string; sent: number; delivered: number; opened: number; clicked: number }>`
- c) One `Line` per metric; use different colors (blue=delivered, green=opened, orange=clicked)

**完成判定**：`npx tsc --noEmit src/ui/components/marketing/PerformanceChart.tsx` → 0 errors

### Step 5: Build `AudiencePreview.tsx` molecule

Panel showing audience segment name and estimated reach.

Operation:
- a) Create `src/ui/components/marketing/AudiencePreview.tsx`
- b) Props: `segmentName: string`, `estimatedReach: number`

**完成判定**：`npx tsc --noEmit src/ui/components/marketing/AudiencePreview.tsx` → 0 errors

### Step 6: Build `CampaignActionButtons.tsx` molecule

Launch / Pause / Resume buttons. Visibility controlled by `campaign.status`. Each button calls the POST action endpoint.

Operation:
- a) Create `src/ui/components/marketing/CampaignActionButtons.tsx`
- b) Props: `campaignId: number`, `status: 'draft' | 'active' | 'paused'`, `onStatusChange: (s: string) => void`
- c) Derived visibility: `draft` → show Launch; `active` → show Pause; `paused` → show Resume
- d) Each button fires `POST /marketing/campaigns/{id}/action` with `{ action: 'launch'|'pause'|'resume' }`; set local `isLoading` per action

**完成判定**：`npx tsc --noEmit src/ui/components/marketing/CampaignActionButtons.tsx` → 0 errors

### Step 7: Build `CampaignStats.tsx` page

Assemble the page from all molecules. Fetch stats on mount via `GET /marketing/campaigns/{id}/stats`. Handle loading and error states.

Operation:
- a) Create `src/ui/pages/marketing/CampaignStats.tsx`
- b) `useEffect` on mount: call `GET /marketing/campaigns/{id}/stats`, store response in state
- c) Render: header (campaign name + status badge), 4× `StatCard`, `PerformanceChart`, `AudiencePreview`, `CampaignActionButtons`
- d) Handle `loading: true` state (spinner) and `error` state (error message with retry button)

**完成判定**：`npx tsc --noEmit src/ui/pages/marketing/CampaignStats.tsx` → 0 errors

### Step 8: Write unit tests

Operation:
- a) `tests/unit/test_stat_card.py` — test delta badge positive/negative rendering, value formatting
- b) `tests/unit/test_campaign_stats.py` — mock API responses; test page renders stat cards with correct values, action buttons call correct endpoints

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_stat_card.py tests/unit/test_campaign_stats.py -v` → all passed

---

## 6. 验收

- [ ] `npx tsc --noEmit src/ui/pages/marketing/CampaignStats.tsx src/ui/components/marketing/StatCard.tsx src/ui/components/marketing/PerformanceChart.tsx src/ui/components/marketing/AudiencePreview.tsx src/ui/components/marketing/CampaignActionButtons.tsx` → 0 errors
- [ ] `ruff check src/api/routers/marketing/campaigns.py src/services/campaign_stats_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_stat_card.py tests/unit/test_campaign_stats.py -v` → all passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 0 errors (if #532 includes migrations)
- [ ] Action buttons: manually verify Launch/Pause/Resume buttons appear based on campaign status; each calls the correct API endpoint and updates the campaign status label

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #532 stats endpoint not ready when UI work starts | 中 | 中 | Block UI work until #532 merged; alternatively mock the API response in tests and wire real endpoint later |
| Recharts version mismatch in `package.json` | 低 | 中 | Pin Recharts to the version already in `package.json`; skip if not yet added |
| Performance chart renders empty if API returns empty `timeSeries` array | 低 | 低 | Add defensive rendering: show "No data yet" placeholder when array length === 0 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/ui/pages/marketing/CampaignStats.tsx \
       src/ui/components/marketing/StatCard.tsx \
       src/ui/components/marketing/PerformanceChart.tsx \
       src/ui/components/marketing/AudiencePreview.tsx \
       src/ui/components/marketing/CampaignActionButtons.tsx \
       src/ui/router.tsx \
       tests/unit/test_stat_card.py \
       tests/unit/test_campaign_stats.py
git commit -m "feat(frontend): build CampaignStats UI page

Closes #533"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): build CampaignStats UI page" --body "Closes #533"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/ui/pages/` — existing page components for reference on component + test patterns
- 父 issue / 关联：#62 (parent epic), #532 (stats router + service — must be merged first)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
