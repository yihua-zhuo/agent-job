# Implementation Plan — Issue #77

## Goal

Add automated, rule-based lead routing so that leads (customers with status="lead") are automatically assigned to the right sales rep based on geography, industry, company size, or time window. Unassigned or un-responded leads are automatically recycled back into the pool after 24 hours, up to a configurable maximum (default 3). This replaces manual抢单 and removes the admin burden of equitable distribution.

## Affected Files

- `src/db/models/customer.py` — add `assigned_at`, `recycle_count`, `recycle_history` (JSON) fields to `CustomerModel`
- `src/db/models/routing_rule.py` *(new)* — ORM model for `routing_rules` table
- `src/models/routing.py` *(new)* — Pydantic schemas for rule DTOs and condition builders
- `src/services/lead_routing_service.py` *(new)* — routing engine: rule evaluation, load-balanced assignee selection, round-robin fallback, recycling logic
- `src/api/routers/lead_routing.py` *(new)* — REST endpoints: CRUD for routing rules, rule priority ordering, rule test preview
- `src/api/routers/customers.py` — add `GET /api/v1/sales/leads` (unassigned leads queue), `POST /api/v1/customers/{id}/reassign`, and SLA countdown in customer detail
- `src/services/customer_service.py` — extend `assign_owner` to set `assigned_at`, add `reassign_lead` and `recycle_lead` methods, add `get_unassigned_leads` and `get_leads_by_owner`
- `src/main.py` — register `lead_routing_router`
- `alembic/env.py` — import `RoutingRuleModel` so `--autogenerate` picks it up
- `alembic/versions/<rev>_add_lead_routing.py` *(generated)* — migration for `routing_rules` table and new customer columns
- `tests/unit/conftest.py` — add `make_routing_rule_handler(state)` and `make_lead_routing_handler(state)` factory handlers for unit tests
- `tests/unit/test_lead_routing_service.py` *(new)* — unit tests for rule matching, load balancing, round-robin, SLA/cycle logic
- `tests/unit/test_customers_router.py` — add test cases for new `/sales/leads` and reassign endpoints
- `tests/integration/conftest.py` — add `_seed_routing_rule` helper
- `tests/integration/test_lead_routing_integration.py` *(new)* — integration tests covering rule CRUD, auto-assignment on lead creation, manual override, SLA recycling, and max-recycle disqualification

## Implementation Steps

**Step 1 — DB migration**

Create `src/db/models/routing_rule.py` with `RoutingRuleModel` (id, tenant_id, name, conditions_json, assignee_type, assignee_id, priority, is_active, created_at, updated_at). Run autogenerate against a clean `alembic_dev` DB, then manually fix the migration (data migrations, index declarations). Apply migration. Update `alembic/env.py` to import the new model.

**Step 2 — Pydantic schemas**

Create `src/models/routing.py` with: `RuleCondition` (field, operator, value), `RoutingRuleCreate`, `RoutingRuleUpdate`, `RoutingRuleResponse`, `LeadAssignPreview`, `RecycleHistoryEntry`. Supported fields: region, industry, employee_count, source, created_date. Operators: equals, not_equals, in, not_in, gt, lt, gte, lte, between.

**Step 3 — LeadRoutingService**

Create `src/services/lead_routing_service.py` with:

- `evaluate_conditions(conditions: list[RuleCondition], customer: dict) -> bool` — evaluate a rule's conditions against a customer record
- `get_matching_rule(tenant_id, customer) -> RoutingRuleModel | None` — find highest-priority active rule whose conditions match; if none, fall back to round-robin
- `select_assignee(rule: RoutingRuleModel, tenant_id: int) -> int` — for "user" type: count active leads per eligible sales user and pick lowest; for "team": pick lowest-load user in team; for "round_robin": track cursor in Redis/DB and advance
- `auto_assign_lead(customer_id: int, tenant_id: int) -> int` — evaluate rules, select assignee, call `CustomerService.assign_owner` with `assigned_at` set
- `recycle_stale_leads(tenant_id: int) -> list[int]` — scan leads with `assigned_at` older than configurable threshold (default 24h), `recycle_count < max_recycle`, set `owner_id=0`, `recycle_count += 1`, push to `recycle_history`, return list of recycled IDs
- `disqualify_over cycled_leads(tenant_id: int) -> list[int]` — called from the scheduled job: leads where `recycle_count >= max_recycle` get status changed to "disqualified"
- `get_sla_status(assigned_at: datetime) -> str` — return "green" (<2h), "yellow" (<24h), "red" (>24h)

**Step 4 — CustomerService extensions**

Add to `CustomerService`:

- `assign_owner` sets `assigned_at = now()` on first assignment
- `reassign_lead(customer_id, new_owner_id, tenant_id, reason)` — saves previous owner to `recycle_history`, increments `recycle_count`, updates `owner_id` and `assigned_at`
- `get_unassigned_leads(tenant_id, page, page_size)` — `owner_id=0 AND status="lead"`, ordered by `created_at ASC`
- `get_leads_by_owner(owner_id, tenant_id)` — leads with that owner_id
- `bulk_recycle(ids: list[int], tenant_id)` — batch version used by the scheduled job

