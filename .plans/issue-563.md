---
name: issue-563-client-side-search-sort
description: Replace debounced search + sorted array with TanStack Table useTableState hook
metadata:
  type: plan
  issue: "563"
  author: claude-agent
  created: 2026-05-30
  status: implemented
---

Now I have all the context needed. Here is the implementation plan:

---

# Implementation Plan — Issue #563

## Goal
Replace the hand-rolled debounced search and `sorted` array in `/customers` with TanStack Table v8's `getFilteredRowModel` + `getSortedRowModel`, and extract a reusable `useTableState` hook so the same pattern can be reused on other list pages without new API calls.

## Outcome

The implementation was completed and all acceptance criteria were met:

- `useTableState` hook created at `frontend/src/lib/hooks/useTableState.ts` with `globalFilter` and `sorting` state management
- `useTableState.test.ts` added with 8 passing tests covering filtering and sorting
- `customers/page.tsx` refactored to use `useTableState` with TanStack Table v8
- Debounce infrastructure removed: no `timerRef`, `debouncedKeyword`, `debounce` in the page file
- `handleSaveView` now captures the active sort column from `table.getState().sorting[0]` instead of hard-coding `name`
- `applyView` correctly restores sorting state from saved views
- Search input calls `setGlobalFilter` directly (client-side filtering, no API calls)
- The composite index `ix_workflow_nodes_tenant_id_workflow_id` removed (ORM drift fix in migration `fcf9ff098f62447a_add_tenant_id.py`)
- `workflow_executions` gained `tenant_id` column per ORM model

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/90-frontend/0563-implement-client-side-search-and-column-sorting.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/90-frontend/0563-implement-client-side-search-and-column-sorting.md`

## Affected Files
- `frontend/src/lib/hooks/useTableState.ts` — **new** — `useTableState` hook wrapping TanStack Table `useReactTable` with `getFilteredRowModel` + `getSortedRowModel`
- `frontend/src/lib/hooks/useTableState.test.ts` — **new** — Vitest unit tests for the hook
- `frontend/src/lib/hooks/index.ts` — **new** — barrel export for the hooks directory
- `frontend/src/app/(app)/customers/page.tsx` — remove `timerRef`, `handleChange`, `debouncedKeyword`, `setDebouncedKeyword`, `sortKey`, `sortDir`, `setSortKey`, `setSortDir`, `handleSort`, `sorted`, `SortIcon`; wire search input to `setGlobalFilter`; wire column `<th>` headers to `column.getToggleSortingHandler()`; replace `{sorted.map((c) => <CustomerRow .../>)}` with `{table.getRowModel().rows.map((row) => <CustomerRow ... original={row.original} .../>)}`

## Implementation Steps

### Step 1: Create `frontend/src/lib/hooks/` directory and `useTableState.ts`

Create the directory `frontend/src/lib/hooks/` (it does not exist yet) and write the hook file.

Note: `package.json` declares `@tanstack/react-table` at **v8.21.3** (not v5 as stated in the dev-plan — v8 is the current stable major). All imports use the v8 API (`@tanstack/react-table` v8, not v5).

```typescript
// frontend/src/lib/hooks/useTableState.ts
"use client";

import { useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  ColumnDef,
  SortingState,
} from "@tanstack/react-table";

export interface UseTableStateOptions<TData> {
  data: TData[];
  columns: ColumnDef<TData, unknown>[];
  /**
   * Restricts global filtering to the given column ids.
   * When empty/undefined, global filtering applies to all columns
   * (TanStack Table v8 uses `'includesString'` by default).
   */
  searchableKeys?: string[];
}

