Now I have everything I need. Let me write the implementation plan.

# Implementation Plan — Issue #594

## Goal

Implement `NotificationRoutingService` in `src/services/notification_routing_service.py` — a rule-based service that accepts a `SmartNotification` record (from the dependent #593 model) and returns a `list[ChannelDelivery]` by applying three dispatch rules: urgent → in-app + email, normal → in-app only, low → batch (daily digest). No LLM calls. No delivery dispatch. Unit tested with the project's mock-session pattern.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0594-implement-notificationrouting-service.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0594-implement-notificationrouting-service.md`

## Affected Files

- `src/models/channel_delivery.py` — **new file** — `ChannelDelivery` Pydantic dataclass (return type)
- `src/services/notification_routing_service.py` — **new file** — `NotificationRoutingService` class with rule-based routing
- `tests/unit/test_notification_routing.py` — **new file** — 6 unit tests covering all routing paths + error path
- `tests/unit/conftest.py` — read `make_mock_session([])` pattern used to build mock session for tests

## Implementation Steps

### Step 1: Create `src/models/channel_delivery.py`

Create the `ChannelDelivery` Pydantic dataclass — the return type for routing decisions. Place alongside existing Pydantic models in `src/models/` (e.g., `routing.py`, `customer.py`). No DB migration needed — this is a pure dataclass.

```python
from pydantic import BaseModel, Field


class ChannelDelivery(BaseModel):
    """Represents a single routing decision — which channel to deliver a notification on."""

    channel: str = Field(description="Delivery channel: in_app | email | batch")
    target: str = Field(description="Recipient address: user_id for in_app, email addr for email, 'daily_digest' for batch")
    priority: str = Field(description="Original notification priority: urgent | normal | low")
    status: str = Field(default="pending", description="Routing status: pending | routed")
    tenant_id: int = Field(description="Tenant for multi-tenant isolation")

    model_config = {"from_attributes": True}
```

**Verification**: `ruff check src/models/channel_delivery.py` → 0 errors

---

### Step 2: Create `src/services/notification_routing_service.py`

Implement `NotificationRoutingService` following the service pattern from [`src/services/customer_service.py`](src/services/customer_service.py) L16-L22:
- `__init__(self, session: AsyncSession)` — no default, assigns `self.session`
- `route(self, notification, tenant_id: int) -> list[ChannelDelivery]` — async, stateless (no DB writes)
- Raises `ValidationException` from [`src/pkg/errors/app_exceptions.py`](src/pkg/errors/app_exceptions.py) L35 for unknown priority
- Does **not** call `.to_dict()`; does **not** return `ApiResponse`

Routing rules (rule-based, no LLM):
- `urgent` → one `ChannelDelivery` with `channel="in_app"` + one with `channel="email"`
- `normal` → one `ChannelDelivery` with `channel="in_app"` only
- `low` → one `ChannelDelivery` with `channel="batch"`, `target="daily_digest"`, `status="pending"`

The `notification` parameter uses `getattr` for graceful compatibility with a plain mock object (before #593 lands) and with the real ORM model after #593 merges.

**Verification**: `ruff check src/services/notification_routing_service.py` → 0 errors

---

### Step 3: Create `tests/unit/test_notification_routing.py`

Write 6 unit tests using the mock session pattern from [`tests/unit/conftest.py`](tests/unit/conftest.py) L234-L255. Call `make_mock_session([])` (empty handlers — routing is stateless, no DB needed).

Test cases:

| Test | Input | Expected |
|------|-------|----------|
| `test_urgent_routes_to_in_app_and_email` | priority="urgent", user_id=42, email="user@example.com" | 2 records, channels == {"in_app", "email"}, both status="routed" |
| `test_normal_routes_to_in_app_only` | priority="normal", user_id=42 | 1 record, channel="in_app" |
| `test_low_routes_to_batch` | priority="low" | 1 record, channel="batch", target="daily_digest", status="pending" |
| `test_unknown_priority_raises` | priority="invalid" | raises `ValidationException` |
| `test_tenant_id_carried_on_all_records` | priority="urgent", tenant_id=99 | all records have tenant_id=99 |
| `test_normal_without_user_id_returns_empty_list` | priority="normal", user_id=None | returns [] |

Mock the notification as a plain `MagicMock` object with `.priority`, `.user_id`, `.email` attributes (drop-in replaceable once #593 provides the real ORM model).

**Verification**: `PYTHONPATH=src pytest tests/unit/test_notification_routing.py -v` → 6 passed

---

### Step 4: Lint all new files

Run ruff on every new file to catch import errors, formatting issues, and unused imports:

```bash
ruff check src/models/channel_delivery.py src/services/notification_routing_service.py tests/unit/test_notification_routing.py
```

**Verification**: all three commands exit 0

---

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_notification_routing.py` (new) — 6 tests covering all three routing rules, error case (unknown priority), tenant_id propagation, and edge case (normal without user_id). No real DB; uses `make_mock_session([])`.
- **Integration tests in `tests/integration/`**: none — this is a stateless rule-based service with no DB writes; routing logic is fully covered by unit tests.
- **Dev-plan verification**: run each §6 acceptance criterion command:
  - `ruff check src/services/notification_routing_service.py src/models/channel_delivery.py` → 0 errors
  - `ruff check tests/unit/test_notification_routing.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_notification_routing.py -v` → 6 passed

## Acceptance Criteria

- `ruff check src/services/notification_routing_service.py src/models/channel_delivery.py tests/unit/test_notification_routing.py` → 0 errors on all three
- `PYTHONPATH=src pytest tests/unit/test_notification_routing.py -v` → 6 passed
- `NotificationRoutingService.__init__` accepts `session: AsyncSession` with **no default value**
- `svc.route(notif, tenant_id=N)` returns `list[ChannelDelivery]` where:
  - priority="urgent" → 2 records, channels {"in_app", "email"}, status="routed"
  - priority="normal" → 1 record, channel="in_app"
  - priority="low" → 1 record, channel="batch", target="daily_digest", status="pending"
- `svc.route(notif, tenant_id=N)` with unknown priority raises `ValidationException`
- All returned `ChannelDelivery` records carry the passed `tenant_id`
