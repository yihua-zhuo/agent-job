# 前端 · 客户页搜索过滤与列排序

| 元数据 | 值 |
|---|---|
| Issue | #563 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 1-2 工作日 |
| 依赖 | [无] |
| 启用后赋能 | 无 — 纯前端体验改进，完成后其他模块不受影响 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `/customers` 页面（[`frontend/src/app/(app)/customers/page.tsx`](../../../frontend/src/app/%28app%29/customers/page.tsx)）已有一个手写的排序实现（`handleSort` + `SortIcon` 组件，L426-L433）和一个手写的 debounced 搜索（`handleChange` + `timerRef`，L310-L318）。两者在同一个文件内紧耦合，无法复用。项目已安装 `@tanstack/react-table`（`package.json` v5.100.8），但从未引入到 customers 页面中。Issue 要求在此基础上引入 TanStack Table 的排序状态机制，并补全一个结构化的 `useTableState` hook，使手写的 sort/search 逻辑升级为可复用方案。

### 1.2 做完后

- **用户视角**：在 `/customers` 页面输入搜索词，300ms 防抖后客户端过滤 name/email/phone 字段；点击列头在 asc/desc/null 三态间切换排序方向；无任何新的 API 调用。
- **开发者视角**：新增 `frontend/src/lib/hooks/useTableState.ts` 可复用 hook，接受 `data`、`searchableKeys`、`sortableKeys` props，返回 `{ filtered, sorting, globalFilter, setGlobalFilter, getTableProps, getRowModel }`，可在其他列表页（如 tickets、opportunities）直接复用。

### 1.3 不做什么（剔除）

- [ ] 不实现服务端搜索或排序（全部客户端处理）
- [ ] 不修改 `/customers` 页面以外的任何文件
- [ ] 不引入新的 API endpoint
- [ ] 不修改 `useCustomers` 查询逻辑或 pagination 行为
- [ ] 不使用 `useSearchCustomers`（那是服务端搜索，与本 issue 无关）

### 1.4 关键 KPI

- [`cd frontend && npm run build` → exit 0]
- [`cd frontend && npx tsc --noEmit` → exit 0（无 TypeScript 错误）]
- [`cd frontend && npm run lint` → exit 0（无 ESLint 错误）]
- 行为验证：搜索"Acme"后页面内可见行只含含"Acme"的记录；点击 "Name" 列头排序图标从▲变为▼，行顺序随之改变

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`frontend/src/app/(app)/customers/page.tsx`](../../../frontend/src/app/%28app%29/customers/page.tsx) L256-L433

现有 debounced search 逻辑（L310-L329）：

```tsx:frontend/src/app/(app)/customers/page.tsx
// L310-329 — 手写 debounce，无 hook 复用
const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
  const val = e.target.value;
  setKeyword(val);
  if (timerRef.current) clearTimeout(timerRef.current);
  timerRef.current = setTimeout(() => {
    setDebouncedKeyword(val);
    setPage(1);
  }, 300);
}
```

现有手写 sort 逻辑（L414-L433）：

```tsx:frontend/src/app/(app)/customers/page.tsx
// L414-433 — 手写 sort，无 TanStack Table
const sorted = [...items].sort((a, b) => {
  if (!sortKey) return 0;
  let av: string | number = a[sortKey];
  let bv: string | number = b[sortKey];
  if (sortKey === "created_at") { /* date parse */ }
  const cmp = av < bv ? -1 : av > bv ? 1 : 0;
  return sortDir === "asc" ? cmp : -cmp;
});
```

TanStack React Table 已在 `package.json` 中声明（`@tanstack/react-query` v5.100.8 的兄弟依赖），但未在 customers 页面中使用。

### 2.2 涉及文件清单

- 要改：
  - [`frontend/src/app/(app)/customers/page.tsx`](../../../frontend/src/app/%28app%29/customers/page.tsx) — 引入 TanStack Table，重构 search/sort 逻辑
- 要建：
  - `frontend/src/lib/hooks/useTableState.ts` — 搜索 + 排序状态 hook，供本板块及后续复用
  - `frontend/src/lib/hooks/useTableState.test.ts` — Vitest 单元测试

### 2.3 缺什么

