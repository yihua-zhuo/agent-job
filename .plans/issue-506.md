I now have all the context needed to write the implementation plan.

# Implementation Plan — Issue #506

## Goal

Create `src/services/copilot_service.py` with a `CopilotService` class that builds a system prompt from customer/opportunity/activity context, stubs conversation message persistence, and exposes a tool registry with four active tools (`get_customer`, `get_opportunities`, `get_recent_activities`, `get_churn_risk`) and two deferred stubs (`send_email`, `create_task`). Unit tests are added in `tests/unit/test_copilot_service.py`. No API router, no email/task implementation, no message DB write — all deferred.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0506-implement-copilotservice-with-context-building-and-tool-regi.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0506-implement-copilotservice-with-context-building-and-tool-regi.md`

## Affected Files

- `src/services/copilot_service.py` — **新建** `CopilotService` class with `__init__(session: AsyncSession)`, `build_system_prompt`, `persist_message`, `get_tool_registry`, and private helpers `_get_customer`, `_get_opportunities`, `_get_recent_activities`
- `tests/unit/test_copilot_service.py` — **新建** unit tests using `make_mock_session`, `MockState`, and domain handlers from `tests/unit/conftest.py`

## Implementation Steps

### Step 1: Create `src/services/copilot_service.py` skeleton

Create the file with the full class matching the service pattern. Constructor takes `session: AsyncSession` with no default. All public methods accept `tenant_id: int`. Raise `NotFoundException` on missing context. Stub all four public methods with `raise NotImplementedError`.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from pkg.errors.app_exceptions import NotFoundException

class CopilotService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_system_prompt(self, tenant_id: int, customer_id: int) -> str:
        raise NotImplementedError

    async def persist_message(self, tenant_id: int, role: str, content: str) -> None:
        raise NotImplementedError

    def get_tool_registry(self) -> dict[str, dict]:
        raise NotImplementedError
```

**Verification**: `PYTHONPATH=src ruff check src/services/copilot_service.py` → 0 errors; `PYTHONPATH=src python -c "from services.copilot_service import CopilotService; print('import ok')"` → exit 0

---

### Step 2: Implement `build_system_prompt`

