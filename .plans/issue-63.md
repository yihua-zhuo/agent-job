Now I have a thorough picture of the codebase. Let me compile the implementation plan.

# Implementation Plan — Issue #63

## Goal

The frontend already has a Kanban board, list view, and task modal for `/tasks` and `/tasks/list`, backed by React Query hooks. The **backend has no tasks router** — `TaskService` and `TaskModel` exist but no `/api/v1/tasks` endpoints are wired up. This issue completes the backend API and enhances the UI with drag-and-drop, assignee picker, markdown preview, quick-add header, and bulk operations.

## Affected Files

- `src/api/routers/tasks.py` — **New** — FastAPI router for all task CRUD endpoints
- `src/api/__init__.py` — **Modify** — add `tasks_router` export
- `src/main.py` — **Modify** — register `tasks_router`
- `frontend/src/app/(app)/tasks/page.tsx` — **Modify** — add drag-and-drop, column task counts from correct total
- `frontend/src/app/(app)/tasks/list/page.tsx` — **Modify** — add bulk complete/delete, assignee filter, due date range sort
- `frontend/src/app/(app)/tasks/task-modal.tsx` — **Modify** — add markdown preview, assignee selector, customer/opportunity link selector
- `frontend/src/components/layout/app-sidebar.tsx` — **Modify** — add global quick-add task button in header
- `tests/unit/test_tasks.py` — **New** — unit tests for task service + router
- `tests/integration/test_tasks_integration.py` — **New** — integration tests for task endpoints

## Implementation Steps

### Backend
1. Create `src/api/routers/tasks.py` with these endpoints, matching the patterns in `tickets.py` and the hook calls in `frontend/src/lib/api/queries.ts`:
   - `GET /api/v1/tasks` — list with `page`, `page_size`, `status`, `assigned_to` query params; returns `{success, data: {items, total, page, page_size, has_next}}`
   - `POST /api/v1/tasks` — create; body fields `title`, `description`, `priority`, `status`, `due_date`, `assigned_to`
   - `GET /api/v1/tasks/{task_id}` — single task
   - `PATCH /api/v1/tasks/{task_id}` — update fields
   - `DELETE /api/v1/tasks/{task_id}` — delete
   - `POST /api/v1/tasks/{task_id}/complete` — sets `status=completed`
   - All endpoints use `ctx: AuthContext = Depends(require_auth)` and `session: AsyncSession = Depends(get_db)`
2. Export `tasks_router` from `src/api/__init__.py`
3. Register `tasks_router` in `src/main.py` via `app.include_router(tasks_router)`

### Frontend — Kanban Enhancements
4. In `frontend/src/app/(app)/tasks/page.tsx`:
   - Add `@dnd-kit/core` + `@dnd-kit/sortable` for drag-and-drop between columns (install if not in `package.json`)
   - Make task cards draggable with `useSortable`, columns are droppable zones keyed by `col.id`
   - On drop, call `useUpdateTask().mutateAsync({ id, data: { status: targetColumnId } })`
   - Display accurate column counts by computing `allTasks.filter(t => t.status === col.id).length` from the full dataset; remove the redundant per-status API calls and use only `useTasks(1, "")`

### Frontend — TaskModal Enhancements
5. In `frontend/src/app/(app)/tasks/task-modal.tsx`:
   - Add `react-markdown` or `@uiw/react-md-editor` for description preview/edit toggle
   - Add assignee `Select` dropdown using `useUsers()` hook to populate user list
   - Add optional customer and opportunity link selectors using `useSearchCustomers()` and `useOpportunities()` (or `usePipelines()`) — these store `customer_id` and `opportunity_id` in the task payload but the backend TaskModel stores them via extra fields or a relation

### Frontend — List View Enhancements
6. In `frontend/src/app/(app)/tasks/list/page.tsx`:
   - Add checkbox column for bulk selection
   - Add bulk "Complete" and "Delete" buttons that call `useCompleteTask()` / `useDeleteTask()` on the selected array
   - Add assignee filter dropdown (uses `useUsers()` to populate options)
   - Add created-by date range filter (two date inputs: `created_after`, `created_before`)

### Frontend — Global Quick-Add
7. In `frontend/src/components/layout/app-sidebar.tsx` (or the app layout header):
   - Add a `+` icon button in the top nav bar next to the page title
   - On click, open `TaskModal` with `initialStatus="pending"` pre-selected
   - Pass `onClose` to reset the button state

## Test Plan

- **Unit tests in `tests/unit/test_tasks.py`**: Create a `mock_db_session` fixture using `make_mock_session` with a `task_handler` (add this handler to `conftest.py` following the pattern of `customer_handler`). Test `TaskService` methods: `create_task`, `get_task`, `update_task`, `complete_task`, `delete_task`, `list_tasks`. Also test the router functions directly by constructing a mock `App` with `tasks_router` mounted and calling endpoint handlers with mocked session/auth.

- **Integration tests in `tests/integration/test_tasks_integration.py`**: Use `db_schema`, `tenant_id`, `async_session` fixtures. Test full round-trip: create task via `POST /api/v1/tasks`, retrieve via `GET /api/v1/tasks/{id}`, list via `GET /api/v1/tasks?status=pending`, update via `PATCH /api/v1/tasks/{id}`, complete via `POST /api/v1/tasks/{id}/complete`, delete via `DELETE /api/v1/tasks/{id}`. Verify response envelope shape `{success, data}` and status codes.

## Acceptance Criteria

- `GET /api/v1/tasks` returns `{success: true, data: {items: [...], total: N, page, page_size, has_next}}`
- `POST /api/v1/tasks` returns 201 with `{"success": true, "data": <task dict>}`
- `PATCH /api/v1/tasks/{id}` updates and returns the task
- `POST /api/v1/tasks/{id}/complete` sets status to `completed`
- `DELETE /api/v1/tasks/{id}` returns 200
- Kanban board renders 3 columns (To Do / In Progress / Done) with accurate task counts
- Drag-and-drop moves a card from one Kanban column to another and persists via API
- Task detail modal shows title, description with markdown toggle, status, priority, due date, assignee dropdown
- Task list view has filters for status, priority, assignee, and sort by due date/priority/created date
- Bulk complete and bulk delete work on the list view with checkbox selection
- Unit tests for `TaskService` pass with mocked DB
- Integration tests for all task API endpoints pass against real PostgreSQL
