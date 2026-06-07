# Campaign List UI · /marketing/campaigns table with filters and status badges

| 元数据 | 值 |
|---|---|
| Issue | #531 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | TBD - 待验证：父 issue #530 的 Campaign API 文档路径 |
| 启用后赋能 | TBD - 待验证：父 issue #62 的板卡路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #62 推进 Marketing CRM 前端，当前缺少一个集中的 Campaign 列表页面。现有的 campaign 相关功能散布或尚未实现，用户无法高效浏览、筛选已创建的市场活动。#530 已构建对应的后端 API endpoints，本板块负责将数据以结构化表格的形式呈现给用户，并提供筛选、排序等交互能力。

### 1.2 做完后

- **用户视角**：访问 `/marketing/campaigns` 可看到一张包含 Name、Type、Status、Sent Date、Open Rate、Click Rate 列的表格；顶部有状态筛选下拉框和排序控制；右上角有 "Create Campaign" 按钮；每条记录的状态字段以彩色徽章展示（draft=灰、scheduled=蓝、sending=黄、sent=绿、failed=红）。
- **开发者视角**：获得可复用的 `StatusBadge` 和 `SortableTable` 组件；`CampaignList` 页面通过 `campaignService`（由 #530 提供）获取数据，返回 ORM 对象经 router 序列化后的 dict；前端路由已在 `App.tsx` 中挂载。

### 1.3 不做什么（剔除）

- [ ] Campaign 创建表单页（`/marketing/campaigns/new` 及完整 CRUD edit/detail 页面）—— 属于后续子 issue
- [ ] 统计图表或 Analytics Dashboard —— 属于 #62 下的 analytics 子 issue
- [ ] 后端 API 实现 —— 由 #530 提供，本板块仅调用

### 1.4 关键 KPI

- `ruff check src/ui/` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_campaign_service.py -v` → 全 passed（含 #530 提供的 service 层测试）
- Campaign List 页面表格渲染 ≥ 6 列（name, type, status, sent date, open rate, click rate）
- 状态筛选切换后表格结果行数相应变化（前端逻辑验证）
- StatusBadge 在 draft / scheduled / sending / sent / failed 五种状态下分别显示不同背景色

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：TBD - 待验证：`src/ui/pages/marketing/CampaignList.tsx` 是否已存在（issue #530 提及需新建此文件）

请在实现前运行：
```bash
find src/ui -name "*.tsx" | grep -i campaign
find src/ui -name "*.tsx" | grep -i "table\|badge"
```
确认 CampaignList.tsx 是否为新建还是修改。

```tsx
// TBD — 参考同类页面结构（若存在 CustomerList 或 OpportunityList）
// 示例来自 TBD - 待验证：src/ui/pages/sales/CustomerList.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
// import { customerService } from '@/services/customerService';

export const CustomerList: React.FC = () => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const navigate = useNavigate();
  // ...
};
```

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/ui/pages/marketing/CampaignList.tsx` — 新建或修改列表页组件
  - TBD - 待验证：`src/ui/App.tsx`（或 `src/ui/router/index.tsx`） — 注册 `/marketing/campaigns` 路由
- 要建：
  - `src/ui/components/shared/StatusBadge.tsx` — 通用状态徽章组件
  - `src/ui/components/shared/SortableTable.tsx` — 可复用排序表格组件
  - `src/ui/components/campaign/CampaignTable.tsx` — Campaign 专属表格（封装 SortableTable）
  - `src/ui/components/campaign/CampaignFilters.tsx` — 状态筛选和排序控件
  - `src/ui/hooks/useCampaignList.ts` — 数据获取与状态管理 hook
  - `src/ui/services/campaignService.ts` — API 调用封装（依赖 #530 暴露的 endpoints）
  - `src/ui/types/campaign.ts` — Campaign 相关 TypeScript 类型定义

### 2.3 缺什么

