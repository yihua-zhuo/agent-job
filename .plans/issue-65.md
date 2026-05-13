I now have a thorough understanding of the codebase. Let me write the implementation plan.

# Implementation Plan — Issue #65

## Goal

Add a visual rule builder UI for the automation rules engine already present in the backend. Admin users can create, edit, enable/disable, and monitor automation rules via three new pages (rules list, rule builder, execution history) and a templates gallery — all consuming the existing `/api/v1/automation` endpoints.

## Affected Files

**Backend** (no changes needed — all endpoints already exist):
- `src/api/routers/automation.py` — already exposes full CRUD + logs endpoints
- `src/services/automation_service.py` — already implements rule engine
- `src/db/models/automation.py` — already defines ORM models

**Frontend — new files:**
- `frontend/src/lib/api/queries.ts` — add automation rule query/mutation hooks
- `frontend/src/components/layout/app-sidebar.tsx` — add "Automation" nav item
- `frontend/src/app/(app)/automation/rules/page.tsx` — rules list page
- `frontend/src/app/(app)/automation/rules/new/page.tsx` — rule builder page
- `frontend/src/app/(app)/automation/rules/[id]/edit/page.tsx` — edit existing rule
- `frontend/src/app/(app)/automation/rules/templates/page.tsx` — templates gallery
- `frontend/src/app/(app)/automation/rules/history/page.tsx` — execution history
- `frontend/src/app/(app)/automation/rules/history/[rule_id]/page.tsx` — per-rule history
- `frontend/src/components/automation/rule-builder.tsx` — shared rule builder form component
- `frontend/src/components/automation/trigger-selector.tsx` — trigger selector control
- `frontend/src/components/automation/condition-row.tsx` — condition row with field/operator/value
- `frontend/src/components/automation/action-row.tsx` — action row with type/params
- `frontend/src/app/(app)/automation/rules/[id]/page.tsx` — rule detail/read-only view

**Frontend — test files:**
- `tests/unit/test_automation_rules_ui.py` — unit tests for rule builder component state
- `tests/integration/test_automation_rules_integration.py` — integration tests for rule CRUD UI flow

## Implementation Steps

1. **Add API hooks to `frontend/src/lib/api/queries.ts`.** Add `useAutomationRules`, `useAutomationRule`, `useCreateAutomationRule`, `useUpdateAutomationRule`, `useDeleteAutomationRule`, `useToggleAutomationRule`, `useAutomationLogs` following the same pattern as existing hooks (TanStack Query + `apiClient`, token from `useAuthStore`, invalidates appropriate keys). Use query keys under `"automation_rules"` and `"automation_logs"`.

2. **Add sidebar navigation.** In `app-sidebar.tsx`, add an `"Automation"` item with a `Zap` or `Workflow` icon to `crmItems` array (or a new section), linking to `/automation/rules`.

3. **Build shared form components.** Create `frontend/src/components/automation/trigger-selector.tsx` — a `<Select>` backed by `TRIGGER_EVENTS` from the backend (`ticket.created`, `ticket.updated`, `ticket.assigned`, `opportunity.stage_changed`, `opportunity.created`, `customer.created`, `customer.updated`, `user.login`, `lead.created`). Create `condition-row.tsx` — three fields: field name `<Input>`, operator `<Select>` (eq/ne/gt/gte/lt/lte/contains/startswith/endswith), value `<Input>` — all inside a `d-flex` row with a remove button. Create `action-row.tsx` — action type `<Select>` (notification.send / ticket.assign / ticket.update_priority / opportunity.add_note / task.create / email.send / webhook.call / tag.add), then a dynamic params form based on selected type (e.g. user_id for notification, priority for ticket.update_priority), with a remove button.

4. **Build `rule-builder.tsx` shared component.** Accepts `initialValues?`, `onSubmit`, `onCancel`. Renders a `<form>` with: name `<Input>`, description `<Textarea>`, `TriggerSelector`, a "IF Conditions" section listing `ConditionRow` components with "Add condition" button, a "THEN Actions" section listing `ActionRow` components with "Add action" button, and a "Save as draft / Activate" footer. Handles client-side validation (at least one action required). Does not call the API directly — calls `onSubmit` prop with the serialized form data.

