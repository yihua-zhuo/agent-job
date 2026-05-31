# 客户列表页（TanStack Table 初始版本）

| 元数据 | 值 |
|---|---|
| Issue | #562 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 父 issue #557 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

父 issue #557 已定义客户管理模块的产品路线图，要求前端以 TanStack Table 作为统一列表组件。当前 `/customers` 页面不存在，产品路线图中的客户列表功能无法推进。本板块是全量功能（搜索、筛选、排序、批量操作）的前置骨架。

### 1.2 做完后

- **用户视角**：导航至 `/customers` 后，页面渲染一张包含六列（name, industry, status, lead tier, last activity, value）的客户数据表，表头与数据行均来自后端 API，无分页控件、无搜索框、无操作按钮。
- **开发者视角**：前端获得 `src/pages/customers/index.tsx` 页面组件，TanStack Table 已作为依赖引入，可在此骨架上增量扩展排序、筛选、分页等功能，无需重写组件。

### 1.3 不做什么（剔除）

- [ ] 搜索框 / 模糊查询
- [ ] 列筛选或全局过滤
- [ ] 服务端或客户端排序
- [ ] 批量选择或批量操作按钮
- [ ] 分页控件（仅在 API 响应已含 total/page 信息时保留骨架占位）
- [ ] 行操作按钮（编辑/删除）

### 1.4 关键 KPI

- [KPI 1：路由 `/customers` 可访问，`src/pages/customers/index.tsx` 组件被加载]
- [KPI 2：`npm run build`（或等效前端构建）exit 0，无 TS 类型错误]
- [KPI 3：TanStack Table 依赖已记录在 `package.json` 中]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/pages/` 目录下是否已有 customers 子目录；前端 API 客户端文件路径（如 `src/api/customers.ts`）；现有 `GET /customers` 后端 endpoint 的响应 schema（含 tenant_id, page, page_size 参数）

主入口（若存在）：TBD - 待验证：`src/api/customers.ts` 中的 list 函数

### 2.2 涉及文件清单

- 要改：
  - `package.json` — 添加 TanStack Table 依赖
  - `src/router/index.ts`（或 `src/App.tsx`）— 新增 `/customers` 路由注册
- 要建：
  - `src/pages/customers/index.tsx` — 客户列表页面组件（TBD — 待确认现有 pages 目录结构）
  - `src/pages/customers/useCustomers.ts` — 数据获取 hook（TBD — 待确认现有 hook 组织方式）
  - `src/__tests__/customers.test.tsx` — 组件渲染测试（TBD — 待确认现有测试框架）

### 2.3 缺什么

- [ ] 前端 `GET /customers` 页面组件（全新）
- [ ] TanStack Table 依赖（需添加）
- [ ] `/customers` 路由注册
- [ ] 客户列表 API 数据类型定义（若有 shared types 包，TBD）
- [ ] 六列表格列头定义（name, industry, status, lead tier, last activity, value）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/pages/customers/index.tsx` | 客户列表页面组件，渲染 TanStack Table 并从 API 拉取数据 |
| `src/pages/customers/useCustomers.ts` | 数据获取 hook，调用现有客户列表 API 并返回 rows + total |
| `src/__tests__/customers.test.tsx` | 组件渲染测试，验证表头六列存在且 API 数据正确显示（TBD — 待确认测试目录结构） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `package.json` | 添加 TanStack Table v8 依赖 |
| `src/router/index.tsx`（或 `src/App.tsx`） | 新增 `Route path="/customers" element={<CustomersPage />}` |

### 3.3 新增能力

- **React 页面组件**：`CustomersPage`（`src/pages/customers/index.tsx`）
- **数据 hook**：`useCustomers()` hook，接收 `{ tenantId, page, pageSize }` 参数，返回 `rows` 数组
- **TanStack Table 实例**：包含六列（name, industry, status, lead tier, last activity, value）的 `<table>` 结构
- **路由注册**：`/customers` → `CustomersPage`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 TanStack Table v8 不选原生 HTML `<table>` + CSS**：[TanStack Table v8 提供开箱即用的列定义、类型推断和虚拟化扩展基础，避免自行维护列配置逻辑]
- **选在 `src/pages/customers/` 下新建组件 不复用 `src/components/` 下现有 Table 组件**：[页面级组件逻辑（API 调用、tenant_id 注入）与通用 Table 组件职责分离，符合现有前端目录结构（TBD — 待验证该目录结构是否存在）]
- **选 React hook 封装 API 调用 不在组件内直接调用 fetch**：[可独立测试，组件只负责渲染，便于后续扩展（加载状态、错误处理）]

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `@tanstack/react-table` | `^8.x` | 当前稳定版，API 较成熟 |
| `react` | 与项目现有版本一致 | 无需升级 |