Add to `CustomerModel`: `assigned_at: Mapped[datetime | None]`, `recycle_count: Mapped[int] = mapped_column(default=0)`, `recycle_history: Mapped[list] = mapped_column(JSON, default=list)`. Add to `to_dict()`.

**Step 5 — REST API: routing rules**

Create `src/api/routers/lead_routing.py` with:

- `GET /api/v1/settings/routing` — list rules (name, conditions summary, assignee, priority, is_active)
- `POST /api/v1/settings/routing` — create rule
- `PUT /api/v1/settings/routing/{rule_id}` — update rule
- `DELETE /api/v1/settings/routing/{rule_id}` — delete rule
- `PUT /api/v1/settings/routing/{rule_id}/priority` — bulk reorder (body: `{rule_ids: list[int]}`), update `priority` column for all in list
- `PUT /api/v1/settings/routing/{rule_id}/toggle` — enable/disable
- `POST /api/v1/settings/routing/test` — `{conditions, customer_data}` → return which rule would match + assignee preview, no side effects

All endpoints require `admin` or `manager` role via `RBACService.require_permission`.

**Step 6 — REST API: lead distribution**

In `src/api/routers/customers.py`, add:

- `GET /api/v1/sales/leads` — unassigned leads queue with SLA indicator per lead; `?status=unassigned|assigned|recycled`
- `GET /api/v1/customers/{id}/assignment` — current assignment info: assigned_to, assigned_at, SLA countdown, recycle_count, recycle_history
- `POST /api/v1/customers/{id}/assign` — manual assign: `{owner_id}` + optional `{reason}`; bypasses routing rules
- `POST /api/v1/customers/{id}/reassign` — reassign with reason (logged to recycle_history)
- `POST /api/v1/sales/leads/recycle` — trigger manual recycle (admin/manager only), body: `{customer_ids: list[int]}`

**Step 7 — Background job (recycle)**

The scheduled job is a standalone async function `check_and_recycle_leads(sessionmaker)` called every 30 minutes (integration via external scheduler / APScheduler — not implemented in this PR). The function calls `LeadRoutingService.recycle_stale_leads` then `disqualify_over cycled_leads`. For notification: call `NotificationService.send_lead_recycled(lead_id, previous_owner_id)` for each recycled lead.

**Step 8 — Auto-assignment trigger**

In `CustomerService.create_customer`, after the INSERT flush: if `status == "lead"` and `owner_id == 0`, call `LeadRoutingService.auto_assign_lead(customer.id, tenant_id)`. This requires `LeadRoutingService` to be instantiated with the same session or a separate session.

**Step 9 — Load balancing threshold**

The load-balance skip threshold (>20 active leads per rep) is configurable via tenant settings. Read from `TenantModel.settings["lead_routing"]["max_load_per_rep"]` with fallback to `20`. When no eligible rep is below threshold, fall back to the lowest-load rep (no skip).

## Test Plan

- **Unit tests in `tests/unit/`**:
  - `test_lead_routing_service.py` — rule matching (all operators), load balancing (selects lowest-load, skips overloaded, falls back to lowest when all overloaded), round-robin cursor behavior, `recycle_stale_leads` (marks owner=0, increments count, records history), `disqualify_over cycled_leads` (status→disqualified when count >= max), `get_sla_status` (green/yellow/red thresholds), `auto_assign_lead` (no rule → round-robin, rule matched → correct assignee)
  - `test_lead_routing_router.py` *(new)* — CRUD endpoints, priority reorder, toggle, test-rule preview (mocked service)
  - `test_customers_router.py` (extend) — `/sales/leads` returns unassigned, assignment endpoint returns SLA data, reassign logs to history

- **Integration tests in `tests/integration/`**:
  - `test_lead_routing_integration.py` — create rule, create lead with status=lead, verify owner auto-assigned; update rule to not match, create lead, verify round-robin; reassign lead manually and verify history; wait (mock time) and trigger recycle, verify owner=0 and count incremented; reach max recycle, trigger disqualify, verify status=disqualified; toggle rule off and verify it is skipped
  - `test_sales_leads_endpoint_integration.py` *(new)* — `GET /api/v1/sales/leads` returns correct subset; SLA indicators computed from `assigned_at`

## Acceptance Criteria

- Creating a lead (POST /api/v1/customers with status="lead", owner_id=0) automatically assigns an owner within the same request, returned in the response
- A routing rule with `conditions_json: [{"field": "region", "operator": "in", "value": ["APAC"]}]` assigned to user_id=5 only assigns leads with `region=APAC` to user 5
- `GET /api/v1/sales/leads?status=unassigned` returns only leads with `owner_id=0` and `status=lead` for the current tenant, ordered by `created_at ASC`
- `GET /api/v1/customers/{id}/assignment` returns `assigned_to`, `assigned_at`, `sla_status` ("green"/"yellow"/"red"), `recycle_count`, `recycle_history`
- After 24 hours without response, a recycled lead has `owner_id=0`, `recycle_count` incremented by 1, and an entry in `recycle_history`
- After 3 recycles (recycle_count=3), the next recycle attempt changes status to "disqualified"
- `PUT /api/v1/settings/routing/{rule_id}/toggle` disables a rule; disabled rules are skipped during auto-assignment
- `POST /api/v1/settings/routing/test` with sample conditions returns the matched rule and assignee without persisting any change
- All SQL queries in routing and customer services filter by `tenant_id`
