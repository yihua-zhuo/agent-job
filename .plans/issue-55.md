# Implementation Plan — Issue #55

## Goal

Build a full ticket management UI: an enhanced ticket list with filters, Kanban view, and bulk operations; a detail page with description, comments, sidebar, and activity log; and an SLA countdown timer with breach notification toasts.

## Affected Files

- `frontend/src/app/(app)/tickets/page.tsx` — expand table with category/assignee/SLA columns, Kanban toggle, bulk actions, "Create Ticket" dialog
- `frontend/src/app/(app)/tickets/[id]/page.tsx` — new ticket detail page (header, description, replies, sidebar, activity log, actions)
- `frontend/src/components/tickets/sla-timer.tsx` — new reusable SLA countdown component with color thresholds and breach flash
- `frontend/src/components/tickets/kanban-board.tsx` — new Kanban board component with drag-to-group columns
- `frontend/src/components/tickets/ticket-form-dialog.tsx` — new create/edit ticket dialog
- `frontend/src/components/tickets/bulk-actions-bar.tsx` — new floating bulk-assign / bulk-status-change bar
- `frontend/src/lib/api/queries.ts` — add `useTicket`, `useTicketReplies`, `useAddReply`, `useUpdateTicket`, `useChangeTicketStatus`, `useBulkUpdateTickets`, `useAutoAssignTicket` hooks
- `src/api/routers/tickets.py` — add `GET /tickets/{id}/replies` and `GET /tickets/{id}/activity` endpoints (fetch replies and activity log)
- `src/services/ticket_service.py` — add `get_ticket_replies(ticket_id, tenant_id)` and `get_ticket_activity(ticket_id, tenant_id)` methods
- `tests/unit/test_tickets_router.py` — add test classes for new endpoints and service methods
- `tests/integration/test_tickets_integration.py` — new integration test file for full ticket CRUD flow

## Implementation Steps

1. **Add missing backend endpoints.** In `src/services/ticket_service.py`, add `get_ticket_replies(ticket_id, tenant_id)` (query `TicketReplyModel` filtered by ticket_id and tenant_id, ordered by `created_at asc`) and `get_ticket_activity(ticket_id, tenant_id)` (query activity log records filtered by entity_type=ticket and entity_id=ticket_id). In `src/api/routers/tickets.py`, add `GET /tickets/{ticket_id}/replies` and `GET /tickets/{ticket_id}/activity` endpoints.

2. **Add frontend query hooks.** In `frontend/src/lib/api/queries.ts`, add `useTicket(id)`, `useTicketReplies(ticketId)`, `useAddReply()`, `useUpdateTicket()`, `useChangeTicketStatus()`, `useAutoAssignTicket()`, and bulk `useBulkUpdateTickets()` mutations with proper cache invalidation.

3. **Build `sla-timer.tsx` component.** Accept `responseDeadline: string | null`, `createdAt: string`, `slaLevel: string`. Compute elapsed/total ratio; render color-coded badge: green when >50%, yellow 25–50%, red <25%, pulsing red border when breached. Show remaining time in "Xh Ym" format.

4. **Build `ticket-form-dialog.tsx` component.** Radix Dialog with subject, description (Textarea), customer_id (Select backed by `useCustomers`), channel Select, priority Select, sla_level Select. POST via `useCreateTicket()` or PATCH via `useUpdateTicket()`. Include "Create Ticket" button in list page header.

5. **Build `kanban-board.tsx` component.** Accept `tickets: TicketRowData[]`, `groupBy: "status" | "priority" | "assignee"`. Render CSS grid columns. Each column is a scrollable list of `TicketCard` sub-components (subject, status badge, priority badge, SLA timer, assignee avatar). Status group columns: Open, In Progress, Pending, Resolved, Closed. Priority groups: Urgent, High, Medium, Low. Assignee groups: unassigned + per-agent.

