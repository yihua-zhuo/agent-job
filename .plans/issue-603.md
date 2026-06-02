Now I have a thorough picture of the codebase. Let me write the plan.

# Implementation Plan — Issue #603

## Goal

Implement `TicketCategorizationService` in `src/services/ticket_categorization_service.py` that fetches a ticket by ID, calls the `AIChatGateway` stub to classify it, and persists a `TicketCategorizationModel` row. The service follows the existing service pattern (session-in-constructor, returns ORM, raises `AppException`). Unit tests mock the LLM call entirely.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/30-tickets/0603-build-ticketcategorizationservice-with-llm-categorization-lo.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/30-tickets/0603-build-ticketcategorizationservice-with-llm-categorization-lo.md`

## Affected Files

- `src/services/ticket_categorization_service.py` — **new** — `TicketCategorizationService` with `categorize_ticket` method
- `tests/unit/domain_handlers/ticket_categorization.py` — **new** — `ticket_categorization_handler` SQL mock factory
- `tests/unit/test_ticket_categorization_service.py` — **new** — unit tests (happy path, not found, unknown category, empty reply)
- `tests/unit/conftest.py` — **modify** — re-export `ticket_categorization_handler` for backward compat import path

## Implementation Steps

### Step 1: Verify `TicketCategorizationModel` schema

The model was written by #602 at `src/db/models/ticket_categorization.py`. Read it and confirm these fields exist (they do):

| Field | Type |
|---|---|
| `id` | `Mapped[int]` (primary key) |
| `tenant_id` | `Mapped[int]` (index=True) |
| `ticket_id` | `Mapped[int]` (FK to `tickets.id`) |
| `category_type` | `Mapped[str]` (String 50, NOT `category`) |
| `confidence` | `Mapped[Decimal \| None]` (Numeric 5,4) |
| `reasons` | `Mapped[dict \| None]` (JSON) |
| `suggested_assignee_id`, `suggested_team`, `priority` | various |
| `human_override` | `Mapped[bool]` |
| `categorized_at` | `Mapped[datetime \| None]` |
| `created_at`, `updated_at` | `Mapped[datetime]` with server_default |

**Note**: The model uses `category_type` (not `category`) and `reasons: dict` (not `reasoning: str`). The service must use the actual field names.

Run: `PYTHONPATH=src ruff check src/db/models/ticket_categorization.py` → 0 errors.

---

### Step 2: Add `ticket_categorization_handler` to domain handlers

Create `tests/unit/domain_handlers/ticket_categorization.py`. Unlike the dev-plan's inline approach, follow the established pattern of a domain-owned handler module (like `tickets.py`, `sla.py`).

The handler stores rows in `state.opaque["ticket_categorizations"]` (the idiomatic slot for domain-specific state in `MockState`). It handles:

- `select` by `id` (returns one row), by `ticket_id+tenant_id` (returns one row), and count
- `insert into ticket_categorizations` — auto-increment ID, assign `created_at`/`updated_at`

```python
# tests/unit/domain_handlers/ticket_categorization.py
from __future__ import annotations
from datetime import UTC, datetime
from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 55


def make_ticket_categorization_handler(state: MockState) -> callable:
    state.opaque.setdefault("ticket_categorizations", [])

    def handler(sql_text, params):
        if "insert into ticket_categorizations" in sql_text:
            rows = state.opaque["ticket_categorizations"]
            new_id = len(rows) + 1
            now = datetime.now(UTC)
            row = {
                "id": new_id,
                "tenant_id": params.get("tenant_id"),
                "ticket_id": params.get("ticket_id"),
                "category_type": params.get("category_type", "uncategorized"),
                "priority": params.get("priority"),
                "confidence": params.get("confidence"),
                "reasons": params.get("reasons"),
                "suggested_assignee_id": params.get("suggested_assignee_id"),
                "suggested_team": params.get("suggested_team"),
                "human_override": params.get("human_override", False),
                "categorized_at": params.get("categorized_at"),
                "created_at": now,
                "updated_at": now,
            }
            rows.append(row)
            return MockResult([MockRow({"id": new_id})])

        if "from ticket_categorizations" in sql_text:
            rows = state.opaque["ticket_categorizations"]
            # filter by id or ticket_id+tenant_id
            for row in rows:
                if params.get("id") and row["id"] == params["id"]:
                    return MockResult([MockRow(row)])
                if (
                    params.get("ticket_id") == row["ticket_id"]
                    and params.get("tenant_id") == row["tenant_id"]
                ):
                    return MockResult([MockRow(row)])
            return MockResult([])

        return None

    return handler


def get_handlers(state: MockState):
    return [make_ticket_categorization_handler(state)]