Implement `build_system_prompt` by querying `CustomerModel`, `OpportunityModel`, and `ActivityModel` using the existing models (see [`src/db/models/customer.py`](../../src/db/models/customer.py) L1-30, [`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) L1-28, [`src/db/models/activity.py`](../../src/db/models/activity.py) L1-24)). Add three private helpers:

- `_get_customer(tenant_id, customer_id) -> CustomerModel` — raises `NotFoundException("客户")` if not found
- `_get_opportunities(tenant_id, customer_id) -> list[OpportunityModel]` — raw SQL select, filtered by `tenant_id` + `customer_id`
- `_get_recent_activities(tenant_id, customer_id, limit=10) -> list[ActivityModel]` — raw SQL select, filtered by `tenant_id` + `customer_id`, ordered by `created_at DESC`, limit

The prompt string concatenates:
1. Customer name, status, owner_id, tags
2. Each opportunity: name, stage, amount, probability, expected_close_date
3. Last `limit` activities: type, content, created_at

```python
async def build_system_prompt(self, tenant_id: int, customer_id: int) -> str:
    customer = await self._get_customer(tenant_id, customer_id)
    opportunities = await self._get_opportunities(tenant_id, customer_id)
    activities = await self._get_recent_activities(tenant_id, customer_id)
    lines = [f"Customer: {customer.name} | Status: {customer.status} | Owner: {customer.owner_id}"]
    for opp in opportunities:
        lines.append(f"Opportunity: {opp.name} | Stage: {opp.stage} | Amount: {opp.amount} | Prob: {opp.probability}%")
    for act in activities:
        lines.append(f"Activity[{act.type}]: {act.content or ''} at {act.created_at}")
    return "\n".join(lines)
```

The `persist_message` method remains a no-op stub (implemented in Step 3).

**Verification**: `PYTHONPATH=src ruff check src/services/copilot_service.py` → 0 errors

---

### Step 3: Implement `persist_message` stub

Since the message table schema is not yet finalized, implement as a no-op with a docstring:

```python
async def persist_message(self, tenant_id: int, role: str, content: str) -> None:
    """Persist a conversation message. DB write is deferred until the message schema is defined."""
    # TODO: Replace with ConversationMessageModel insert once schema is finalized (issue #505).
    pass
```

**Verification**: `PYTHONPATH=src ruff check src/services/copilot_service.py` → 0 errors

---

### Step 4: Implement `get_tool_registry`

Return a `dict[str, dict]` with 6 entries. Each entry has `{"description": str, "handler": Callable | None, "deferred": bool}`. Four active: `get_customer`, `get_opportunities`, `get_recent_activities`, `get_churn_risk`. Two deferred stubs: `send_email`, `create_task`.

`get_churn_risk` delegates to `ChurnPredictionService.get_churn_prediction(session, customer_id, tenant_id)` — raise `NotFoundException("客户")` if the customer does not exist (handled upstream by `build_system_prompt` caller).

```python
from services.churn_prediction import ChurnPredictionService

def get_tool_registry(self) -> dict[str, dict]:
    return {
        "get_customer": {
            "description": "Retrieve a customer record by customer_id",
            "handler": lambda tenant_id, customer_id: self._get_customer(tenant_id, customer_id),
            "deferred": False,
        },
        "get_opportunities": {
            "description": "List all opportunities for a customer",
            "handler": lambda tenant_id, customer_id: self._get_opportunities(tenant_id, customer_id),
            "deferred": False,
        },
        "get_recent_activities": {
            "description": "List recent activities for a customer",
            "handler": lambda tenant_id, customer_id: self._get_recent_activities(tenant_id, customer_id),
            "deferred": False,
        },
        "get_churn_risk": {
            "description": "Get churn risk prediction for a customer",
            "handler": lambda tenant_id, customer_id: ChurnPredictionService(self.session).get_churn_prediction(customer_id, tenant_id),
            "deferred": False,
        },
        "send_email": {
            "description": "TBD — deferred: email sending tool not yet implemented",
            "handler": None,
            "deferred": True,
        },
        "create_task": {
            "description": "TBD — deferred: task creation tool not yet implemented",
            "handler": None,
            "deferred": True,
        },
    }
```

**Verification**: `PYTHONPATH=src ruff check src/services/copilot_service.py` → 0 errors

---

### Step 5: Write `tests/unit/test_copilot_service.py`

Create the test file using `tests/unit/conftest.py` helpers (`MockState`, `make_mock_session`). Provide at least three tests:

1. **Service instantiates correctly** — fixture `mock_db_session` (empty handlers list), verify `CopilotService(mock_db_session).session is mock_db_session`
2. **`build_system_prompt` raises `NotFoundException` for unknown customer** — use `make_mock_session([])` (no customer handler), call `build_system_prompt(tenant_id=1, customer_id=9999)`, assert `pytest.raises(NotFoundException)`
3. **`get_tool_registry` returns exactly 6 entries** — 4 non-deferred (`get_customer`, `get_opportunities`, `get_recent_activities`, `get_churn_risk`) + 2 deferred (`send_email`, `create_task`); assert `len(registry) == 6` and the deferred/active key sets match

```python
import pytest
from tests.unit.conftest import make_mock_session, MockState
from pkg.errors.app_exceptions import NotFoundException
from services.copilot_service import CopilotService

@pytest.fixture
def mock_db_session():
    return make_mock_session([])

@pytest.fixture
def copilot_service(mock_db_session):
    return CopilotService(mock_db_session)

@pytest.mark.asyncio
async def test_build_system_prompt_raises_not_found(copilot_service):
    with pytest.raises(NotFoundException):
        await copilot_service.build_system_prompt(tenant_id=1, customer_id=9999)

def test_tool_registry_returns_six_tools(copilot_service):
    registry = copilot_service.get_tool_registry()
    assert len(registry) == 6
    active = [k for k, v in registry.items() if not v["deferred"]]
    deferred = [k for k, v in registry.items() if v["deferred"]]
    assert set(active) == {"get_customer", "get_opportunities", "get_recent_activities", "get_churn_risk"}
    assert set(deferred) == {"send_email", "create_task"}

def test_constructor_no_default_session(copilot_service, mock_db_session):
    assert copilot_service.session is mock_db_session
```

**Verification**: `PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v` → 3 passed

---

### Step 6: Full lint check

Run the full lint gate for the new files:
- `PYTHONPATH=src ruff check src/services/copilot_service.py tests/unit/test_copilot_service.py`
- `PYTHONPATH=src ruff format --check src/services/copilot_service.py tests/unit/test_copilot_service.py`

**Verification**: Both commands exit 0.

---

### Step 7: Dev-plan verification

```bash
PYTHONPATH=src ruff check src/services/copilot_service.py tests/unit/test_copilot_service.py
PYTHONPATH=src ruff format --check src/services/copilot_service.py tests/unit/test_copilot_service.py
PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v
```

Expected output: 3 passed, 0 errors/warnings from ruff.

## Test Plan

- Unit tests in `tests/unit/test_copilot_service.py`: 3 tests covering (a) constructor accepts `AsyncSession` with no default, (b) `build_system_prompt` raises `NotFoundException` for unknown customer_id, (c) `get_tool_registry` returns exactly 6 entries with correct deferred/active key sets
- Integration tests in `tests/integration/`: none — this is a pure service with DB reads that follow existing patterns; integration coverage belongs in the router issue (deferred)
- Dev-plan verification: the §6 checklist items above

## Acceptance Criteria

- `src/services/copilot_service.py` exists and `PYTHONPATH=src ruff check src/services/copilot_service.py` exits 0
- `tests/unit/test_copilot_service.py` exists and `PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v` exits 0 with all tests passing
- `CopilotService.__init__` signature is `(self, session: AsyncSession)` with no default parameter
- `build_system_prompt(tenant_id, customer_id)` raises `NotFoundException("客户")` when the customer does not exist for the given `tenant_id`
- `get_tool_registry()` returns a `dict` with exactly 6 keys: `get_customer`, `get_opportunities`, `get_recent_activities`, `get_churn_risk` (all `deferred=False`) and `send_email`, `create_task` (both `deferred=True`)
- `persist_message(tenant_id, role, content)` is a no-op (returns `None`, no side effects)
- All SQL queries include `tenant_id` in their WHERE clause
