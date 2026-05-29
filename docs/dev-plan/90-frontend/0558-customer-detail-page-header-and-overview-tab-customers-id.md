# 客户详情页 · 客户详情头部与概览标签页

| 元数据 | 值 |
|---|---|
| Issue | #558 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [客户列表页](./0557-customer-list-page.md) |
| 启用后赋能 | 销售流程完整化（客户列表 → 客户详情 → 编辑/删除）；后续标签页（Activity Timeline、Notes）依赖此页面结构 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

目前系统缺少客户详情查看入口，用户无法从客户列表跳转到单一客户页面查看完整信息。列表页的 inline 编辑或弹窗模式无法承载完整的客户资料展示与操作需求。#557 完成后已有客户列表页和基础 API 端点，本 issue 在此基础上构建详情页面骨架（header + Overview 标签），为后续 Edit Modal、Delete 确认、Activity Timeline 等功能提供页面框架。

### 1.2 做完后

- **用户视角**：访问 `/customers/:id` 可看到客户详情头部（姓名、头像占位、状态徽章、Lead Tier 徽章）和 Overview 标签页（联系信息、公司详情、自定义字段）。页面右上角有 Edit 和 Delete 操作按钮。点击 Edit 打开编辑弹窗，Delete 弹出确认框。
- **开发者视角**：`GET /customers/:id` API 已存在（#557），本 issue 消费该端点渲染页面。新增 `CustomerDetailPage`、`CustomerHeader`、`OverviewTab` 组件，以及对应的 `customerApi.ts` 查询 hook。所有组件以 `tenant_id` 鉴权，路由受 auth guard 保护。

### 1.3 不做什么（剔除）

- [ ] Edit Modal 的实际提交逻辑（保存 API 调用 + 表单验证）— 归入后续 issue
- [ ] Delete 确认后的实际删除 API 调用 + 页面跳转 — 归入后续 issue
- [ ] Activity Timeline 标签页内容 — 归入独立 issue
- [ ] Notes 标签页内容 — 归入独立 issue
- [ ] 后端 API 端点实现（已在 #557 完成）
- [ ] 头像上传功能（仅展示占位符）

### 1.4 关键 KPI