### 4.3 兼容性约束

- `GET /customers` 调用时必须在请求头或 query 中携带 `tenant_id`（后端多租户要求）
- API 客户端函数须使用项目中现有的 HTTP 请求方式（TBD — 待确认是 `axios` / `fetch` / `ky` 等）
- 组件使用 TypeScript，表格列定义须与 API 响应类型对应（TBD — 若无 shared types 包，需自行定义 `Customer` 接口）

### 4.4 已知坑

1. **TanStack Table v8 列定义中 `accessorKey` 大小写敏感** → 规避：确保 accessorKey 与 API 响应字段名严格一致（含下划线/驼峰），若不一致使用 `accessorFn` 映射
2. **前端构建时缺少 TanStack Table 类型定义** → 规避：确认 `@tanstack/react-table` 安装时带类型；若项目使用 TypeScript `skipLibCheck: false`，可能需要 `@types/` 补充类型（TBD — 确认项目 TS 配置）
3. **CRM 后端多租户：API 请求不带 tenant_id 返回 403** → 规避：useCustomers hook 在调用 API 前必须注入当前用户的 tenant_id（TBD — 待确认现有前端如何获取 tenant_id）

---

## 5. 实现步骤（按顺序）

### Step 1: 添加 TanStack Table 依赖

确认前端包管理器（npm / yarn / pnpm），在 `package.json` 中添加 `@tanstack/react-table`。

操作：

```bash
# 方案 A（npm）
npm install @tanstack/react-table

# 方案 B（yarn）
yarn add @tanstack/react-table

# 方案 C（pnpm）
pnpm add @tanstack/react-table
```

```json
// package.json 新增（示例）
{
  "dependencies": {
    "@tanstack/react-table": "^8.21.0"
  }
}
```

**完成判定**：`cat package.json | grep "@tanstack/react-table"` 输出含版本号；`node_modules/@tanstack/react-table` 目录存在

---

### Step 2: 定义客户数据类型

在 `src/pages/customers/types.ts`（或 `src/types/customer.ts`，TBD — 待确认现有类型目录）定义 `Customer` 接口。

操作：

```typescript
// src/pages/customers/types.ts
export interface Customer {
  id: number;
  name: string;
  industry: string;
  status: string;
  lead_tier: string;       // 或 leadTier，视 API 实际字段名而定
  last_activity: string;  // ISO date string
  value: number;          // 或 string（货币格式化）
}

export interface CustomersApiResponse {
  success: boolean;
  data: {
    items: Customer[];
    total: number;
    page: number;
    page_size: number;
  };
}
```

**完成判定**：文件 `src/pages/customers/types.ts` 存在；无 TypeScript 类型错误

---

### Step 3: 创建 useCustomers hook

在 `src/pages/customers/useCustomers.ts` 中封装 API 调用。

操作：

```typescript
// src/pages/customers/useCustomers.ts
import { useState, useEffect } from 'react';
import type { Customer, CustomersApiResponse } from './types';

interface UseCustomersOptions {
  tenantId: number;
  page?: number;
  pageSize?: number;
}

interface UseCustomersResult {
  rows: Customer[];
  total: number;
  loading: boolean;
  error: Error | null;
}

export function useCustomers({
  tenantId,
  page = 1,
  pageSize = 20,
}: UseCustomersOptions): UseCustomersResult {
  const [rows, setRows] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // TBD — 使用现有 API 客户端函数（existingApiClient.getCustomers 或等效）
    const controller = new AbortController();
    setLoading(true);
    fetch(`/customers?tenant_id=${tenantId}&page=${page}&page_size=${pageSize}`, {
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<CustomersApiResponse>;
      })
      .then((data) => {
        setRows(data.data.items);
        setTotal(data.data.total);
        setError(null);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [tenantId, page, pageSize]);

  return { rows, total, loading, error };
}
```

**完成判定**：文件 `src/pages/customers/useCustomers.ts` 存在；无 TS 类型错误

---

### Step 4: 创建客户列表页面组件

在 `src/pages/customers/index.tsx` 创建 TanStack Table 组件，渲染六列表格。

操作：

