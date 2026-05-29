# Customer Detail · Activities, Opportunities, Tickets tabs

| 元数据 | 值 |
|---|---|
| Issue | #559 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [Customer Detail — Overview Tab #558](../50-automation/0558-customer-detail-overview-tab.md) |
| 启用后赋能 | [Customer Detail — Full Page #53](../README.md#53) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The Customer Detail page (started in #558) currently only shows the Overview tab. The three remaining tabs — Activities, Opportunities, and Tickets — are missing. Each of these maps to an existing backend endpoint, and all three are required for the page to be considered complete per the parent issue #53. Without them the detail page is unfinished and unusable for real CRM workflows.

### 1.2 做完后

- **用户视角**：On the Customer Detail page, the user can switch between Overview, Activities, Opportunities, and Tickets. The Activities tab shows a timeline (emails, calls, meetings). The Opportunities and Tickets tabs show related lists fetched from their respective APIs. All tabs display loading and empty states correctly.
- **开发者视角**：Three new React tab components (`ActivitiesTab`, `OpportunitiesTab`, `TicketsTab`) and three data-fetching hooks (`useActivities`, `useOpportunities`, `useTickets`) are available in `src/`. The existing `CustomerDetailPage` in #558 wires in these tabs via a tab-switching UI.

### 1.3 不做什么（剔除）

- [ ] Backend APIs for activities, opportunities, and tickets are NOT implemented in this board — they are assumed to already exist (or be handled by separate backend boards)
- [ ] Full create/edit forms for any of the three entities are NOT in scope — only read/display tabs
- [ ] The tab routing (URL params per tab) is NOT in scope; tabs switch in-page only

### 1.4 关键 KPI

- [KPI 1：`ruff check src/` → 0 errors in any new or touched frontend file]
- [KPI 2：All three tabs render without console errors in the browser]
- [KPI 3：Each tab component has at least one unit test covering loading/empty/data states]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/` 目录下 `CustomerDetailPage` 组件和 `useCustomer` hook 的实现（由 #558 产出）

Prior board #558 introduced the `CustomerDetailPage` route and the Overview tab. The tab-switching container UI (tabs bar + active tab panel) is assumed to exist. This board adds the three missing tab panel components and their data-fetching hooks.

### 2.2 涉及文件清单

- 要改：
  - `src/pages/customers/CustomerDetailPage.tsx` — wire in the three new tab panels
  - `src/hooks/useCustomer.ts` — add hooks for activities/opportunities/tickets (or create separate hook files)
- 要建：
  - `src/components/customers/tabs/ActivitiesTab.tsx` — timeline tab panel
  - `src/components/customers/tabs/OpportunitiesTab.tsx` — related list tab panel
  - `src/components/customers/tabs/TicketsTab.tsx` — related list tab panel
  - `src/hooks/useActivities.ts` — fetch activities for a customer
  - `src/hooks/useOpportunities.ts` — fetch opportunities for a customer
  - `src/hooks/useTickets.ts` — fetch tickets for a customer
  - `tests/unit/test_activities_tab.ts` — unit test for ActivitiesTab
  - `tests/unit/test_opportunities_tab.ts` — unit test for OpportunitiesTab
  - `tests/unit/test_tickets_tab.ts` — unit test for TicketsTab

### 2.3 缺什么

- [ ] `ActivitiesTab` component — renders a timeline of activity events (email, call, meeting) fetched from `/customers/{id}/activities`
- [ ] `OpportunitiesTab` component — renders a list of related opportunities fetched from `/customers/{id}/opportunities`
- [ ] `TicketsTab` component — renders a list of related tickets fetched from `/customers/{id}/tickets`
- [ ] `useActivities(customerId)` hook — calls the activities endpoint, returns `{ data, isLoading, error }`
- [ ] `useOpportunities(customerId)` hook — calls the opportunities endpoint, returns `{ data, isLoading, error }`
- [ ] `useTickets(customerId)` hook — calls the tickets endpoint, returns `{ data, isLoading, error }`
- [ ] Tab wiring in `CustomerDetailPage` — tab bar already exists from #558; needs to mount the new panels on tab selection

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/components/customers/tabs/ActivitiesTab.tsx` | React component rendering activity timeline (email, call, meeting entries) |
| `src/components/customers/tabs/OpportunitiesTab.tsx` | React component rendering related opportunities list |
| `src/components/customers/tabs/TicketsTab.tsx` | React component rendering related tickets list |
| `src/hooks/useActivities.ts` | Data-fetching hook: GET `/customers/{id}/activities` |
| `src/hooks/useOpportunities.ts` | Data-fetching hook: GET `/customers/{id}/opportunities` |
| `src/hooks/useTickets.ts` | Data-fetching hook: GET `/customers/{id}/tickets` |
| `tests/unit/test_activities_tab.ts` | Unit tests for ActivitiesTab (loading, empty, data states) |
| `tests/unit/test_opportunities_tab.ts` | Unit tests for OpportunitiesTab (loading, empty, data states) |
| `tests/unit/test_tickets_tab.ts` | Unit tests for TicketsTab (loading, empty, data states) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/pages/customers/CustomerDetailPage.tsx` | Import and mount ActivitiesTab, OpportunitiesTab, TicketsTab in the tab panel area |

### 3.3 新增能力

- **React component**：`ActivitiesTab` — renders activity timeline grouped by date, with icon per activity type (email/call/meeting)
- **React component**：`OpportunitiesTab` — renders a table/list of opportunity rows (name, stage, amount, close date)
- **React component**：`TicketsTab` — renders a list of ticket rows (subject, status, priority)
- **React hook**：`useActivities(customerId: number)` → `{ activities: Activity[], isLoading: boolean, error: string | null }`
- **React hook**：`useOpportunities(customerId: number)` → `{ opportunities: Opportunity[], isLoading: boolean, error: string | null }`
- **React hook**：`useTickets(customerId: number)` → `{ tickets: Ticket[], isLoading: boolean, error: string | null }`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Own hook files per entity over one monolithic `useCustomerDetail`**：Each tab may be mounted independently in the future (e.g. in a dashboard widget). Separate hooks keep them decoupled and testable in isolation.
- **Inline empty state over a shared `<EmptyState>` component**：Unless a shared `EmptyState` component already exists in the repo (TBD - 待验证), each tab renders its own empty message to keep the board self-contained. If a shared component is found, refactor as a follow-up.

### 4.2 版本约束

TBD - 待验证：Node / React / TypeScript 版本约束（查看 `package.json`）

### 4.3 兼容性约束

- All API calls must pass the current tenant's auth token (rely on the existing `apiClient` singleton used by `useCustomer` in #558)
- All API responses are paginated — hooks should handle the `{ items: [...], total: N }` envelope shape used by other frontend hooks in this repo
- Components must render loading skeletons or spinners while `isLoading` is true
- Components must render a friendly empty-state message when the array is empty (not crash or show blank)

### 4.4 已知坑

1. **Activities timeline grouping** → 规避：Group by date (`YYYY-MM-DD`) client-side from the `created_at` field; do not rely on the backend returning grouped data unless confirmed
2. **Opportunities / Tickets list overflow** → 规避：Use pagination controls (page + page_size query params) consistent with the existing list pages in this repo; do not load all records at once
3. **Auth token expiry** → 规避：Hooks should handle 401 responses by returning an `error` string; the page-level auth guard (from #558) is responsible for redirect; do not implement a separate re-auth flow inside the hooks

---

## 5. 实现步骤（按顺序）

### Step 1: Create data-fetching hooks (useActivities, useOpportunities, useTickets)

Create three hook files in `src/hooks/`. Each hook:
- Accepts `customerId: number` as a parameter
- Calls `apiClient.get('/customers/{customerId}/activities')` (and /opportunities, /tickets respectively)
- Returns `{ data: T[], isLoading: boolean, error: string | null }`
- Uses React Query or the existing fetching pattern from #558 (TBD - 待验证：确认本项目使用 React Query 还是手写 fetch wrapper）

```typescript
// src/hooks/useActivities.ts
import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/apiClient';

export interface Activity {
  id: number;
  type: 'email' | 'call' | 'meeting';
  subject: string;
  body?: string;
  created_at: string;
  tenant_id: number;
}

export function useActivities(customerId: number) {
  const [data, setData] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!customerId) return;
    setIsLoading(true);
    apiClient.get(`/customers/${customerId}/activities`)
      .then(res => setData(res.data?.items ?? []))
      .catch(err => setError(err.message ?? 'Failed to load activities'))
      .finally(() => setIsLoading(false));
  }, [customerId]);

  return { data, isLoading, error };
}
```

**完成判定**：`ruff check src/hooks/useActivities.ts src/hooks/useOpportunities.ts src/hooks/useTickets.ts` → 0 errors

---

### Step 2: Create ActivitiesTab component

Create `src/components/customers/tabs/ActivitiesTab.tsx`. The component:
- Imports and calls `useActivities(customerId)`
- Groups `data` by date string (YYYY-MM-DD from `created_at`)
- Renders each group as a date heading with a vertical timeline of activity entries
- Each entry shows: type icon (email/call/meeting SVG or emoji as fallback), subject, body snippet, timestamp
- While `isLoading`: renders 3-5 skeleton placeholder rows
- While `error` is non-null: renders an error alert div
- While `data.length === 0`: renders "No activities recorded yet."

```typescript
// src/components/customers/tabs/ActivitiesTab.tsx
import { useActivities } from '@/hooks/useActivities';