- [ ] `useTableState.ts` hook：封装 TanStack Table 的 `useReactTable` + `getFilteredRowModel` + `getSortedRowModel`
- [ ] 全局搜索过滤器（globalFilter）替换现有手写 debounce + `sorted`
- [ ] 列头 `<th>` 替换为 TanStack Table 的 `header.getContext()` 渲染
- [ ] `<tbody>` 替换为 `row.getVisibleCells()` 渲染
- [ ] Vitest 测试覆盖 `useTableState` 的 search + sort 逻辑

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/src/lib/hooks/useTableState.ts` | 搜索 + 排序状态 hook，封装 TanStack Table `useReactTable`、`getFilteredRowModel`、`getSortedRowModel` |
| `frontend/src/lib/hooks/useTableState.test.ts` | Vitest 单元测试，覆盖 search 过滤、sort asc/desc、empty state |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`frontend/src/app/(app)/customers/page.tsx`](../../../frontend/src/app/%28app%29/customers/page.tsx) | 引入 `useTableState` hook，删除手写 `sorted`/`handleSort`/`handleChange`/`timerRef`，以 TanStack Table 的 `getRowModel().rows` 替换现有渲染逻辑 |

### 3.3 新增能力

- **Hook**：`useTableState(data, options)` — 返回 `{ table, filteredRows, globalFilter, setGlobalFilter }`
- **行为**：全局搜索过滤 name/email/phone（三列，case-insensitive substring）；点击列头切换 asc/desc，第三次点击清除排序

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 TanStack Table v5 (`@tanstack/react-table`) 不选手写 sort+filter**：TanStack Table 是业界标准，封装了 `getFilteredRowModel`、`getSortedRowModel`、column definitions、global filter 等完整能力，比手写更健壮；项目已安装，无需新增依赖。
- **选 `useTableState` hook 封装 TanStack Table 而非直接在 page 内调用 `useReactTable`**：hook 模式使 search/sort 逻辑可测试（Vitest）、可复用（tickets/opportunities 等其他列表页直接接入）；page 只负责渲染，与状态逻辑解耦。
- **选 globalFilter 而非 per-column filter**：客户列表只有 3 个可搜索列（name/email/phone），globalFilter 可以一个搜索框同时覆盖三列，用户体验更好。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `@tanstack/react-table` | `^5.100.8` | 与项目中已有 `@tanstack/react-query` v5 配套（同系列，同版本约定） |
| `@tanstack/react-query` | `^5.100.8` | 已安装，不变 |

### 4.3 兼容性约束

- 不修改 `useCustomers` 查询的 `queryKey`（否则缓存失效，导致额外 API 请求）
- `useTableState` hook 不做数据获取，只做客户端 filter/sort，不会触发新的 API 请求
- React 版本：项目使用 React 19.2.4，与 TanStack Table v5 兼容

### 4.4 已知坑

1. **TanStack Table v5 的 `getFilteredRowModel()` 需要单独导入** → 规避：在 `useTableState.ts` 顶部显式 `import { getFilteredRowModel, getSortedRowModel } from '@tanstack/react-table'`
2. **`globalFilter` 默认只对 string 类型做 case-sensitive 匹配** → 规避：在 `useTableState.ts` 中提供一个自定义 `filterFn`（`includesString`），实现 case-insensitive substring 匹配：`row.getValue(key)?.toString().toLowerCase().includes(filterValue.toLowerCase())`
3. **Vitest 中 TanStack Table 需要 mock 部分导出（`getFilteredRowModel` 等）** → 规避：在测试文件中通过 `vi.mock('@tanstack/react-table', ...)` mock 这些函数，或使用真实函数在 Vitest 环境运行（Vitest 支持 ESM）
4. **`page.tsx` 是 `'use client'` 但导入 hook 时要注意避免 circular dependency** → 规避：`useTableState.ts` 不导入任何来自 `customers/page.tsx` 的内容，纯函数无状态

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `useTableState.ts` hook

在 `frontend/src/lib/hooks/useTableState.ts` 中实现搜索 + 排序状态封装：

```typescript
// frontend/src/lib/hooks/useTableState.ts
'use client';

import { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  flexRender,
  ColumnDef,
  FilterFn,
} from '@tanstack/react-table';
import { rankingBrowser } from '@tanstack/sort-utils'; // or use default

// case-insensitive substring filter
const includesString: FilterFn<unknown> = (row, columnId, filterValue: string) => {
  const value = row.getValue<string>(columnId);
  return value?.toString().toLowerCase().includes(filterValue.toLowerCase()) ?? false;
};
includesString.autoRemove = (val: string) => !val;

export interface UseTableStateOptions<TData> {
  data: TData[];
  columns: ColumnDef<TData, unknown>[];
  searchableKeys?: string[];   // column ids for globalFilter scope
  globalFilterPlaceholder?: string;
}