__all__ = ["get_handlers", "make_ticket_categorization_handler"]
```

Re-export from `tests/unit/conftest.py`:

```python
from tests.unit.domain_handlers.ticket_categorization import make_ticket_categorization_handler  # noqa: F401, E402
```

**完成判定**: `PYTHONPATH=src ruff check tests/unit/domain_handlers/ticket_categorization.py tests/unit/conftest.py` → 0 errors.

---

### Step 3: Write `TicketCategorizationService`

Create `src/services/ticket_categorization_service.py`. Key deviations from the dev-plan's sample code:

1. **Field name `category_type`**, not `category`
2. **`confidence: Decimal`** — cast `float` from `_parse_category_from_reply` to `Decimal`
3. **`reasons: dict`** — store the raw LLM reply under `{"reasoning": <reply>}` rather than a string `reasoning` field
4. **`human_override=False`** on every new categorization
5. **`categorized_at` set to `datetime.now(UTC)`**

```python
# src/services/ticket_categorization_service.py
"""Ticket categorization service — LLM-based classification."""
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.ticket_categorization import TicketCategorizationModel
from db.models.ticket import TicketModel
from internal.ai_gateway import AIChatGateway, AIResponse
from pkg.errors.app_exceptions import NotFoundException, ValidationException

_CATEGORY_KEYWORDS = {
    "billing": ["billing", "invoice", "payment", "charge", "refund"],
    "technical": ["technical", "bug", "error", "crash", "not working", "broken"],
    "sales": ["sales", "pricing", "quote", "demo", "purchase"],
    "feature_request": ["feature", "request", "suggest", "improve", "would like"],
    "account": ["account", "login", "password", "access", "permission"],
    "general": ["general", "other", "question", "inquiry"],
}
_DEFAULT_CATEGORY = "uncategorized"
_DEFAULT_CONFIDENCE = 0.5


def _parse_category_from_reply(reply: str) -> tuple[str, float]:
    reply_lower = reply.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in reply_lower for kw in keywords):
            return category, 0.85
    return _DEFAULT_CATEGORY, _DEFAULT_CONFIDENCE


