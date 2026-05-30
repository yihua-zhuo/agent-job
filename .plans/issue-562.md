Now I have everything I need. Let me write the plan.

# Implementation Plan — Issue #562

## Goal

Scaffold a new `/customers` page under `frontend/src/app/(app)/customers/` that uses TanStack Table v8 to render customer rows fetched from the existing `GET /api/v1/customers` endpoint (tenant_id, page, page_size params). The page displays six columns — name, industry, status, lead tier, last activity, value — in a basic table shell. No search, filtering, sorting, or bulk actions. The existing rich page at `frontend/src/app/(app)/customers/page.tsx` is untouched; the scaffolded page lives at `frontend/src/app/(app)/customers/table/page.tsx` (or `index.tsx` inside a new subdirectory) to avoid conflicting with the existing route. The issue title and body imply creating a new route, so a sub-route off `/customers` is the right approach.

## Affected Files

- `frontend/package.json` — add `@tanstack/react-table` dependency
- `frontend/src/app/(app)/customers/table/page.tsx` — **new** scaffolded page with TanStack Table
- `frontend/src/lib/api/queries.ts` — no changes needed; `useCustomers(page, pageSize)` already wires to the correct endpoint

## Implementation Steps

1. **Add TanStack Table dependency**
   - Run `cd frontend && npm install @tanstack/react-table` (or add `"@tanstack/react-table": "^8.x.x"` to `dependencies` in `frontend/package.json` and run `npm install`).

2. **Create the scaffolded page at `frontend/src/app/(app)/customers/table/page.tsx`**
   - `"use client"` directive, import `useCustomers` from `@/lib/api/queries`.
   - Import `useQuery` types and `ColumnDef` from `@tanstack/react-table`.
   - Define a `CustomerRow` TypeScript interface with fields: `id`, `name`, `industry` (from `company` field), `status`, `lead_tier` (from `tags[0]` or default "unknown"), `last_activity` (from `created_at`), `value` (derived or from a placeholder field).
   - Build a `columns: ColumnDef<CustomerRow>[]` array with six static column definitions: `name`, `industry`, `status`, `lead_tier`, `last_activity`, `value`. Use plain text cells — no custom renderers beyond a status badge helper.
   - In the component, call `useCustomers(1, 20)` to fetch page 1 with 20 rows per page.
   - Use `useReactTable` to initialize the table with `getCoreRowModel`, empty `getSortedRowModel`, empty `getFilteredRowModel`, and `getPaginationRowModel` (or omit pagination for now since the issue says "no search, filtering, sorting").
   - Render a `<table>` shell using `<thead>` with column headers from `header.getContext()` and `<tbody>` with rows from `row.getVisibleCells()`, mapping each cell to a `<td>` with `cell.getValue()`.
   - Add a simple loading skeleton (text "Loading...") when `isLoading` is true and an empty state message when `data?.data?.items` is empty.
   - The page wraps in the existing `(app)` layout automatically — no router file needed.

3. **Wire tenant_id** — `useCustomers` reads the bearer token from the Zustand auth store (`useAuthStore`), so tenant isolation is already handled server-side via the authenticated session.

## Test Plan

- **Unit tests in `tests/unit/`**: Not applicable — this is a frontend component with no backend logic; unit tests for the service layer already exist for `CustomerService`. No new unit test files needed at this stage.
- **Integration tests in `tests/integration/`**: Not applicable — the backend `/api/v1/customers` endpoint is already covered by existing integration tests. No new integration test files needed at this stage.

Manual verification: navigate to `/customers/table` (or whichever sub-path is chosen) in the dev server and confirm the table renders with column headers and data rows fetched from the API.

## Acceptance Criteria

- `npm install @tanstack/react-table` succeeds and the package appears in `frontend/package.json`.
- `frontend/src/app/(app)/customers/table/page.tsx` exists and exports a default React component.
- The component calls `useCustomers(1, 20)` and renders a `<table>` with six `<th>` cells: Name, Industry, Status, Lead Tier, Last Activity, Value.
- The `<tbody>` renders one `<tr>` per item returned in `data.data.items` from the API response.
- A loading state ("Loading..." or equivalent) is displayed while the query is pending.
- Navigating to the route in the dev server shows the table with API data — no search, filter, sort, or bulk-action UI elements are present.
- The app builds without TypeScript errors (`npm run build` in `/frontend` succeeds).