interface Props {
  customerId: number;
}

export function ActivitiesTab({ customerId }: Props) {
  const { data, isLoading, error } = useActivities(customerId);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) return <div className="text-red-600">{error}</div>;

  if (data.length === 0) {
    return <p className="text-gray-500">No activities recorded yet.</p>;
  }

  const grouped = data.reduce<Record<string, typeof data>>((acc, item) => {
    const date = item.created_at.split('T')[0];
    (acc[date] ??= []).push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([date, items]) => (
        <div key={date}>
          <h4 className="text-sm font-semibold text-gray-500 mb-2">{date}</h4>
          <ul className="relative border-l border-gray-200 pl-6 space-y-4">
            {items.map(activity => (
              <li key={activity.id} className="relative">
                <span className="absolute -left-3 top-1 w-4 h-4 rounded-full bg-blue-500" />
                <p className="font-medium">{activity.subject}</p>
                <p className="text-sm text-gray-600">{activity.type}</p>
                {activity.body && <p className="text-sm text-gray-700 mt-1">{activity.body}</p>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
```

**完成判定**：`ruff check src/components/customers/tabs/ActivitiesTab.tsx` → 0 errors

---

### Step 3: Create OpportunitiesTab component

Create `src/components/customers/tabs/OpportunitiesTab.tsx`. The component:
- Imports and calls `useOpportunities(customerId)`
- Renders a table with columns: Name, Stage, Amount, Close Date, Status
- Each row maps one opportunity object
- While `isLoading`: renders 3 skeleton table rows
- While `error` is non-null: renders an error alert div
- While `data.length === 0`: renders "No opportunities found."

```typescript
// src/components/customers/tabs/OpportunitiesTab.tsx
import { useOpportunities } from '@/hooks/useOpportunities';

interface Props {
  customerId: number;
}

export function OpportunitiesTab({ customerId }: Props) {
  const { data, isLoading, error } = useOpportunities(customerId);

  if (isLoading) {
    return (
      <table className="w-full text-sm">
        <tbody>
          {[1, 2, 3].map(i => (
            <tr key={i} className="border-b">
              <td className="py-3"><div className="h-4 w-32 bg-gray-100 rounded animate-pulse" /></td>
              <td className="py-3"><div className="h-4 w-20 bg-gray-100 rounded animate-pulse" /></td>
              <td className="py-3"><div className="h-4 w-16 bg-gray-100 rounded animate-pulse" /></td>
              <td className="py-3"><div className="h-4 w-24 bg-gray-100 rounded animate-pulse" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (error) return <div className="text-red-600">{error}</div>;

  if (data.length === 0) {
    return <p className="text-gray-500">No opportunities found.</p>;
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-gray-500 border-b">
          <th className="pb-2">Name</th>
          <th className="pb-2">Stage</th>
          <th className="pb-2">Amount</th>
          <th className="pb-2">Close Date</th>
        </tr>
      </thead>
      <tbody>
        {data.map(opp => (
          <tr key={opp.id} className="border-b hover:bg-gray-50">
            <td className="py-2">{opp.name}</td>
            <td className="py-2">{opp.stage}</td>
            <td className="py-2">{opp.amount}</td>
            <td className="py-2">{opp.close_date ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**完成判定**：`ruff check src/components/customers/tabs/OpportunitiesTab.tsx` → 0 errors

---

### Step 4: Create TicketsTab component

Create `src/components/customers/tabs/TicketsTab.tsx`. The component:
- Imports and calls `useTickets(customerId)`
- Renders a list with rows showing: Subject, Status badge, Priority, Created date
- While `isLoading`: renders 3 skeleton list rows
- While `error` is non-null: renders an error alert div
- While `data.length === 0`: renders "No tickets found."

```typescript
// src/components/customers/tabs/TicketsTab.tsx
import { useTickets } from '@/hooks/useTickets';

interface Props {
  customerId: number;
}

const STATUS_COLORS: Record<string, string> = {
  open: 'bg-yellow-100 text-yellow-800',
  closed: 'bg-green-100 text-green-800',
  pending: 'bg-blue-100 text-blue-800',
};

export function TicketsTab({ customerId }: Props) {
  const { data, isLoading, error } = useTickets(customerId);

  if (isLoading) {
    return (
      <ul className="space-y-3">
        {[1, 2, 3].map(i => (
          <li key={i} className="h-14 bg-gray-100 rounded animate-pulse" />
        ))}
      </ul>
    );
  }

  if (error) return <div className="text-red-600">{error}</div>;

  if (data.length === 0) {
    return <p className="text-gray-500">No tickets found.</p>;
  }

  return (
    <ul className="space-y-2">
      {data.map(ticket => (
        <li key={ticket.id} className="flex items-center justify-between p-3 border rounded hover:bg-gray-50">
          <div>
            <p className="font-medium text-sm">{ticket.subject}</p>
            <p className="text-xs text-gray-500">#{ticket.id} · Created {ticket.created_at?.split('T')[0]}</p>
          </div>
          <div className="flex gap-2 items-center">
            <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[ticket.status] ?? 'bg-gray-100 text-gray-700'}`}>
              {ticket.status}
            </span>
            <span className="text-xs text-gray-500">{ticket.priority}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
```

**完成判定**：`ruff check src/components/customers/tabs/TicketsTab.tsx` → 0 errors

---

### Step 5: Wire tabs into CustomerDetailPage

Edit `src/pages/customers/CustomerDetailPage.tsx`:
- Import `ActivitiesTab`, `OpportunitiesTab`, `TicketsTab`
- Import the `activeTab` state and tab-change handler from #558 (TBD - 待验证：确认 #558 导出的变量名）
- In the tab panel area (below the Overview tab `if (activeTab === 'overview')` block), add:

```typescript
if (activeTab === 'activities') {
  return <ActivitiesTab customerId={customerId} />;
}
if (activeTab === 'opportunities') {
  return <OpportunitiesTab customerId={customerId} />;
}
if (activeTab === 'tickets') {
  return <TicketsTab customerId={customerId} />;
}
```

Also add three new tab buttons to the tab bar (after the Overview tab button): Activities, Opportunities, Tickets.

**完成判定**：`ruff check src/pages/customers/CustomerDetailPage.tsx` → 0 errors

---

### Step 6: Write unit tests for all three tab components

Create `tests/unit/test_activities_tab.ts`, `tests/unit/test_opportunities_tab.ts`, `tests/unit/test_tickets_tab.ts`.

Each test file:
- Mocks the respective hook to return `{ data: [...], isLoading: false, error: null }` and asserts the component renders the expected data
- Mocks the hook to return `{ data: [], isLoading: false, error: null }` and asserts the empty-state message renders
- Mocks the hook to return `{ data: [], isLoading: true, error: null }` and asserts skeleton loaders render
- Mocks the hook to return `{ data: [], isLoading: false, error: 'Server error' }` and asserts the error message renders

```typescript
// tests/unit/test_activities_tab.ts
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ActivitiesTab } from '@/components/customers/tabs/ActivitiesTab';

vi.mock('@/hooks/useActivities', () => ({
  useActivities: vi.fn(),
}));

const { useActivities } = await import('@/hooks/useActivities');

describe('ActivitiesTab', () => {
  it('renders loading skeletons while loading', () => {
    useActivities.mockReturnValue({ data: [], isLoading: true, error: null });
    render(<ActivitiesTab customerId={1} />);
    expect(document.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('renders empty state when no data', () => {
    useActivities.mockReturnValue({ data: [], isLoading: false, error: null });
    render(<ActivitiesTab customerId={1} />);
    expect(screen.getByText(/No activities/i)).toBeTruthy();
  });

  it('renders activity entries', () => {
    useActivities.mockReturnValue({
      data: [{ id: 1, type: 'email', subject: 'Follow-up', body: 'Hi', created_at: '2026-01-01T10:00:00Z', tenant_id: 1 }],
      isLoading: false,
      error: null,
    });
    render(<ActivitiesTab customerId={1} />);
    expect(screen.getByText('Follow-up')).toBeTruthy();
  });

  it('renders error message', () => {
    useActivities.mockReturnValue({ data: [], isLoading: false, error: 'Network error' });
    render(<ActivitiesTab customerId={1} />);
    expect(screen.getByText('Network error')).toBeTruthy();
  });
});
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activities_tab.ts tests/unit/test_opportunities_tab.ts tests/unit/test_tickets_tab.ts -v` → all pass (or `vitest run` if using Vitest)

---

## 6. 验收

- [ ] `ruff check src/hooks/useActivities.ts src/hooks/useOpportunities.ts src/hooks/useTickets.ts src/components/customers/tabs/ActivitiesTab.tsx src/components/customers/tabs/OpportunitiesTab.tsx src/components/customers/tabs/TicketsTab.tsx src/pages/customers/CustomerDetailPage.tsx` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_activities_tab.ts tests/unit/test_opportunities_tab.ts tests/unit/test_tickets_tab.ts -v` → all passed (or `vitest run tests/unit/` → all passed if using Vitest)
- [ ] Tab bar on Customer Detail page shows all four tabs (Overview, Activities, Opportunities, Tickets)
- [ ] Clicking "Activities" tab renders the timeline (or empty-state message if no data)
- [ ] Clicking "Opportunities" tab renders the opportunities table (or empty-state message if no data)
- [ ] Clicking "Tickets" tab renders the tickets list (or empty-state message if no data)
- [ ] All three tabs display loading skeletons while their respective hook `isLoading` is true

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Backend endpoints for /activities, /opportunities, /tickets do not exist yet or return unexpected shape | 中 | 高 | Add a feature flag / early-return in each hook to show a "Data unavailable" placeholder; tabs degrade gracefully without crashing |
| #558 (CustomerDetailPage) is not merged yet, blocking Step 5 | 低 | 中 | Implement tabs in isolation against a local mock of `CustomerDetailPage`; rebase Step 5 once #558 lands |
| React Query or the existing fetch pattern in #558 changes | 低 | 中 | Hook interface (`{ data, isLoading, error }`) is intentionally compatible with both custom fetch and React Query; update `apiClient` calls without changing hook signatures |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/hooks/useActivities.ts src/hooks/useOpportunities.ts src/hooks/useTickets.ts \
       src/components/customers/tabs/ActivitiesTab.tsx \
       src/components/customers/tabs/OpportunitiesTab.tsx \
       src/components/customers/tabs/TicketsTab.tsx \
       src/pages/customers/CustomerDetailPage.tsx \
       tests/unit/test_activities_tab.ts \
       tests/unit/test_opportunities_tab.ts \
       tests/unit/test_tickets_tab.ts
git commit -m "feat(frontend): add Activities, Opportunities, Tickets tabs to Customer Detail page"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): Customer Detail — Activities, Opportunities, Tickets tabs" --body "Closes #559"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/pages/` 下已有 list page（如 opportunities list）的实现，作为 tab 内表格/列表渲染的参考
- 父 issue / 关联：#53 (Customer Detail — Full Page), #558 (Customer Detail — Overview Tab)