class TicketCategorizationService:
    def __init__(self, session: AsyncSession, gateway: AIChatGateway | None = None):
        if session is None:
            raise TypeError("session is required, no default")
        self.session = session
        self.gateway = gateway or AIChatGateway()

    async def categorize_ticket(self, ticket_id: int, tenant_id: int) -> TicketCategorizationModel:
        from sqlalchemy import and_
        from sqlalchemy import select
        from datetime import UTC

        # Fetch + verify ticket
        result = await self.session.execute(
            select(TicketModel).where(
                and_(TicketModel.id == ticket_id, TicketModel.tenant_id == tenant_id)
            )
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise NotFoundException("Ticket")

        # Build LLM prompt
        subject = ticket.subject or ""
        description = ticket.description or ""
        prompt = (
            "Classify this support ticket. Respond with only the category name "
            "(billing, technical, sales, feature_request, account, or general).\n\n"
            f"Subject: {subject}\nDescription: {description}"
        )

        # Call AI gateway
        ai_response: AIResponse = await self.gateway.chat(
            messages=[{"role": "user", "content": prompt}],
            context={},
        )

        if not ai_response.reply or not ai_response.reply.strip():
            raise ValidationException("AI gateway returned empty response")

        category, confidence = _parse_category_from_reply(ai_response.reply)

        from datetime import datetime
        now = datetime.now(UTC)
        record = TicketCategorizationModel(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            category_type=category,
            confidence=Decimal(str(confidence)),
            reasons={"reasoning": ai_response.reply[:500]} if ai_response.reply else None,
            human_override=False,
            categorized_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record
```

**完成判定**: `PYTHONPATH=src ruff check src/services/ticket_categorization_service.py` → 0 errors.

---

### Step 4: Write unit tests

Create `tests/unit/test_ticket_categorization_service.py`. Use `make_mock_session` with both `make_ticket_handler(state)` and `make_ticket_categorization_handler(state)`. Seed `state.opaque["ticket_categorizations"]` with at least one pre-seeded ticket (id=10, tenant_id=1).

Four test cases (dev-plan says ≥3, we cover 4):

1. **Happy path** — mock gateway returns `"technical — the login page crashes"`; assert `category_type == "technical"`, `confidence == Decimal("0.85")`
2. **Ticket not found** — call with `ticket_id=9999`; assert `pytest.raises(NotFoundException)`
3. **Unknown category** — mock gateway returns `"please contact support"` (no known keyword); assert `category_type == "uncategorized"`, `confidence == Decimal("0.5")`
4. **Empty AI reply** — mock gateway returns `AIResponse(reply="")`; assert `pytest.raises(ValidationException)`

```python
# tests/unit/test_ticket_categorization_service.py
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock
from datetime import UTC, datetime

from tests.unit.conftest import make_mock_session, MockState
from tests.unit.domain_handlers.ticket_categorization import make_ticket_categorization_handler
from tests.unit.domain_handlers.tickets import make_ticket_handler
from src.services.ticket_categorization_service import TicketCategorizationService
from src.internal.ai_gateway import AIResponse
from src.pkg.errors.app_exceptions import NotFoundException, ValidationException


@pytest.fixture
def mock_state():
    state = MockState()
    state._tickets = [
        {"id": 10, "tenant_id": 1, "subject": "Login broken", "description": "Cannot log in", "status": "open", "priority": "medium", "customer_id": 1, "assignee_id": None, "created_at": None, "updated_at": None},
    ]
    return state


@pytest.fixture
def mock_db_session(mock_state):
    return make_mock_session([
        make_ticket_handler(mock_state),
        make_ticket_categorization_handler(mock_state),
    ], state=mock_state)


@pytest.fixture
def mock_gateway():
    return AsyncMock()


@pytest.fixture
def service(mock_db_session, mock_gateway):
    return TicketCategorizationService(mock_db_session, mock_gateway)


class TestCategorizeTicket:
    async def test_happy_path_parses_technical(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="technical — the login page crashes", suggestions=[], actions=[])
        result = await service.categorize_ticket(ticket_id=10, tenant_id=1)
        assert result.category_type == "technical"
        assert result.confidence == Decimal("0.85")
        assert result.ticket_id == 10
        assert result.tenant_id == 1

    async def test_not_found_raises(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="billing", suggestions=[], actions=[])
        with pytest.raises(NotFoundException):
            await service.categorize_ticket(ticket_id=9999, tenant_id=1)

    async def test_unknown_category_falls_back_to_uncategorized(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="please contact support", suggestions=[], actions=[])
        result = await service.categorize_ticket(ticket_id=10, tenant_id=1)
        assert result.category_type == "uncategorized"
        assert result.confidence == Decimal("0.5")

    async def test_empty_reply_raises_validation(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="", suggestions=[], actions=[])
        with pytest.raises(ValidationException):
            await service.categorize_ticket(ticket_id=10, tenant_id=1)
```

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_service.py -v` → `4 passed`.

---

## Test Plan

- **Unit tests**: `tests/unit/test_ticket_categorization_service.py` — 4 cases covering happy path, not-found, unknown category, empty reply; all use `AsyncMock` for `AIChatGateway` with no real AI call
- **Integration tests**: none — the router isn't part of this step, and the service has no DB persistence path that integration tests would add value on beyond unit coverage
- **Dev-plan verification** (§6 commands run in order):
  - `PYTHONPATH=src ruff check src/services/ticket_categorization_service.py` → 0 errors
  - `PYTHONPATH=src ruff check src/db/models/ticket_categorization.py` → 0 errors
  - `PYTHONPATH=src ruff check tests/unit/test_ticket_categorization_service.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_service.py -v` → `4 passed`
  - `PYTHONPATH=src ruff format --check src/services/ticket_categorization_service.py src/db/models/ticket_categorization.py tests/unit/test_ticket_categorization_service.py` → all pass

---

## Acceptance Criteria

- `TicketCategorizationService` constructor rejects `session=None` with `TypeError`
- `categorize_ticket(ticket_id=9999, tenant_id=1)` raises `NotFoundException` when ticket doesn't exist
- `categorize_ticket(ticket_id=10, tenant_id=1)` with gateway returning `"billing inquiry"` sets `category_type == "billing"` and `confidence == Decimal("0.85")`
- `categorize_ticket(ticket_id=10, tenant_id=1)` with gateway returning `"no match here"` sets `category_type == "uncategorized"` and `confidence == Decimal("0.5")`
- `categorize_ticket` with gateway returning empty string raises `ValidationException`
- No `.to_dict()` calls in the service body
- `ruff check` on all new/modified files returns 0 errors

---

## Risks / Open Questions

- **`Decimal` precision for confidence**: the model stores `Numeric(5, 4)` which allows values up to `9.9999`. The service casts `0.85` → `Decimal("0.85")` which fits. If confidence ever exceeds `9.9999`, the DB insert would raise. Low risk for this step.
- **`AIChatGateway` constructor takes no args**: the `gateway or AIChatGateway()` fallback is safe. Confirm the real integration (once #41 lands) will also have a no-arg constructor. Currently stub-only.
- **`state.opaque` vs `state._ticket_categorizations`**: the dev-plan suggested a `_ticket_categorizations` attribute directly on `MockState`. `MockState` has no such attribute; the idiomatic slot is `state.opaque["ticket_categorizations"]` which is already used by other handlers (e.g. `sla.py`). This is a deviation from the dev-plan sample code but aligns with existing patterns.