6. **Build `bulk-actions-bar.tsx` component.** Floating bar that appears when `selectedIds.size > 0`. Shows count selected, "Assign to" Select (agents from `useUsers`), "Change status to" Select, and "Apply" button. Calls `useBulkUpdateTickets()` mutation.

7. **Enhance `tickets/page.tsx`.** Add priority and category (channel) filter selects alongside existing status filter. Add assignee filter (populated from `useUsers`). Add sort options for priority and SLA deadline (client-side sort on `response_deadline`). Add Kanban/Table toggle button in header. When Kanban is active, render `<KanbanBoard>` with `groupBy="status"`. Add bulk actions bar and create ticket dialog. Add SLA timer column in table view. Ensure "View details" row action navigates to `/tickets/${id}`.

8. **Create `frontend/src/app/(app)/tickets/[id]/page.tsx`.** Implement full detail page:
   - Header row: `#{id} — {subject}` left-aligned, status and priority Badge components right-aligned, Edit and Delete icon buttons.
   - Two-column layout (2/3 + 1/3): left = description block (rendered markdown via `react-markdown`), reply thread (fetched via `useTicketReplies`, each reply shows author avatar (initials via Avatar component), content, timestamp, is_internal badge). Below replies: Textarea + "Send Reply" / "Internal Note" toggle + "Send" button using `useAddReply()`.
   - Right sidebar: Card showing assignee (Avatar + name or "Unassigned"), priority, channel, SLA timer component, customer link, created_at. Below sidebar: activity log section (fetched via `useTicketActivity`, list of timestamped entries).
   - Edit mode: inline Dialog with pre-filled `TicketFormDialog` for editing subject/description/priority/channel.

9. **Wire breach notification toasts.** In the tickets list and detail pages, on mount check `useSlaBreaches()`. If any returned ticket matches the current ticket's ID, fire `toast.error("SLA breached on ticket #X")` using the existing `sonner` package already in package.json.

10. **Add unit tests.** In `tests/unit/test_tickets_router.py`, add `TestGetTicketRepliesEndpoint` and `TestGetTicketActivityEndpoint` classes using `MockReply`. Add service-level tests for `get_ticket_replies` and `get_ticket_activity` in a new `tests/unit/test_ticket_service.py`.

11. **Add integration tests.** Create `tests/integration/test_tickets_integration.py` using `db_schema`, `tenant_id`, `async_session` fixtures. Test: create ticket → fetch detail → add reply → change status → verify SLA timer logic, bulk assign flow, and Kanban grouping (list endpoints return correct data shape for all filter combinations).

## Test Plan

- Unit tests in `tests/unit/`: `test_tickets_router.py` (add new endpoint test classes), `test_ticket_service.py` (new file — test `get_ticket_replies`, `get_ticket_activity`, SLA calculation logic)
- Integration tests in `tests/integration/`: `test_tickets_integration.py` (new — full create → detail → reply → status-change flow against real DB)

## Acceptance Criteria

- List page renders all ticket columns (ID, title, status, priority, channel, assignee, SLA countdown) with working sort by priority and SLA deadline
- Status, priority, channel, and assignee filter selects narrow results correctly
- Kanban toggle switches between table and board views; Kanban groups by status by default
- Bulk selection checkboxes work; bulk-assign and bulk-status-change bar appears and applies changes via API
- "Create Ticket" dialog submits and new ticket appears in list without page refresh
- Ticket detail page at `/tickets/:id` renders subject, markdown description, reply thread, sidebar (assignee, priority, SLA timer, customer), and activity log
- Reply submission adds reply to thread without refresh; internal notes show a distinct visual indicator
- SLA timer shows correct color at each threshold; breached ticket shows pulsing animation
- SLA breach toast fires when opening a ticket whose SLA is already breached
- All API endpoints return correct status codes and response shapes per existing router patterns
- Backend routes covered by unit tests; full CRUD flow covered by integration tests
