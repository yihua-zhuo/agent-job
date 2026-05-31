I now have a complete picture of the codebase. Here is the implementation plan.

---

# Implementation Plan — Issue #595

## Goal

Add `POST /notifications/smart` to the existing `notifications_router` at `src/api/routers/notifications.py`. The endpoint accepts a pre-classified event payload, persists a `SmartNotificationModel` record, calls `NotificationRoutingService.route()`, and returns the delivery status. It requires `AuthContext`, enforces tenant isolation, and includes a `TODO` comment pointing to issue #41 for future LLM integration. Unit tests live in `tests/unit/test_notifications.py`.

---

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0595-add-post-notifications-smart-endpoint.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0595-add-post-notifications-smart-endpoint.md`

---

## Affected Files

- `src/api/routers/notifications.py` — add `SmartNotificationCreate` Pydantic schema and `POST /notifications/smart` endpoint
- `src/services/notification_service.py` — add `create_smart_notification` method
- `tests/unit/test_notifications.py` — **create new file** with unit tests for the new endpoint

---

## Implementation Steps

### Step 1: Add `create_smart_notification` to `NotificationService`

Open `src/services/notification_service.py` and add an import for `SmartNotificationModel` alongside the existing model imports. Then add a new async method to `NotificationService`:

```python
async def create_smart_notification(
    self,
    summarized_content: str,
    priority: int,
    channel: int,
    timing: int,
    tenant_id: int,
    recipient_filter: dict | None = None,
) -> SmartNotificationModel:
    """Persist a smart notification record and return it.

    Actual channel routing is performed by NotificationRoutingService.route()
    in the router — this method only persists.
    """
    notification = SmartNotificationModel(
        tenant_id=tenant_id,
        summarized_content=summarized_content,
        priority=priority,
        channel=channel,
        timing=timing,
        recipient_filter=recipient_filter,
    )
    self.session.add(notification)
    await self.session.flush()
    return notification
```

The import to add (after the existing `NotificationModel` import):
```python
from db.models.smart_notification import SmartNotificationModel
```

**Completion check**: `PYTHONPATH=src python -c "from services.notification_service import NotificationService; print('ok')"` exits 0.

### Step 2: Add Pydantic request schema and `POST /notifications/smart` endpoint

Open `src/api/routers/notifications.py`. Add the import for the enums and the routing service at the top of the existing imports block:

```python
from db.models.smart_notification import Priority, Channel, Timing
from models.channel_delivery import ChannelDelivery
from services.notification_routing_service import NotificationRoutingService
```

Add the `SmartNotificationCreate` Pydantic schema after the existing `ReminderCreate` class (before the `# Notification endpoints` comment):

```python
class SmartNotificationCreate(BaseModel):
    summarized_content: str = Field(..., min_length=1, max_length=1024)
    priority: int = Field(..., ge=0, le=2, description="0=urgent, 1=normal, 2=low")
    channel: int = Field(..., ge=0, le=3, description="0=email, 1=sms, 2=push, 3=in_app")
    timing: int = Field(..., ge=0, le=1, description="0=immediate, 1=batch")
    recipient_filter: dict | None = Field(None, description="Filter criteria for routing")

    @field_validator("priority")
    @classmethod
    def priority_must_be_valid(cls, v: int) -> int:
        if v not in {p.value for p in Priority}:
            raise ValueError(f"priority must be 0 (urgent), 1 (normal), or 2 (low), got {v}")
        return v

    @field_validator("channel")
    @classmethod
    def channel_must_be_valid(cls, v: int) -> int:
        if v not in {c.value for c in Channel}:
            raise ValueError(f"channel must be 0 (email), 1 (sms), 2 (push), or 3 (in_app), got {v}")
        return v
```

Add the endpoint after the `send_notification` endpoint (before `PUT /notifications/{id}/read`):

```python
@notifications_router.post(
    "/notifications/smart",
    summary="Create a smart notification with routing",
)
async def create_smart_notification(
    body: SmartNotificationCreate,
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Accept a pre-classified event payload, persist a SmartNotification, and route it.

    The LLM classification integration is tracked in issue #41.
    """
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    svc = NotificationService(session)
    record = await svc.create_smart_notification(
        summarized_content=body.summarized_content,
        priority=body.priority,
        channel=body.channel,
        timing=body.timing,
        tenant_id=current_user.tenant_id,
        recipient_filter=body.recipient_filter,
    )

    # Route via NotificationRoutingService to determine delivery channels
    routing_svc = NotificationRoutingService(session)
    deliveries = await routing_svc.route(record, tenant_id=current_user.tenant_id)

    return {
        "success": True,
        "data": {
            "notification": record.to_dict(),
            "deliveries": [d.model_dump() for d in deliveries],
        },
        "message": "Smart notification created and routed",
    }
```

#### Priority IntEnum → string adapter (part of Step 2)

`NotificationRoutingService.route()` reads `getattr(notification, "priority", None)` and expects string values (`"urgent"`, `"normal"`, `"low"`), but `SmartNotificationModel.priority` is a `Priority` IntEnum (values `0`, `1`, `2`). Directly passing the ORM object to `route()` would cause a `ValidationException`.

Add the following constants and helper class before the `# Notification endpoints` comment (after `SmartNotificationCreate`):