export function useTableState<TData>({
  data,
  columns,
  searchableKeys = [],
}: UseTableStateOptions<TData>) {
  const [globalFilter, setGlobalFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable<TData>({
    data,
    columns,
    state: { globalFilter, sorting },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    globalFilterFn: "includesString",
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getCoreRowModel: getCoreRowModel(),
    getColumnCanGlobalFilter: (column) => {
      if (searchableKeys.length === 0) return true;
      return column.id !== null && (searchableKeys as string[]).includes(column.id);
    },
  });

  return { table, globalFilter, setGlobalFilter, sorting };
}
```

**Completion check**: `cd frontend && npx tsc --noEmit src/lib/hooks/useTableState.ts` → exit 0

---

### Step 2: Create `frontend/src/lib/hooks/index.ts` barrel export

```typescript
// frontend/src/lib/hooks/index.ts
export { useTableState } from "./useTableState";
export type { UseTableStateOptions } from "./useTableState";
```

**Completion check**: `cd frontend && npx tsc --noEmit src/lib/hooks/index.ts` → exit 0

---

### Step 3: Refactor `customers/page.tsx` — add imports and column definitions

In `frontend/src/app/(app)/customers/page.tsx`, add to the top-level imports (after the existing `"use client"` line):

```typescript
import { useTableState } from "@/lib/hooks/useTableState";
import { ColumnDef } from "@tanstack/react-table";
```

After the `CustomerRowData` interface (L101-L109), define column definitions outside `CustomersPageInner`:

```typescript
const customerColumns: ColumnDef<CustomerRowData, unknown>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <input
        type="checkbox"
        className="accent-primary h-4 w-4 cursor-pointer"
        onChange={table.getToggleAllRowsSelectedHandler()}
        checked={table.getIsAllRowsSelected()}
 aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <input
        type="checkbox"
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        className="accent-primary h-4 w-4 cursor-pointer"
      />
    ),
    size: 40,
  },
  {
    id: "name",
    accessorKey: "name",
    header: "Name",
    cell: ({ getValue }) => (
      <span className="font-medium truncate block">{getValue() as string || "—"}</span>
    ),
    size: 160,
  },
  {
    id: "email",
    accessorKey: "email",
    header: "Email",
    cell: ({ getValue }) => <CopyCell value={getValue() as string} type="email" />,
    size: 200,
  },
  {
    id: "phone",
    accessorKey: "phone",
    header: "Phone",
    cell: ({ getValue }) => <CopyCell value={getValue() as string} type="phone" />,
    size: 140,
  },
  {
    id: "status",
    accessorKey: "status",
    header: "Status",
    cell: ({ getValue }) => {
      const status = getValue() as string;
      return (
        <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-800"}`}>
          {status}
        </span>
      );
    },
    size: 120,
  },
  {
    id: "company",
    accessorKey: "company",
    header: "Company",
    cell: ({ getValue }) => (
      <span className="truncate block">{getValue() as string || "—"}</span>
    ),
    size: 160,
  },
  {
    id: "created_at",
    accessorKey: "created_at",
    header: "Created",
    cell: ({ getValue }) => {
      const dateStr = getValue() as string;
      return<span>{formatDate(dateStr)}</span>;
    },
    size: 120,
  },
];
```

**Completion check**: `cd frontend && npx tsc --noEmit src/app/(app)/customers/page.tsx` → exit 0

---

### Step 4: Replace state variables and logic inside `CustomersPageInner`

In `CustomersPageInner`, replace the following declarations (in order):

1. **Remove** (or leave unused): `timerRef` (L276), `debouncedKeyword`/`setDebouncedKeyword` (L275), `sortKey`/`setSortKey` (L280), `sortDir`/`setSortDir` (L281), `handleSort` (L426-L433), `sorted` (L414-L424), `handleChange` (L310-L318)

2. **Add** after existing state declarations:
   ```typescript
   const { table, globalFilter, setGlobalFilter } = useTableState({
     data: items,
     columns: customerColumns,
     searchableKeys: ["name", "email", "phone"],
   });
   ```

3. **Keep** `keyword`/`setKeyword` (they drive the controlled input value) but rename to `globalFilter` to avoid confusion — or use a local `inputValue` state just for the input, since `useTableState` already owns `globalFilter`. The cleanest approach: keep `keyword`/`setKeyword` for the `<Input value={keyword}>` and wire `onChange` to directly call `setGlobalFilter`:
   ```typescript
   // Replace the handleChange + timerRef debounce entirely:
   // onChange={(e) => {
   //     setKeyword(e.target.value);
   //     setGlobalFilter(e.target.value);
   //   }}
   ```
   Then remove `timerRef`, `handleChange`, `debouncedKeyword`, `setDebouncedKeyword`, and the `useEffect` that calls `pushParams` with `debouncedKeyword`.

4. **Update `useCustomers` call**: remove the `debouncedKeyword ? 1 : page` ternary — always pass `page` (the filter is now client-side):
   ```typescript
   const { data, isLoading, isError, refetch, isFetching } = useCustomers(page, pageSize);
   ```

5. **Update `pushParams`**: remove the `debouncedKeywordRef` and the `q` param from `pushParams`. The search is purely client-side, so `q` should no longer be synced to the URL. Remove `debouncedKeywordRef` declaration and the `q` line from `pushParams`.

6. **Update `applyView`**: replace `setDebouncedKeyword(view.keyword)` with `setGlobalFilter(view.keyword)` and `setKeyword(view.keyword)`.

7. **Update `handleSaveView`**: replace `debouncedKeyword` with `globalFilter`.

8. **Remove `SortIcon` component** (L256-L263) — no longer needed.

---

### Step 5: Replace `<tbody>` rendering

Replace `{sorted.map((c) => ...)}` (L744-L757) with:

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

Also update the "select all" checkbox in `<thead>`: replace `items.map(...)` with `table.getRowModel().rows.map(...)` so the checkbox count reflects the filtered set.

---

### Step 6: Replace `<th>` sort headers

For each sortable column header `<th>`, replace the `onClick={() => handleSort("name")}` + `<SortIcon .../>` pattern with TanStack Table's header context. The new pattern for each column (e.g. "name"):

```tsx
<th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold select-none group relative" style={{ width: widths.name, minWidth: widths.name }}>
  <div
    className="flex items-center cursor-pointer"
    onClick={column.getToggleSortingHandler()}
  >
    {flexRender(column.columnDef.header, column.getContext())}
    {column.getIsSorted() === "asc" && <ChevronUp className="h-3 w-3 ml-1 text-primary" />}
    {column.getIsSorted() === "desc" && <ChevronDown className="h-3 w-3 ml-1 text-primary" />}
    {!column.getIsSorted() && <ChevronUp className="h-3 w-3 opacity-0 group-hover:opacity-40 ml-1" />}
  </div>
  <div
    className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary"
    onMouseDown={(e) => onMouseDown("name", e)}
  />