- [ ] Campaign 列表页面组件（`/marketing/campaigns` 路由未注册）
- [ ] 可复用的彩色状态徽章组件（`StatusBadge`）
- [ ] 支持多列排序的表格组件（`SortableTable`）
- [ ] 状态筛选逻辑（draft / scheduled / sending / sent / failed）
- [ ] Campaign TypeScript 类型定义
- [ ] API 数据获取 hook（`useCampaignList`）
- [ ] 前端路由注册（`App.tsx` 或 router 配置）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/ui/components/shared/StatusBadge.tsx` | 通用状态徽章，接收 status 枚举输出彩色标签 |
| `src/ui/components/shared/SortableTable.tsx` | 可复用排序表格，封装列头点击排序逻辑 |
| `src/ui/components/campaign/CampaignTable.tsx` | Campaign 表格，列：name, type, status, sentDate, openRate, clickRate |
| `src/ui/components/campaign/CampaignFilters.tsx` | 状态筛选下拉框 + 排序控制栏 |
| `src/ui/hooks/useCampaignList.ts` | 封装 campaign API 调用、loading/error 状态、筛选参数 |
| `src/ui/services/campaignService.ts` | 封装 GET /campaigns 等前端 API 调用 |
| `src/ui/types/campaign.ts` | Campaign, CampaignStatus, CampaignType TypeScript 类型 |
| `src/ui/pages/marketing/CampaignList.tsx` | 页面入口，组合 Filters + Table + Create 按钮 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/ui/App.tsx` 或 `src/ui/router/index.tsx` | 注册 `Route path="/marketing/campaigns" element={<CampaignList />}` |
| TBD - 待验证：`src/ui/services/index.ts` 或 barrel file | 导出 `campaignService` 供页面使用 |

### 3.3 新增能力

- **React 组件**：`CampaignList` 页面渲染完整表格
- **共享组件**：`StatusBadge` 支持 5 种状态颜色；`SortableTable` 支持任意列排序
- **Hook**：`useCampaignList(status?: CampaignStatus, sortBy?: string, sortOrder?: 'asc'|'desc')`
- **API 集成**：GET `/campaigns`（带 status filter 和 sort params）
- **路由**：`/marketing/campaigns` → `CampaignList`
- **类型**：完整 TypeScript 类型覆盖，无 `any` 类型

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 React+Vite（现有栈）不选其他框架**：与仓库现有前端技术栈一致，降低学习成本
- **选受控的 SortableTable 组件不选第三方 DataGrid**：避免大型依赖；现有 CRM 数据量级用原生表格足够
- **选自定义 hook 而非 Redux/Zustand**：页面级状态无需全局 store，useCampaignList 足够清晰

### 4.2 版本约束

<!-- 无新增 npm 依赖，整段不适用 -->

### 4.3 兼容性约束

- 前端类型定义文件（`src/ui/types/`）须与 #530 后端返回的 JSON shape 完全对齐，避免 `undefined` 字段运行时错误
- API 返回数据中 `tenant_id` 不在 UI 表格列中展示，但前端 service 层须透传（依赖 #530 后端正确过滤多租户）
- `StatusBadge` 使用 CSS class 而非 inline style，便于后续统一主题管理

### 4.4 已知坑

1. **TypeScript 类型未对齐导致运行时 undefined** → 规避：在 `src/ui/types/campaign.ts` 中严格定义每个字段类型（含可选字段），并与 #530 后端 Pydantic schema 保持一致；前端 mock 数据测试须覆盖所有枚举值
2. **表格列排序与后端 API 参数不匹配** → 规避：`SortableTable` sort 参数值（如 `sent_date`）须与后端 endpoint 的 query param name 一致；在 `CampaignFilters.tsx` 中硬编码映射表

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 Campaign TypeScript 类型定义

定义 `CampaignStatus` 枚举（五种状态）和 `Campaign` 接口（含 id, name, type, status, sentDate, openRate, clickRate 等字段），确保与 #530 后端 Pydantic schema 字段名完全对齐。

```ts
// src/ui/types/campaign.ts
export enum CampaignStatus {
  Draft = 'draft',
  Scheduled = 'scheduled',
  Sending = 'sending',
  Sent = 'sent',
  Failed = 'failed',
}

export enum CampaignType {
  Email = 'email',
  SMS = 'sms',
  Social = 'social',
}

export interface Campaign {
  id: number;
  tenant_id: number;
  name: string;
  type: CampaignType;
  status: CampaignStatus;
  sent_date: string | null; // ISO 8601
  open_rate: number | null; // 0.0 - 1.0
  click_rate: number | null; // 0.0 - 1.0
  created_at: string;
  updated_at: string;
}
```

**完成判定**：`ruff check src/ui/types/campaign.ts` exit 0（若 ruff 未覆盖 TS 文件，则确认 `tsc --noEmit` 无错误）

---

### Step 2: 创建 StatusBadge 共享组件

新建 `StatusBadge`，接收 `status: CampaignStatus`，输出对应颜色的 `<span>` 标签。颜色规范：draft=gray、scheduled=blue、sending=yellow、sent=green、failed=red。