```python
_PRIORITY_MAP = {Priority.urgent: "urgent", Priority.normal: "normal", Priority.low: "low"}


def _priority_to_string(priority) -> str:
    """Convert a priority value (Priority enum, int, or string) to routing string."""
    if isinstance(priority, Priority):
        return _PRIORITY_MAP[priority]
    if isinstance(priority, int):
        try:
            return _PRIORITY_MAP[Priority(priority)]
        except KeyError:
            return str(priority)
    return str(priority)


class _MockRoutingRecord:
    """Lightweight adapter that exposes priority as a string for NotificationRoutingService.

    Rather than mutate the ORM object (which would corrupt in-memory state before
    serialization), we project it into a plain adapter with priority converted to a string.
    """

    def __init__(self, record):
        self.id = record.id
        self.tenant_id = record.tenant_id
        self.priority = _priority_to_string(record.priority)
        self.channel = record.channel
        self.timing = record.timing
        self.summarized_content = record.summarized_content
        self.recipient_filter = record.recipient_filter
```

In the endpoint, replace `deliveries = await routing_svc.route(record, ...)` with:

```python
    routing_record = _MockRoutingRecord(record)
    deliveries = await routing_svc.route(routing_record, tenant_id=current_user.tenant_id)
```

The `isinstance` guard in `_priority_to_string` handles all three input shapes (enum, int, string), and `_MockRoutingRecord` projects the ORM object into the shape `route()` expects.

**Completion check**: `ruff check src/` exits 0.

### Step 3: Add unit tests in `tests/unit/test_notifications.py`

Create the file `tests/unit/test_notifications.py` (the issue specifically requests this path, distinct from `test_notifications_router.py`). Follow the established pattern from `test_notifications_router.py`:

```python
"""Unit tests for POST /notifications/smart endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from api.routers.notifications import notifications_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.channel_delivery import ChannelDelivery
from pkg.errors.app_exceptions import AppException
from tests.unit.conftest import make_mock_session
```

Add a `_MockSmartNotificationModel` class (mirrors the `_MockNotificationModel` pattern, implements `to_dict()` and `__iter__`). Add tests for:

- **Happy path**: valid payload → 200, `notification` key and `deliveries` key present, `NotificationService.create_smart_notification` and `NotificationRoutingService.route` both called with correct args.
- **Validation — missing `summarized_content`**: 422.
- **Validation — invalid `priority`**: 422 (value out of `{0,1,2}` range).
- **Invalid tenant (tenant_id=0)**: 401.
- **Routing returns empty deliveries** (e.g. priority=normal with no user_id): still 200 with empty `deliveries` list.

**Completion check**: `PYTHONPATH=src pytest tests/unit/test_notifications.py -v` → all passed.

### Step 4: Run full lint and unit suite

```bash
ruff check src/ && ruff format --check src/
PYTHONPATH=src pytest tests/unit/ -v
```

All must exit 0.

---

## Test Plan

- **Unit tests in `tests/unit/`**: Create `tests/unit/test_notifications.py` covering the `POST /notifications/smart` endpoint (schema validation, tenant isolation, service call forwarding, routing integration). Uses `patch` on `NotificationService` and `NotificationRoutingService` at the class level, following the established `test_notifications_router.py` pattern.
- **Integration tests in `tests/integration/`**: No new integration test file required — the endpoint uses existing ORM models and services already covered by integration test fixtures. An integration test can be added as a follow-up if desired.
- **Dev-plan verification**: The dev-plan board (§6) has no machine-checkable command beyond the existing `ruff check` and `pytest` suite; the new tests in `test_notifications.py` will be picked up by `PYTHONPATH=src pytest tests/unit/ -v`.

---

## Acceptance Criteria

- `POST /api/v1/notifications/smart` with a valid payload returns `200` with `{"success": true, "data": {"notification": {...}, "deliveries": [...]}, "message": "..."}`
- Pydantic schema rejects missing `summarized_content`, out-of-range `priority`, and out-of-range `channel` with `422`
- `tenant_id=0` returns `401`
- `NotificationRoutingService.route()` is called with the persisted record and `tenant_id`
- `ruff check src/` exits 0
- `PYTHONPATH=src pytest tests/unit/test_notifications.py -v` → all passed
- A `TODO` comment pointing to issue #41 is present in the router or service

---

## Risks / Open Questions

- The `NotificationRoutingService.route()` method reads `getattr(notification, "priority", None)` and expects string values (`"urgent"`, `"normal"`, `"low"`), but `SmartNotificationModel.priority` is an `IntEnum` (values `0`, `1`, `2`). The service will raise `ValidationException` on the integer enum values. **Action needed**: the router or a helper must map the integer `priority` (from the request body) to its string name before passing to `route()`, or `route()` must be updated to handle both. The safest approach is to add a string conversion in the router before calling `route()` (e.g. map `0→"urgent"`, `1→"normal"`, `2→"low"`), keeping the service unchanged and avoiding a breaking change to `route()`.
- `ChannelDelivery` uses `channel: str` but `SmartNotificationModel.channel` is an `IntEnum`. The `getattr` call in `route()` returns the int — the current service code never reads `channel` via `getattr`, only `priority`, so this is not a runtime blocker, but consistency should be reviewed when the LLM integration in #41 is implemented.