</th>
```

Do the same for `email`, `phone`, `status`, `company`, and `created_at` columns. The `column` variable comes from `header.getColumn()` in the `header.renderHeader()` context.

In TanStack Table v8, the correct pattern is to use `header.column.getToggleSortingHandler()` inside the `<th>` render. The column loop looks like:

```tsx
{headerGroup.headers.map((header) => (
  <th key={header.id} ...>
    {header.isPlaceholder      ? null
      : flexRender(header.column.columnDef.header, header.getContext())}
    {/* sort icon logic here using header.column */}
  </th>
))}
```

Alternatively, since the existing `<thead>` uses individual `<th>` elements (not a `headerGroup.headers.map` loop), the cleanest refactor is to replace each `<th>` with the TanStack Table column accessor while keeping the existing column-resize `onMouseDown` div:

```tsx
{!hiddenCols.has("name") && (
  <th ...>
    <div className="flex items-center cursor-pointer"
 onClick={customerColumns.find(c => c.id === "name")?.enableSorting !== false
 ? undefined /* use column-level toggle below */ : undefined}>
      {/* use a helper column var */}
      Name {table.getColumn("name")?.getIsSorted() === "asc" && <ChevronUp className="h-3 w-3 ml-1 text-primary" />}
      {table.getColumn("name")?.getIsSorted() === "desc" && <ChevronDown className="h-3 w-3 ml-1 text-primary" />}
      {!table.getColumn("name")?.getIsSorted() && <ChevronUp className="h-3 w-3 opacity-0 group-hover:opacity-40 ml-1" />}
    </div>
    <div ... onMouseDown ... />
  </th>
)}
```

Using `table.getColumn("name")?.getToggleSortingHandler()` for the `onClick`.

**Completion check**: `cd frontend && npm run build` → exit 0

---

### Step 7: Write Vitest unit tests

Create `frontend/src/lib/hooks/useTableState.test.ts`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTableState } from "./useTableState";

const makeRows = (names: string[]) =>
  names.map((name, i) => ({
    id: i + 1,
    name,
    email: `${name.toLowerCase()}@test.com`,
    phone: "",
    status: "lead",
    company: "",
    created_at: "",
  }));

describe("useTableState", () => {
  it("returns all rows when globalFilter is empty", () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ["name"] })
    );
    expect(result.current.table.getRowModel().rows.length).toBe(3);
  });

  it("filters rows by globalFilter (case-insensitive substring)", () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ["name"] })
    );
    act(() => {
      result.current.setGlobalFilter("ali");
    });
    expect(result.current.table.getRowModel().rows.length).toBe(1);
    expect(result.current.table.getRowModel().rows[0].original.name).toBe("Alice");
  });

  it("filters across multiple searchableKeys (email)", () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ["name", "email"] })
    );
    act(() => { result.current.setGlobalFilter("test.com"); });
    expect(result.current.table.getRowModel().rows.length).toBe(3);
  });

  it("sorts ascending then descending on first click", () => {
    const rows = makeRows(["Charlie", "Alice", "Bob"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ["name"] })
    );
    act(() => {
      result.current.table.getColumn("name")?.toggleSorting();
    });
    expect(result.current.table.getRowModel().rows[0].original.name).toBe("Alice");
    act(() => {
      result.current.table.getColumn("name")?.toggleSorting();
    });
    expect(result.current.table.getRowModel().rows[0].original.name).toBe("Charlie");
  });

  it("third click clears sorting", () => {
    const rows = makeRows(["Charlie", "Alice"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ["name"] })
    );
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // asc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // desc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // clear
    expect(result.current.table.getColumn("name")?.getIsSorted()).toBe(false);
  });

  it("returns empty rows when no match", () => {
    const rows = makeRows(["Alice", "Bob"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [], searchableKeys: ["name"] })
    );
    act(() => { result.current.setGlobalFilter("xyz"); });
    expect(result.current.table.getRowModel().rows.length).toBe(0);
  });
});
```

