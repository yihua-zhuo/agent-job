# Implementation Plan — Issue #118

## Goal
Extend the `useUsers` hook to accept `q` and `role` parameters and pass them to the `GET /api/v1/users` endpoint, and update the team page to use server-side filtering instead of client-side in-memory filtering — so search and role filter correctly paginate through all matching users.

## Affected Files
- `frontend/src/lib/api/queries.ts` — add `q` and `role` params to `useUsers`, update query key to include filter values
- `frontend/src/app/(app)/team/page.tsx` — pass `search` and `roleFilter` state to `useUsers` instead of filtering `items` client-side

## Implementation Steps

1. **Update `useUsers` in `frontend/src/lib/api/queries.ts`**
   - Change signature to `useUsers(page = 1, page_size = 20, q = "", role = "")`
   - Build `URLSearchParams` with `page`, `page_size`, and conditional `.set()` for `q` and `role` (same pattern as `useTickets` at line 128)
   - Update query key to `["users", page, q, role]` so filter changes trigger a refetch

2. **Update `frontend/src/app/(app)/team/page.tsx`**
   - Change `useUsers(page)` call to `useUsers(page, 20, search, roleFilter !== "all" ? roleFilter : "")`
   - Remove the client-side `filtered = items.filter(...)` block and replace usages of `filtered` with `items`
   - The pagination footer (`info.has_next`, total display) will now reflect server-filtered totals automatically — no other pagination changes needed

## Test Plan
- Unit tests in `tests/unit/`: no changes — `UserService.list_users` filtering is already covered by existing unit tests; the frontend hook change requires no backend test adjustments
- Integration tests in `tests/integration/`: add `test_list_users_filtered` in `tests/integration/test_users_integration.py` covering `q` and `role` params returning correct filtered totals

## Acceptance Criteria
- `GET /api/v1/users?q=alice` returns only users whose username/email/full_name contain "alice" with a `total` reflecting the filtered count
- `GET /api/v1/users?role=admin` returns only users with role "admin" with a correct `total`
- `GET /api/v1/users?q=alice&role=admin` combines both filters correctly
- Team page search input and role dropdown produce server-filtered, correctly paginated results
- Pagination Next/Prev buttons reflect filtered totals, not unfiltered server totals