```tsx
// src/pages/customers/index.tsx
import React from 'react';
import {
  createColumnHelper,
  useReactTable,
  getCoreRowModel,
  flexRender,
} from '@tanstack/react-table';
import type { Customer } from './types';
import { useCustomers } from './useCustomers';

// TBD — 确认获取 tenantId 的方式（如从 auth context / session）
function useTenantId(): number {
  // 示例：return useAuth().tenantId;
  return 1; // placeholder，直到确认 auth context
}

const columnHelper = createColumnHelper<Customer>();

const columns = [
  columnHelper.accessor('name', {
    header: 'Name',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('industry', {
    header: 'Industry',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('status', {
    header: 'Status',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('lead_tier', {
    header: 'Lead Tier',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('last_activity', {
    header: 'Last Activity',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('value', {
    header: 'Value',
    cell: (info) => info.getValue(),
  }),
];

export default function CustomersPage() {
  const tenantId = useTenantId();
  const { rows, loading, error } = useCustomers({ tenantId, page: 1, pageSize: 20 });

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <h1>Customers</h1>
      <table>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**完成判定**：文件 `src/pages/customers/index.tsx` 存在；无 TS/JSX 错误；TanStack Table `createColumnHelper` 和 `useReactTable` 调用正确

---

### Step 5: 注册 `/customers` 路由

在 `src/router/index.tsx`（或 `src/App.tsx`，TBD — 待确认路由配置位置）添加路由。

操作：

```tsx
// 在路由配置文件中新增（示例）
import CustomersPage from '../pages/customers';

// 在路由数组中添加：
{ path: '/customers', element: <CustomersPage /> }
```

**完成判定**：路由配置文件中存在 `/customers` 路径指向 `CustomersPage`；前端构建无路由未找到警告

---

### Step 6: 编写组件渲染测试

在 `src/__tests__/customers.test.tsx`（或 `src/pages/customers/__tests__/index.test.tsx`，TBD — 待确认测试目录结构）添加测试。

操作：

```tsx
// src/__tests__/customers.test.tsx
import { render, screen } from '@testing-library/react';
import CustomersPage from '../pages/customers';

// TBD — 确认现有测试工具（jest / vitest；@testing-library/react / @testing-library/preact）
// TBD — 确认 mock 方式（msw / jest.fn()）

describe('CustomersPage', () => {
  it('renders six column headers', async () => {
    // Arrange: mock fetch / API client to return known rows
    // Act
    render(<CustomersPage />);
    // Assert
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Industry')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Lead Tier')).toBeInTheDocument();
    expect(screen.getByText('Last Activity')).toBeInTheDocument();
    expect(screen.getByText('Value')).toBeInTheDocument();
  });

  it('displays rows from API', async () => {
    // Arrange: mock API returning 2 customers
    // Act
    render(<CustomersPage />);
    // Assert
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
  });
});
```

**完成判定**：测试文件存在；`npm test`（或等效）exit 0

---

## 6. 验收

- [ ] `npm install @tanstack/react-table` → `package.json` 中出现 `@tanstack/react-table` 依赖（版本 `^8.x`）
- [ ] `npx tsc --noEmit`（或项目等效类型检查命令）→ 0 errors
- [ ] `npm run build`（或项目等效构建命令）→ exit 0
- [ ] `npm test`（或项目等效测试命令）→ 相关测试 passed
- [ ] 路由 `/customers` 导航后，页面 `<table>` 存在六列 `<th>` 且 `<tbody>` 包含 API 返回的 `<tr>` 行（可通过手动浏览器访问或 Playwright 验证，TBD — 待确认 e2e 测试是否已存在）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| TanStack Table v8 与现有 React 版本不兼容 | 低 | 中 | 降级至 `@tanstack/react-table@7`，API 差异仅在 `columnHelper.accessor` 签名；`^7.x` 同样满足骨架需求 |
| 后端 `GET /customers` 响应字段名与前端 `Customer` 接口不匹配（如 `leadTier` vs `lead_tier`） | 中 | 低 | Step 2 中使用 `accessorFn: (row) => row['lead-tier-field']` 映射，不改 API；若字段彻底缺失，在 §2.3 更新后补充类型定义 |
| 前端路由系统与预期结构不符（文件位置/命名约定） | 中 | 中 | 参照现有其他页面组件（如 `src/pages/tickets/index.tsx`）的位置和命名，TBD — 待确认该文件是否存在 |
| API 缺少 `tenant_id` 注入机制导致 403 | 高 | 高 | Step 3 中 `useTenantId` hook 在 API 调用前必须注入正确的 `tenantId`；若现有 auth context 不存在，先用硬编码占位值，后续 #557 统一接入 auth |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/pages/customers/ package.json src/router/  # TBD — 确认实际变更路径
git commit -m "feat(frontend): scaffold /customers page with TanStack Table"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): scaffold /customers page with TanStack Table" --body "Closes #562"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/pages/tickets/index.tsx`（或等效现有列表页面）— 参照其 API hook 封装方式和 TanStack Table 初始化方式
- 第三方文档：[TanStack Table v8 快速上手](https://tanstack.com/table/v8/docs/framework/react/examples/basic)
- 父 issue / 关联：#557

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