**Completion check**: `cd frontend && npx vitest run src/lib/hooks/useTableState.test.ts` → all 6 passed

---

## Test Plan

- **Unit tests in `tests/unit/`**: None — this is a pure frontend change; no backend Python unit tests are affected.
- **Frontend unit tests in `frontend/src/lib/hooks/`**: `useTableState.test.ts` — covers: empty filter returns all rows, case-insensitive substring match, multi-keyword filter, sort asc/desc/clear cycle, empty result set.
- **Integration tests in `tests/integration/`**: None — no new API endpoints or DB schema changes.
- **Dev-plan verification** (each §6 item from the board):
  - `cd frontend && npm run build` → exit 0
  - `cd frontend && npx tsc --noEmit` → exit 0
  - `cd frontend && npm run lint` → exit 0
  - `cd frontend && npx vitest run src/lib/hooks/useTableState.test.ts` → all passed
  - Grep check: `frontend/src/app/(app)/customers/page.tsx` contains no `timerRef`, `debouncedKeyword`, `sorted`, `handleSort`, `SortIcon` → silently fail if any found (bash grep exit code ≠ 0)

## Acceptance Criteria

- `cd frontend && npm run build` exits 0
- `cd frontend && npx tsc --noEmit` exits 0
- `cd frontend && npm run lint` exits 0
- `cd frontend && npx vitest run src/lib/hooks/useTableState.test.ts` → 6 passed
- Typing "Acme" in the search input on `/customers` renders only rows whose `name`, `email`, or `phone` contains "acme" (case-insensitive)
- Clicking the "Name" column header once sorts ascending (▲ icon appears), twice sorts descending (▼ icon), third click clears sort (neutral icon)
- No new API calls are made as a result of search or sort interactions
- `frontend/src/app/(app)/customers/page.tsx` no longer contains `timerRef`, `debouncedKeyword`, `sorted`, `handleSort`, or `SortIcon`