5. **Build rules list page `/automation/rules`.** `frontend/src/app/(app)/automation/rules/page.tsx` — patterned after `tickets/page.tsx`. Table columns: checkbox, name, trigger (badge), status (enabled toggle switch per row), last run (from latest log), actions (`DropdownMenu` with Edit link, Delete). "Create Rule" button links to `/automation/rules/new`. Pagination (page/page_size). Row actions: click Edit → router.push(`/automation/rules/${id}/edit`), click History → router.push(`/automation/rules/history?rule_id=${id}`). Toggle calls `useToggleAutomationRule` mutation and invalidates list. Delete confirms then calls mutation.

6. **Build rule detail page `/automation/rules/[id]`.** Read-only view showing name, trigger badge, enabled status, conditions list, actions list. "Edit" and "View History" buttons. Calls `useAutomationRule(id)`.

7. **Build rule builder page `/automation/rules/new`.** Page with header "Create Automation Rule". Renders `<RuleBuilder>` with `onSubmit` calling `useCreateAutomationRule`. On success, router.push to `/automation/rules` with a toast/alert.

8. **Build rule edit page `/automation/rules/[id]/edit`.** Fetches existing rule with `useAutomationRule(id)`, passes `initialValues` to `<RuleBuilder>`. `onSubmit` calls `useUpdateAutomationRule`. On success, router.push to `/automation/rules`.

9. **Build templates gallery `/automation/rules/templates`.** Static gallery of pre-built rules: "High-value ticket alert" (ticket.created + priority=high → notification.send), "Win-back campaign" (customer.updated + churn_risk=high → task.create + email.send), "New opportunity notification" (opportunity.created → notification.send), "Ticket SLA breach warning" (ticket.updated + sla_breached=true → notification.send), "Lead follow-up" (lead.created → task.create). Each card shows name, description, trigger, actions. "Activate" button creates the rule via API (POST without enabling), then toggles it (POST `/rules/{id}/toggle`).

10. **Build execution history page `/automation/rules/history`.** Table: rule name (link to rule detail), trigger event, status badge (success=green, failed=red), executed at, error message (truncated). Filter by `rule_id` (optional URL param) and `status`. "View" action links to `/automation/rules/history/${rule_id}`. Calls `useAutomationLogs(page, pageSize, ruleId, status)`.

11. **Add unit tests `tests/unit/test_automation_rules_ui.py`.** Test the rule builder form state: adding/removing conditions and actions, selecting trigger, serializing form data correctly for known inputs, validation (at least one action required). Use React Testing Library to mount the component and assert form behavior.

12. **Add integration tests `tests/integration/test_automation_rules_integration.py`.** Test the full rule CRUD cycle: create rule via API, retrieve it, update it, toggle it, delete it. Test execution log creation via `POST /api/v1/automation/trigger`. Use the `db_schema` fixture and the existing integration test pattern.

## Test Plan

- **Unit tests in `tests/unit/`:**
  - `test_automation_rules_ui.py` — rule builder component state, condition/action add/remove, form serialization, validation

- **Integration tests in `tests/integration/`:**
  - `test_automation_rules_integration.py` — full CRUD cycle (create, read, update, toggle, delete) via API, trigger execution and log retrieval

## Acceptance Criteria

- Rules list page renders a table with name, trigger badge, enabled toggle, edit/delete actions, and a "Create Rule" button at `/automation/rules`
- Toggle on a rule row enables/disables the rule via `POST /api/v1/automation/rules/{id}/toggle`
- Rule builder page at `/automation/rules/new` has all three sections (trigger, conditions, actions) and saves via `POST /api/v1/automation/rules`
- Edit page at `/automation/rules/[id]/edit` pre-populates the form and saves via `PUT /api/v1/automation/rules/{id}`
- Delete on a rule row calls `DELETE /api/v1/automation/rules/{id}` and removes the row
- Templates page shows at least 4 pre-built rule cards with "Activate" that creates and enables a rule in one flow
- Execution history at `/automation/rules/history` shows log entries with status badges and "View" links per rule
- All pages are protected by `AuthGuard` (user must be logged in)
- All API calls use the existing `useAuthStore` token pattern; no new backend endpoints are required