- [KPI 1：`http://localhost:3000/customers/1` 页面渲染成功，无 404/500，header 和 Overview Tab 均可见]
- [KPI 2：`pytest tests/unit/test_customer_frontend.py -v`（待建）→ ≥ 4 passed（header render、tab switch、button present、no console.error）]
- [KPI 3：`ruff check src/frontend/` → 0 errors（如有 frontend lint 配置）]
- [KPI 4：`git diff --stat` 显示新增文件 ≤ 8 个，无新增依赖]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/frontend/pages/` 或 `src/pages/` 下是否有 customers 相关路由文件；现有客户 API 端点定义在 `src/api/routers/` 哪个文件中（L? 行附近有 `@router.get("/{customer_id}")`）；#557 完成后应在 `src/services/customer_service.py` 有 `get_customer` 方法

### 2.2 涉及文件清单

- 要改：
  - `src/frontend/App.tsx` 或 `src/App.tsx` — 新增 `/customers/:id` 路由注册
  - `src/frontend/api/customerApi.ts` — 新增 `getCustomer(id)` 查询函数（如 #557 未覆盖）
  - `tests/unit/test_customer_detail_page.py` — 新增组件测试（如 #557 无对应测试文件）
- 要建：
  - `src/frontend/pages/CustomerDetailPage.tsx` — 详情页主入口
  - `src/frontend/components/customer/CustomerHeader.tsx` — 头部组件
  - `src/frontend/components/customer/OverviewTab.tsx` — 概览标签组件
  - `tests/unit/test_customer_detail_page.py` — 详情页组件单元测试
  - `tests/unit/test_customer_header.py` — 头部组件测试
  - `tests/unit/test_overview_tab.py` — Overview 标签测试

### 2.3 缺什么

- [ ] 缺少 `GET /customers/:id` 的前端 API 调用函数（`getCustomer` hook）
- [ ] 缺少客户详情页路由 `/customers/:id` 在 `App.tsx` 中的注册
- [ ] 缺少 `CustomerHeader` 组件（姓名、头像占位、Status Badge、Lead Tier Badge、Edit + Delete 按钮）
- [ ] 缺少 `OverviewTab` 组件（联系信息卡片、公司详情卡片、自定义字段渲染）
- [ ] 缺少 Status Badge 和 Lead Tier Badge 的样式系统（可用 Tailwind CSS 或现有 design tokens）
- [ ] 缺少详情页的 loading skeleton / error boundary
- [ ] 缺少 Delete 确认弹窗（基础 UI 可在本 issue 搭建骨架）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/frontend/pages/CustomerDetailPage.tsx` | 客户详情页主入口，fetch 客户数据，下钻到 Header + OverviewTab |
| `src/frontend/components/customer/CustomerHeader.tsx` | 头部组件：姓名 + 头像占位 + Status Badge + Lead Tier Badge + Edit/Delete 按钮 |
| `src/frontend/components/customer/OverviewTab.tsx` | 概览标签：联系信息、公司详情、自定义字段展示 |
| `src/frontend/components/customer/StatusBadge.tsx` | 状态徽章组件（reusable） |
| `src/frontend/components/customer/LeadTierBadge.tsx` | Lead Tier 徽章组件（reusable） |
| `tests/unit/test_customer_detail_page.py` | 详情页主入口测试（Vitest + Testing Library） |
| `tests/unit/test_customer_header.py` | 头部组件测试 |
| `tests/unit/test_overview_tab.py` | OverviewTab 组件测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/frontend/App.tsx` | 新增 `<Route path="/customers/:id" element={<CustomerDetailPage />} />` |
| `src/frontend/api/customerApi.ts` | 新增 `getCustomer(id: number)` async 函数（调用 `GET /customers/:id`） |
| `tests/unit/test_customer_api.py` | 新增 `getCustomer` mock 测试（如文件存在） |

### 3.3 新增能力

- **页面路由**：`/customers/:id` → `CustomerDetailPage`（受 auth guard 保护）
- **API hook**：`getCustomer(id: number) → Promise<CustomerDetail>`（调用现有 `GET /customers/:id`）
- **UI 组件**：`CustomerHeader`（含 Edit/Delete 按钮占位）、`OverviewTab`、`StatusBadge`、`LeadTierBadge`
- **测试覆盖**：3 个新测试文件，覆盖 render、data display、button presence 场景

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **React Router v6 而非 Next.js Pages Router**：本项目前端为 SPA（FastAPI 提供 API），使用 React Router 管理 `/customers/:id` 路由，路径参数通过 `useParams()` 读取。
- **Tailwind CSS 而非 CSS Modules**：现有 frontend 使用 Tailwind，保持一致。
- **TanStack Query（React Query）管理服务端状态**：客户数据 fetch + loading/error 状态由 `useQuery` 封装，cache key 为 `['customer', id]`。
- **组件分层**：`StatusBadge` 和 `LeadTierBadge` 拆为独立可复用组件，避免 `CustomerHeader` 过于臃肿。

### 4.2 版本约束

TBD - 待验证：`package.json` 中 `react-router-dom` 版本、`@tanstack/react-query` 版本、`vitest` 版本

| 依赖 | 版本 | 理由 |
|------|------|------|
| `react-router-dom` | `^6.x` | 支持 `useParams` 和嵌套路由 |
| `@tanstack/react-query` | `^5.x` | `useQuery` hook 管理异步数据 |

### 4.3 兼容性约束

- 所有 API 调用必须携带认证 token（从 `localStorage` 或 context 获取），后端按 `tenant_id` 隔离数据
- API 错误（401/403/404）在 TanStack Query `onError` 中统一处理，401 跳转登录页
- Edit/Delete 按钮点击后需有 loading 状态（disabled + spinner），防止重复提交
- 页面刷新时 URL 中的 `:id` 必须有效（后端返回 404 而不是 500）

### 4.4 已知坑

1. **客户 ID 为字符串 URL 参数但 API 期望整数** → 规避：用 `parseInt(id, 10)` 转换并处理 `NaN` 情况（展示 "Invalid customer ID" 错误页）
2. **API 返回 null（客户不存在）时 `useQuery` 进入 error 状态** → 规避：TanStack Query `onError` 展示 "Customer not found" 空状态，不崩溃
3. **Edit Modal 后续实现时与 Header 的按钮状态同步** → 规避：按钮仅渲染骨架（`console.log` 或 `// TODO: open edit modal`），不引入状态管理框架
4. **前端测试环境 mock `fetch` 而非调用真实 API** → 规避：Vitest `vi.mock('@/api/customerApi')` 隔离 API 层，单元测试不依赖后端

---

## 5. 实现步骤（按顺序）

### Step 1: 新增客户详情 API hook