```tsx
// src/ui/components/shared/StatusBadge.tsx
import React from 'react';
import { CampaignStatus } from '@/types/campaign';

const STATUS_STYLES: Record<CampaignStatus, { label: string; className: string }> = {
  [CampaignStatus.Draft]:    { label: 'Draft',    className: 'badge-gray' },
  [CampaignStatus.Scheduled]: { label: 'Scheduled', className: 'badge-blue' },
  [CampaignStatus.Sending]:   { label: 'Sending',  className: 'badge-yellow' },
  [CampaignStatus.Sent]:      { label: 'Sent',     className: 'badge-green' },
  [CampaignStatus.Failed]:    { label: 'Failed',   className: 'badge-red' },
};

interface Props {
  status: CampaignStatus;
}

export const StatusBadge: React.FC<Props> = ({ status }) => {
  const { label, className } = STATUS_STYLES[status] ?? { label: status, className: 'badge-gray' };
  return <span className={`badge ${className}`}>{label}</span>;
};
```

**完成判定**：`StatusBadge` 可在 Storybook 或 `CampaignList.tsx` 中被 `import { StatusBadge } from '@/components/shared/StatusBadge'` 成功引用，编译无报错

---

### Step 3: 创建 SortableTable 共享组件

封装表格列头排序逻辑：支持 `columns` 配置数组（key, label, sortable）；点击列头切换 `sortBy`/`sortOrder` 并触发 `onSort` 回调；升序/降序箭头图标指示当前排序方向。

```tsx
// src/ui/components/shared/SortableTable.tsx
import React from 'react';

export interface Column<T> {
  key: keyof T | string;
  label: string;
  sortable?: boolean;
  render?: (value: unknown, row: T) => React.ReactNode;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  onSort: (key: string, order: 'asc' | 'desc') => void;
}

export function SortableTable<T>({ columns, data, sortBy, sortOrder, onSort }: Props<T>) {
  const handleHeaderClick = (col: Column<T>) => {
    if (!col.sortable) return;
    if (sortBy === col.key) {
      onSort(col.key as string, sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      onSort(col.key as string, 'asc');
    }
  };
  // ... render thead with sort arrows, tbody with data rows
}
```

**完成判定**：`SortableTable` 组件可被 `CampaignTable` 引用，TypeScript 泛型正确传递 Campaign 类型，无 `any`

---

### Step 4: 创建 CampaignService 和 useCampaignList hook

在 `src/ui/services/campaignService.ts` 封装对 `/campaigns` endpoint 的调用（带 status filter 和 sort params）。`useCampaignList` hook 内部调用 service，管理 `loading/error/data` 状态，接受筛选参数变化时自动重新请求。

```ts
// src/ui/services/campaignService.ts
import { Campaign, CampaignStatus } from '@/types/campaign';

const API_BASE = '/api/campaigns';

export const campaignService = {
  async listCampaigns(params?: {
    status?: CampaignStatus;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  }): Promise<{ items: Campaign[]; total: number }> {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.sort_by) qs.set('sort_by', params.sort_by);
    if (params?.sort_order) qs.set('sort_order', params.sort_order);
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    const res = await fetch(`${API_BASE}?${qs}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
};
```

```ts
// src/ui/hooks/useCampaignList.ts
import { useState, useEffect, useCallback } from 'react';
import { campaignService } from '@/services/campaignService';
import { Campaign, CampaignStatus } from '@/types/campaign';