export function useTableState<TData>({
  data,
  columns,
  searchableKeys = [],
}: UseTableStateOptions<TData>) {
  const [globalFilter, setGlobalFilter] = useState('');
  const [sorting, setSorting] = useState<import('@tanstack/react-table').SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    state: { globalFilter, sorting },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    globalFilterFn: includesString,
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getCoreRowModel: getCoreRowModel(),
    enableGlobalFilter: searchableKeys.length > 0,
  });

  return { table, globalFilter, setGlobalFilter, sorting };
}
```

在 `frontend/src/lib/hooks/index.ts` 中追加导出（新建文件如无则创建）。

**完成判定**：`cd frontend && npx tsc --noEmit src/lib/hooks/useTableState.ts` → exit 0

---

### Step 2: 重构 `customers/page.tsx` 使用 TanStack Table

在 `frontend/src/app/(app)/customers/page.tsx` 中：

a) 在文件顶部添加 import：

```typescript
import { useTableState } from '@/lib/hooks/useTableState';
import { ColumnDef } from '@tanstack/react-table';
```

b) 在文件顶部定义 `CustomerRowData`（已存在，L101-L109）作为 row type。

c) 定义 column definitions（放在 `CustomersPageInner` 函数外或内顶部）：

```typescript
const columns: ColumnDef<CustomerRowData, unknown>[] = [
  {
    id: 'select',
    header: ({ table }) => (
      <input type="checkbox" className="accent-primary h-4 w-4 cursor-pointer"
        onChange={table.getToggleAllRowsSelectedHandler()}
        checked={table.getIsAllRowsSelected()}
      />
    ),
    cell: ({ row }) => (
      <input type="checkbox" checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        className="accent-primary h-4 w-4 cursor-pointer"
      />
    ),
    size: 40,
  },
  {
    id: 'name',
    accessorKey: 'name',
    header: 'Name',
    cell: ({ getValue }) => (
      <span className="font-medium truncate block">{getValue() as string || '—'}</span>
    ),
    size: 160,
  },
  {
    id: 'email',
    accessorKey: 'email',
    header: 'Email',
    cell: ({ getValue }) => <CopyCell value={getValue() as string} type="email" />,
    size: 200,
  },
  // ... phone, status, company, created_at similarly
];
```

d) 替换 `customers/page.tsx` L310-L433 的手写逻辑：

在 `CustomersPageInner` 内，用 `useTableState` 替代现有 state：

```typescript
const { table, globalFilter, setGlobalFilter } = useTableState({
  data: items,
  columns,
  searchableKeys: ['name', 'email', 'phone'],
});

// 删除手写的：
// - timerRef, handleChange, debouncedKeyword, setDebouncedKeyword (L276, L310-318)
// - sortKey, sortDir, setSortKey, setSortDir, handleSort, sorted (L280, L414-433)
// - pushParams 中对 debouncedKeyword 的引用
```

e) 替换 `<tbody>` 渲染：

将现有 `{sorted.map((c) => ...)}` 替换为：

```tsx
<tbody>
  {table.getRowModel().rows.map((row) => (
    <CustomerRow
      key={row.original.id}
      c={row.original}
      onNavigate={navigateToCustomer}
      selected={selectedIds.has(row.original.id)}
      onToggle={toggleSelect}
      onDelete={openDelete}
      widths={widths}
      hiddenCols={hiddenCols}
      onRowClick={() => navigateToCustomer(row.original.id)}
    />
  ))}
</tbody>
```

f) 替换 `<th>` 中的排序逻辑：

将每个 `<th>` 的 `onClick={() => handleSort("name")}` 替换为 TanStack Table 的 header click：

```tsx
<th ...>
  <div
    className="flex items-center cursor-pointer"
    onClick={column.getToggleSortingHandler()}
  >
    {flexRender(column.columnDef.header, column.getContext())}
    {column.getIsSorted() === 'asc' && <ChevronUp className="h-3 w-3 ml-1 text-primary" />}
    {column.getIsSorted() === 'desc' && <ChevronDown className="h-3 w-3 ml-1 text-primary" />}
    {!column.getIsSorted() && <ChevronUp className="h-3 w-3 opacity-0 group-hover:opacity-40 ml-1" />}
  </div>
</th>
```

g) 替换搜索框的 `onChange`：

将搜索框 `onChange={handleChange}` 替换为：

```tsx
onChange={(e) => setGlobalFilter(e.target.value)}
```

移除 `page` 切换时的 `pushParams({ q: debouncedKeyword || null, ... })` 中的 `q` 参数——搜索现在完全在客户端，无需同步到 URL。

**完成判定**：`cd frontend && npm run build` → exit 0

---

### Step 3: 编写 Vitest 测试

在 `frontend/src/lib/hooks/useTableState.test.ts` 中：

```typescript
import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTableState } from './useTableState';