在 `src/frontend/api/customerApi.ts` 中新增 `getCustomer` 函数，调用 `GET /customers/:id`，返回 `CustomerDetail` 类型（含 `id`, `name`, `email`, `phone`, `status`, `lead_tier`, `company_name`, `company_address`, `custom_fields` 等字段）。

```typescript
// src/frontend/api/customerApi.ts
import type { CustomerDetail } from '../types/customer';

export async function getCustomer(id: number): Promise<CustomerDetail> {
  const token = localStorage.getItem('auth_token');
  const res = await fetch(`/api/customers/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch customer: ${res.status}`);
  }
  const data = await res.json();
  return data.data as CustomerDetail;
}
```

同时在 `src/frontend/types/customer.ts` 新增 `CustomerDetail` TypeScript 类型定义（如文件不存在则创建 `src/frontend/types/` 目录）。

**完成判定**：`ls src/frontend/api/customerApi.ts` 文件存在且含 `getCustomer` 函数声明 / `ruff check src/frontend/api/customerApi.ts` exit 0

---

### Step 2: 注册 `/customers/:id` 路由

在 `src/frontend/App.tsx` 的路由表中新增：

```tsx
// src/frontend/App.tsx
import CustomerDetailPage from './pages/CustomerDetailPage';

// 在 <Routes> 内添加：
<Route
  path="/customers/:id"
  element={
    <ProtectedRoute>
      <CustomerDetailPage />
    </ProtectedRoute>
  }
/>
```

确保 `ProtectedRoute` 已处理未登录用户跳转。

**完成判定**：`grep -n "customers/:id" src/frontend/App.tsx` 有输出 / `ruff check src/frontend/App.tsx` exit 0

---

### Step 3: 创建 CustomerHeader 组件

新建 `src/frontend/components/customer/CustomerHeader.tsx`：

- Props：`customer: CustomerDetail`
- 渲染：左侧姓名（大字）+ 头像占位（div with bg-gray-200 initials），右侧 `StatusBadge` + `LeadTierBadge`
- 底部一行：`Edit` 按钮（primary outline）和 `Delete` 按钮（danger outline），各带 `onClick` handler 骨架
- Loading 状态：`const { isLoading } = useQuery(...)` 控制 skeleton 显示

```tsx
// src/frontend/components/customer/CustomerHeader.tsx
import { StatusBadge } from './StatusBadge';
import { LeadTierBadge } from './LeadTierBadge';

interface Props {
  customer: CustomerDetail;
}

export function CustomerHeader({ customer }: Props) {
  return (
    <div className="flex items-center justify-between border-b pb-4">
      <div className="flex items-center gap-4">
        <div className="h-12 w-12 rounded-full bg-gray-200 flex items-center justify-center text-lg font-bold text-gray-500">
          {customer.name.charAt(0).toUpperCase()}
        </div>
        <div>
          <h1 className="text-2xl font-bold">{customer.name}</h1>
          <p className="text-sm text-gray-500">{customer.email}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <StatusBadge status={customer.status} />
        <LeadTierBadge tier={customer.lead_tier} />
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => console.log('Edit modal placeholder')}
          className="px-4 py-2 border border-blue-600 text-blue-600 rounded hover:bg-blue-50"
        >
          Edit
        </button>
        <button
          onClick={() => console.log('Delete confirmation placeholder')}
          className="px-4 py-2 border border-red-600 text-red-600 rounded hover:bg-red-50"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
```

同步创建 `StatusBadge.tsx` 和 `LeadTierBadge.tsx`。

**完成判定**：`ls src/frontend/components/customer/CustomerHeader.tsx` 文件存在 / `ruff check src/frontend/components/customer/` exit 0

---

### Step 4: 创建 OverviewTab 组件

新建 `src/frontend/components/customer/OverviewTab.tsx`：

- Props：`customer: CustomerDetail`
- 渲染两个 Card：`Contact Information` 和 `Company Details`
- `custom_fields` 通过 `Object.entries(customer.custom_fields)` 遍历渲染 key-value
- 若字段为空数组/对象，展示空状态文案（"No custom fields configured"）