export function useCampaignList(initialStatus?: CampaignStatus) {
  const [data, setData] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<CampaignStatus | undefined>(initialStatus);
  const [sortBy, setSortBy] = useState<string>('sent_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await campaignService.listCampaigns({ status, sort_by: sortBy, sort_order: sortOrder });
      setData(result.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [status, sortBy, sortOrder]);

  useEffect(() => { fetch(); }, [fetch]);

  return { data, loading, error, status, setStatus, sortBy, setSortBy, sortOrder, setSortOrder, refetch: fetch };
}
```

**完成判定**：`useCampaignList` hook 成功返回 `data: Campaign[]`、`loading`、`error` 状态，`setStatus` 触发重新 fetch

---

### Step 5: 创建 CampaignFilters 和 CampaignTable 组件

`CampaignFilters` 包含：状态筛选 `<select>`（All / Draft / Scheduled / Sending / Sent / Failed）、排序字段下拉框、排序方向切换按钮。

`CampaignTable` 组合 `SortableTable` 和 `StatusBadge`，定义六列表格：Name（可点击跳转）、Type、Status（`StatusBadge`）、Sent Date（格式化）、Open Rate（百分比）、Click Rate（百分比）。

```tsx
// src/ui/components/campaign/CampaignFilters.tsx 关键片段
<select value={status ?? ''} onChange={e => setStatus(e.target.value || undefined)}>
  <option value="">All</option>
  <option value="draft">Draft</option>
  <option value="scheduled">Scheduled</option>
  <option value="sending">Sending</option>
  <option value="sent">Sent</option>
  <option value="failed">Failed</option>
</select>

// CampaignTable.tsx 列定义片段
const columns: Column<Campaign>[] = [
  { key: 'name',      label: 'Name',      sortable: true },
  { key: 'type',      label: 'Type',      sortable: true },
  { key: 'status',    label: 'Status',    sortable: true, render: (_, row) => <StatusBadge status={row.status} /> },
  { key: 'sent_date', label: 'Sent Date', sortable: true, render: v => v ? formatDate(v as string) : '—' },
  { key: 'open_rate', label: 'Open Rate', sortable: true, render: v => v != null ? `${(v as number * 100).toFixed(1)}%` : '—' },
  { key: 'click_rate', label: 'Click Rate', sortable: true, render: v => v != null ? `${(v as number * 100).toFixed(1)}%` : '—' },
];
```

**完成判定**：`CampaignTable` 渲染 6 列，`StatusBadge` 正确显示 5 种颜色状态

---

### Step 6: 创建 CampaignList 页面并注册路由

组合 `CampaignFilters`、`CampaignTable`、`Create Campaign` 按钮；在 `App.tsx`（或 router 配置）注册 `/marketing/campaigns` 路由指向 `CampaignList`。

```tsx
// src/ui/pages/marketing/CampaignList.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CampaignFilters } from '@/components/campaign/CampaignFilters';
import { CampaignTable } from '@/components/campaign/CampaignTable';
import { useCampaignList } from '@/hooks/useCampaignList';

export const CampaignList: React.FC = () => {
  const { data, loading, error, status, setStatus, sortBy, setSortBy, sortOrder, setSortOrder } = useCampaignList();
  const navigate = useNavigate();

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Campaigns</h1>
        <button onClick={() => navigate('/marketing/campaigns/new')}>Create Campaign</button>
      </div>
      <CampaignFilters
        status={status} onStatusChange={setStatus}
        sortBy={sortBy} onSortByChange={setSortBy}
        sortOrder={sortOrder} onSortOrderChange={setSortOrder}
      />
      {loading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && <CampaignTable data={data} sortBy={sortBy} sortOrder={sortOrder} />}
    </div>
  );
};
```

路由注册（在 `App.tsx` 或 router/index.tsx 中新增）：

```tsx
// App.tsx 新增 route
<Route path="/marketing/campaigns" element={<CampaignList />} />
```

**完成判定**：`CampaignList` 组件可被 `App.tsx` 中的路由正确渲染，`navigate('/marketing/campaigns')` 跳转到列表页

---

## 6. 验收

- [ ] `ruff check src/ui/` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_campaign_service.py -v` → 全 passed（#530 service 层测试）
- [ ] `PYTHONPATH=src pytest tests/integration/test_campaign_integration.py -v` → 全 passed（如 #530 包含 integration 测试）
- [ ] Campaign List 表格渲染 6 列：name, type, status, sent_date, open_rate, click_rate
- [ ] 切换 status filter 下拉框，`data` 数组长度或内容相应变化
- [ ] `StatusBadge` 在 draft / scheduled / sending / sent / failed 五种状态下分别显示 5 种不同背景色

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #530 后端 API 字段名与前端类型定义不一致导致运行时错误 | 中 | 高 | 前端 `Campaign` 类型声明时所有字段均标为可选（`?`），在 `render` 中对 null 做兜底显示；收到后端确认 schema 后再补全必填 |
| 前端路由与 App.tsx 合并冲突（多人 PR 同时修改） | 低 | 中 | 本板块在独立分支开发，PR 合 master 时由 review 人工解决冲突；不使用 feature flag |
| React 测试环境未配置（Vitest / Jest） | 低 | 低 | 在 `package.json` scripts 中补充 `vitest` 测试命令（若仓库已有 Vitest 配置则直接使用） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/ui/components/shared/StatusBadge.tsx \
        src/ui/components/shared/SortableTable.tsx \
        src/ui/components/campaign/CampaignTable.tsx \
        src/ui/components/campaign/CampaignFilters.tsx \
        src/ui/hooks/useCampaignList.ts \
        src/ui/services/campaignService.ts \
        src/ui/types/campaign.ts \
        src/ui/pages/marketing/CampaignList.tsx \
        src/ui/App.tsx
git commit -m "feat(frontend): build /marketing/campaigns list page with filters and status badges"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): campaign list UI — #531" --body "Closes #531"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/ui/pages/sales/OpportunityList.tsx` — 表格+筛选+路由模式参考
- 父 issue / 关联：#531（本职），#530（依赖，后端 API），#62（父 issue，Marketing CRM Full-Stack）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