// Register filter fn so TanStack Table can find it
import '@tanstack/react-table';

const makeRows = (names: string[]) =>
  names.map((name, i) => ({ id: i + 1, name, email: `${name}@test.com`, phone: '', status: 'lead', company: '', created_at: '' }));

describe('useTableState', () => {
  it('filters rows by globalFilter (case-insensitive)', () => {
    const rows = makeRows(['Alice', 'Bob', 'Charlie']);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ['name'] })
    );
    act(() => { result.current.setGlobalFilter('ali'); });
    expect(result.current.table.getRowModel().rows.length).toBe(1);
    expect(result.current.table.getRowModel().rows[0].original.name).toBe('Alice');
  });

  it('returns all rows when globalFilter is empty', () => {
    const rows = makeRows(['Alice', 'Bob']);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ['name'] })
    );
    expect(result.current.table.getRowModel().rows.length).toBe(2);
  });

  it('sorts by column ascending then descending', () => {
    const rows = makeRows(['Charlie', 'Alice', 'Bob']);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ['name'] })
    );
    act(() => { result.current.table.getColumn('name')?.toggleSorting(); });
    expect(result.current.table.getRowModel().rows[0].original.name).toBe('Alice');
    act(() => { result.current.table.getColumn('name')?.toggleSorting(); });
    expect(result.current.table.getRowModel().rows[0].original.name).toBe('Charlie');
  });
});
```

**完成判定**：`cd frontend && npx vitest run src/lib/hooks/useTableState.test.ts` → 全 passed

---

## 6. 验收

- [ ] `cd frontend && npm run build` → exit 0
- [ ] `cd frontend && npx tsc --noEmit` → exit 0
- [ ] `cd frontend && npm run lint` → exit 0
- [ ] `cd frontend && npx vitest run src/lib/hooks/useTableState.test.ts` → 全 passed
- [ ] 行为检查：`frontend/src/app/(app)/customers/page.tsx` 中不再包含 `timerRef`、`debouncedKeyword`、`sorted`、`handleSort` 等手写 sort/search 变量

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| TanStack Table column definitions 覆盖不全导致某些列不渲染 | 低 | 中 | 在 `useTableState` 中添加 `enableSorting` / `enableColumnFilters` 显式控制；若列缺失，回退到 `flexRender` 的原始 header/cell 渲染 |
| globalFilter 重置时 `useCustomers` 缓存 key 变化导致多余 API 请求 | 低 | 中 | 本次实现后 `debouncedKeyword` 引用已移除，`globalFilter` 完全在客户端，不会改变 query key；降级：回退到 Step 2 完成前的状态（手写 sort/search 继续工作） |
| Vitest 测试中 TanStack Table 异步状态更新导致测试 flaky | 低 | 低 | 使用 `act()` 包裹状态更新；如仍 flaky，在测试文件顶部 `import '@tanstack/react-table'` 确保模块注册 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/lib/hooks/useTableState.ts \
       frontend/src/lib/hooks/useTableState.test.ts \
       frontend/src/lib/hooks/index.ts \
       frontend/src/app/\(app\)/customers/page.tsx
git commit -m "feat(frontend): client-side search & column sorting via TanStack Table on /customers"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): client-side search & column sorting on /customers" --body "Closes #563

## Summary
- Add useTableState hook wrapping TanStack Table getFilteredRowModel + getSortedRowModel
- Refactor /customers page to use useTableState (remove hand-rolled sort/search)
- GlobalFilter (name/email/phone, case-insensitive) + clickable column header sort controls
- No new API calls — all client-side

## Test plan
- [x] npm run build → exit 0
- [x] npx tsc --noEmit → exit 0
- [x] npx vitest run src/lib/hooks/useTableState.test.ts → all passed

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 9. 参考

- 同类参考实现：[`frontend/src/app/(app)/customers/page.tsx`](../../../frontend/src/app/%28app%29/customers/page.tsx) L256-L433（手写 sort/search 起点）
- TanStack Table 官方文档：[TanStack Table v8](https://tanstack.com/table/v8)
- TanStack Table React 示例：[useReactTable + getFilteredRowModel](https://tanstack.com/table/v8/docs/framework/react/examples/filters)
- 父 issue：#557（CRM 客户管理完整方案）
- 依赖 issue：#562（TanStack Table 基础依赖，如适用）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |

---

**修复说明**：5 处 broken link 的原因相同 — markdown link 目标中的 `(app)` 被解析为链接语法的括号，导致目标截断。统一将 `(app)` 编码为 `%28app%29`（RFC 3986 percent-encoding），所有其他内容保持不变。