```tsx
// src/frontend/components/customer/OverviewTab.tsx
interface Props {
  customer: CustomerDetail;
}

export function OverviewTab({ customer }: Props) {
  const hasCustomFields = customer.custom_fields && Object.keys(customer.custom_fields).length > 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
      {/* Contact Information Card */}
      <div className="border rounded p-4">
        <h2 className="text-lg font-semibold mb-3">Contact Information</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-gray-500">Email</dt>
            <dd>{customer.email ?? '—'}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Phone</dt>
            <dd>{customer.phone ?? '—'}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Status</dt>
            <dd>{customer.status ?? '—'}</dd>
          </div>
        </dl>
      </div>

      {/* Company Details Card */}
      <div className="border rounded p-4">
        <h2 className="text-lg font-semibold mb-3">Company Details</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-gray-500">Company</dt>
            <dd>{customer.company_name ?? '—'}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Address</dt>
            <dd>{customer.company_address ?? '—'}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Lead Tier</dt>
            <dd>{customer.lead_tier ?? '—'}</dd>
          </div>
        </dl>
      </div>

      {/* Custom Fields Card (full width) */}
      <div className="border rounded p-4 md:col-span-2">
        <h2 className="text-lg font-semibold mb-3">Custom Fields</h2>
        {hasCustomFields ? (
          <dl className="space-y-2 text-sm">
            {Object.entries(customer.custom_fields).map(([key, value]) => (
              <div key={key} className="flex justify-between">
                <dt className="text-gray-500">{key}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-gray-400 text-sm">No custom fields configured.</p>
        )}
      </div>
    </div>
  );
}
```

**完成判定**：`ls src/frontend/components/customer/OverviewTab.tsx` 文件存在 / `ruff check src/frontend/components/customer/` exit 0

---

### Step 5: 创建 CustomerDetailPage 主入口

新建 `src/frontend/pages/CustomerDetailPage.tsx`：

- 从 URL 拿 `id`：`const { id } = useParams<{ id: string }>()`
- `id` 转换：`const customerId = parseInt(id!, 10)`，NaN 时 render `<div>Invalid customer ID</div>`
- `useQuery` fetch 数据，key `['customer', customerId]`，queryFn `() => getCustomer(customerId)`
- `isLoading` → render `<div>Loading...</div>` 或 skeleton
- `isError` → render `<div>Customer not found</div>`
- `data` → render `<CustomerHeader customer={data} />` + `<OverviewTab customer={data} />`
- 外层 `<div className="p-6 max-w-5xl mx-auto">` 包裹

```tsx
// src/frontend/pages/CustomerDetailPage.tsx
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getCustomer } from '../api/customerApi';
import { CustomerHeader } from '../components/customer/CustomerHeader';
import { OverviewTab } from '../components/customer/OverviewTab';

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const customerId = parseInt(id ?? '', 10);

  if (isNaN(customerId)) {
    return <div className="p-6">Invalid customer ID.</div>;
  }

  const { data: customer, isLoading, isError } = useQuery({
    queryKey: ['customer', customerId],
    queryFn: () => getCustomer(customerId),
  });

  if (isLoading) return <div className="p-6">Loading...</div>;
  if (isError) return <div className="p-6">Customer not found.</div>;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <CustomerHeader customer={customer!} />
      <OverviewTab customer={customer!} />
    </div>
  );
}
```

**完成判定**：`ls src/frontend/pages/CustomerDetailPage.tsx` 文件存在 / `ruff check src/frontend/pages/` exit 0

---

### Step 6: 编写单元测试

在 `tests/unit/` 下新建 3 个测试文件（使用 Vitest + Testing Library）：

**tests/unit/test_customer_header.py**（如前端用 Python 测试框架；否则为 `.test.tsx`）：

```tsx
// tests/unit/test_customer_header.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CustomerHeader } from '../../src/frontend/components/customer/CustomerHeader';

vi.mock('../../src/frontend/components/customer/StatusBadge', () => ({
  StatusBadge: ({ status }: { status: string }) => <span data-testid="status-badge">{status}</span>,
}));
vi.mock('../../src/frontend/components/customer/LeadTierBadge', () => ({
  LeadTierBadge: ({ tier }: { tier: string }) => <span data-testid="tier-badge">{tier}</span>,
}));

const mockCustomer = {
  id: 1,
  name: 'Alice Smith',
  email: 'alice@example.com',
  phone: '+1-555-0100',
  status: 'Active',
  lead_tier: 'Hot',
  company_name: 'Acme Corp',
  company_address: '123 Main St',
  custom_fields: {},
};

describe('CustomerHeader', () => {
  it('renders customer name', () => {
    render(<CustomerHeader customer={mockCustomer} />);
    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
  });

  it('renders email', () => {
    render(<CustomerHeader customer={mockCustomer} />);
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
  });

  it('renders Edit and Delete buttons', () => {
    render(<CustomerHeader customer={mockCustomer} />);
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  it('renders StatusBadge and LeadTierBadge', () => {
    render(<CustomerHeader customer={mockCustomer} />);
    expect(screen.getByTestId('status-badge')).toHaveTextContent('Active');
    expect(screen.getByTestId('tier-badge')).toHaveTextContent('Hot');
  });
});
```

**tests/unit/test_overview_tab.test.tsx** 和 **tests/unit/test_customer_detail_page.test.tsx** 按相同模式编写，各覆盖：

- OverviewTab：contact card fields、company card fields、custom fields empty state、custom fields populated
- CustomerDetailPage：loading render、error render、invalid ID render、successful render with children

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_detail_page.py -v` → 4 passed（或 `vitest run tests/unit/test_customer_detail_page.test.tsx` → 4 passed）

---

## 6. 验收

- [ ] `ruff check src/frontend/api/customerApi.ts src/frontend/pages/CustomerDetailPage.tsx src/frontend/components/customer/CustomerHeader.tsx src/frontend/components/customer/OverviewTab.tsx` → 0 errors
- [ ] `vitest run tests/unit/test_customer_detail_page.test.tsx tests/unit/test_customer_header.test.tsx tests/unit/test_overview_tab.test.tsx` → ≥ 12 passed（含 4+4+4，或等效 Python pytest 计数）
- [ ] `ls src/frontend/pages/CustomerDetailPage.tsx src/frontend/components/customer/CustomerHeader.tsx src/frontend/components/customer/OverviewTab.tsx src/frontend/components/customer/StatusBadge.tsx src/frontend/components/customer/LeadTierBadge.tsx` → 5 个文件均存在
- [ ] `grep -c "customers/:id" src/frontend/App.tsx` 输出 ≥ 1
- [ ] `grep "getCustomer" src/frontend/api/customerApi.ts` 有输出
- [ ] `grep -E "(Edit|Delete)" src/frontend/components/customer/CustomerHeader.tsx` 有输出（按钮存在）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `GET /customers/:id` API 端点在 #557 中未完成或接口字段名不匹配 | 中 | 中 | 本 issue 前端代码按预期字段名（`name`, `email`, `phone`, `status`, `lead_tier`, `company_name`, `company_address`, `custom_fields`）编写；API 对齐后再 merge；可临时 mock 数据绕过 |
| TanStack Query 版本与现有前端不兼容（项目未引入） | 低 | 中 | 降级为原生 `useEffect + fetch` + local state loading/error，组件内处理，不引入新依赖 |
| 详情页测试框架（Vitest vs 现有框架）与项目不一致 | 低 | 低 | 先确认 `package.json` 或 `pytest.ini` 确定前端测试框架；如无现有框架，Vitest 为推荐选项并记录在 PR 中 |
| Edit/Delete 按钮占位代码与后续实现冲突（状态管理不同步） | 中 | 低 | 按钮 onClick 仅调用 `console.log` + 注释 `// TODO: implement`，明确不引入共享状态，后续独立 issue 重写整个按钮逻辑 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/pages/CustomerDetailPage.tsx \
  src/frontend/components/customer/CustomerHeader.tsx \
  src/frontend/components/customer/OverviewTab.tsx \
  src/frontend/components/customer/StatusBadge.tsx \
  src/frontend/components/customer/LeadTierBadge.tsx \
  src/frontend/api/customerApi.ts \
  src/frontend/App.tsx \
  tests/unit/test_customer_detail_page.py \
  tests/unit/test_customer_header.py \
  tests/unit/test_overview_tab.py
git commit -m "feat(frontend): customer detail page with header and overview tab"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): customer detail page header + overview tab (#558)" --body "Closes #558

## Summary
- New route /customers/:id with CustomerDetailPage
- CustomerHeader: name, avatar placeholder, StatusBadge, LeadTierBadge, Edit/Delete buttons
- OverviewTab: contact info card, company details card, custom fields
- getCustomer API hook consuming GET /customers/:id

## Test plan
- [ ] vitest run (or pytest) — ≥ 12 passed
- [ ] ruff check — 0 errors
- [ ] manual: /customers/1 renders header + overview tab"
```

---

## 9. 参考

- 同类参考实现：`src/frontend/pages/OpportunityDetailPage.tsx` — TBD - 待验证：是否存在商机详情页可作参考（搜索 `OpportunityDetail` 或 `opp/:id`）
- 父 issue / 关联：#53（Epic: CRM 前端完整化）、#557（客户列表页 + API 端点）
- 第三方文档：[React Router v6 useParams](https://reactrouter.com/en/main/hooks/use-params)、[TanStack Query useQuery](https://tanstack.com/query/latest/docs/framework/react/reference/useQuery)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
