# 票据分类服务 · Build TicketCategorizationService with LLM categorization

| 元数据 | 值 |
|---|---|
| Issue | #603 |
| 分类 | [30-tickets](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [#602 AI Agent Framework](../30-tickets/0602-add-ticket-categorization-sqlalchemy-orm-model-and-db-migrat.md), TBD - 待验证：parent epic #45 |
| 启用后赋能 | Router for ticket categorization endpoint (future issue, TBD) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The ticket domain currently has no mechanism to automatically classify tickets by intent/category. Agents must manually tag every inbound ticket, which is slow and inconsistent. Issue #602 creates the storage model (`TicketCategorizationModel`); this service adds the orchestration layer that fetches the ticket, calls the AI agent framework, and persists the classification result. The work is gated on #602 because this service depends on the model existing.

### 1.2 做完后

- **用户视角**: No direct user-facing change in this step — this is a pure backend service that will be consumed by a future router.
- **开发者视角**: A new `TicketCategorizationService` class that accepts a `ticket_id` and `tenant_id`, runs LLM-based categorization, and returns a `TicketCategorizationModel` ORM object. Unit tests mock the LLM call so the service logic is fully exercisable without a real AI backend.

### 1.3 不做什么（剔除）

- [ ] Router / HTTP endpoint for categorization — that goes in a follow-up issue.
- [ ] Multi-label categorization or sub-category hierarchy — single top-level category per ticket.
- [ ] Integration with the full AI agent framework beyond the `AIChatGateway` interface stub already in `src/internal/ai_gateway.py`.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_service.py -v` → ≥ 6 passed
- `ruff check src/services/ticket_categorization_service.py` → 0 errors
- `ruff check src/db/models/ticket_categorization.py` → 0 errors
- `ruff format --check src/services/ticket_categorization_service.py src/db/models/ticket_categorization.py` → all pass

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块. `TicketCategorizationService` does not exist yet; the `TicketModel` at [`src/db/models/ticket.py`](../../../src/db/models/ticket.py) L11-L59 holds ticket data but has no categorization field. The `AIChatGateway` stub at [`src/internal/ai_gateway.py`](../../../src/internal/ai_gateway.py) L1-L87 is the AI call interface. Existing `TicketService` at [`src/services/ticket_service.py`](../../../src/services/ticket_service.py) L1-L459 shows the service pattern to follow.

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/conftest.py` — add `ticket_categorization_handler` factory for unit tests
- 要建：
  - `src/services/ticket_categorization_service.py` — the new service
  - `src/db/models/ticket_categorization.py` — the new ORM model (produced by #602, verified here)
  - `tests/unit/test_ticket_categorization_service.py` — unit tests with mocked LLM

### 2.3 缺什么

- [ ] `TicketCategorizationService` class — constructor takes `AsyncSession` (no default), exposes `categorize_ticket(ticket_id, tenant_id)` returning `TicketCategorizationModel`
- [ ] `TicketCategorizationModel` ORM model — must have `tenant_id` column with index, must be importable in `alembic/env.py`
- [ ] Unit test mock for `AIChatGateway.chat()` — deterministic mock returning a canned category string
- [ ] `ticket_categorization_handler` in `tests/unit/conftest.py` — SQL mock handler so unit tests don't hit a real DB

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/ticket_categorization_service.py` | `TicketCategorizationService` with `categorize_ticket` method |
| `tests/unit/test_ticket_categorization_service.py` | Unit tests: happy path, ticket not found, LLM returns unknown category |
| `src/db/models/ticket_categorization.py` | `TicketCategorizationModel` ORM (model written by #602, imported here) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) | Add `ticket_categorization_handler(state)` factory + `make_ticket_categorization_handler(state)` |
| [`src/db/models/ticket.py`](../../../src/db/models/ticket.py) | No changes — model already exists; this doc verifies it is the right base |
| [`src/services/ticket_service.py`](../../../src/services/ticket_service.py) | No changes — categorization is a separate service |

### 3.3 新增能力

- **Service class**: `TicketCategorizationService(session: AsyncSession)` — no default session
- **Service method**: `categorize_ticket(self, ticket_id: int, tenant_id: int) -> TicketCategorizationModel`
  - Fetches `TicketModel` by ID (raises `NotFoundException` if missing or wrong tenant)
  - Calls `AIChatGateway.chat()` with a prompt built from ticket subject + description
  - Parses the category from the `AIResponse.reply` string
  - Persists a new `TicketCategorizationModel` row and returns it
- **ORM model**: `TicketCategorizationModel` in `src/db/models/ticket_categorization.py` — fields: `id`, `tenant_id`, `ticket_id`, `category`, `confidence`, `reasoning`, `created_at`
- **Mock**: `MockAIChatGateway` in unit tests — returns deterministic canned responses

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Mock the AI call in unit tests rather than use a test container** — `AIChatGateway` is already a stub with deterministic output; injecting a `gateway: AIChatGateway` constructor argument lets tests pass `MagicMock()` / `AsyncMock()` without any external dependency.
- **Single top-level category string, not enum** — ticket domains vary widely; storing a free-form `category: str` column keeps the model flexible. A future migration can add a `ticket_categories` lookup table if needed.

### 4.2 版本约束

No new runtime dependencies introduced by this board. `AIChatGateway` is already in `src/internal/ai_gateway.py`; `TicketCategorizationModel` is produced by #602.

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` (see CLAUDE.md §Multi-Tenancy).
- Service returns ORM objects, **never** calls `.to_dict()` — serialization is the router's job (no router in this step, but the service must still follow the contract).
- Service raises `AppException` subclasses — `NotFoundException` if ticket not found, `ValidationException` if LLM response is unparseable.
- Constructor signature: `def __init__(self, session: AsyncSession)` — no `None` default, no optional gateway kwarg that defaults to None internally without being declared.

### 4.4 已知坑

1. **`AIChatGateway` returns a free-form string, not structured JSON** → Current stub returns natural-language replies. The service must parse the reply by looking for known category keywords (e.g. `billing`, `technical`, `sales`) using a simple substring match; if none match, fall back to `"uncategorized"`. This keeps the implementation stable without a full JSON schema contract.
2. **Double flush risk** → Both `TicketService` and `TicketCategorizationService` may call `session.flush()` in the same request-scoped session. Ensure the categorization service flushes after insert so the caller can `session.refresh()` without a separate flush call.

---

## 5. 实现步骤（按顺序）

### Step 1: Verify `TicketCategorizationModel` exists and review its schema

Read `src/db/models/ticket_categorization.py` (produced by #602). Confirm it has:
- `tenant_id: Mapped[int]` with `index=True`
- `ticket_id: Mapped[int]` (FK to `tickets.id`)
- `category: Mapped[str]`
- `confidence: Mapped[float | None]`
- `reasoning: Mapped[str | None]`
- `created_at: Mapped[datetime]`

If the file does not exist yet, write the model as part of this step (it was #602's deliverable but may not be landed yet). Pattern:

```python
# src/db/models/ticket_categorization.py
from datetime import UTC, datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class TicketCategorizationModel(Base):
    __tablename__ = "ticket_categorizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="uncategorized")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "ticket_id": self.ticket_id,
            "category": self.category,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**: `PYTHONPATH=src ruff check src/db/models/ticket_categorization.py` → 0 errors

---

### Step 2: Add `ticket_categorization_handler` to `tests/unit/conftest.py`

Add a new handler factory `make_ticket_categorization_handler(state: MockState)` in `tests/unit/conftest.py`. The handler must:
- Track inserted `TicketCategorizationModel` rows in `state._ticket_categorizations` list
- Handle `select` by `id`, by `ticket_id+tenant_id`, and count queries
- Handle `INSERT` by appending a new row with an auto-incremented `id`

Example snippet:

```python
def make_ticket_categorization_handler(state: MockState) -> dict:
    """SQL mock for ticket_categorizations table."""
    def handle(method, table, conditions, returning=None, values=None):
        if method == "select":
            # filter by id or ticket_id+tenant_id
            ...
        if method == "insert":
            new_id = len(state._ticket_categorizations) + 1
            row = {"id": new_id, "tenant_id": values["tenant_id"], "ticket_id": values["ticket_id"],
                   "category": values.get("category", "uncategorized"),
                   "confidence": values.get("confidence"), "reasoning": values.get("reasoning"),
                   "created_at": datetime.now(UTC)}
            state._ticket_categorizations.append(row)
            return {"id": new_id}
    return {"ticket_categorizations": handle}
```

Add the handler to the list returned by `make_mock_session` for any test that needs it.

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_service.py -v` → all passed / `ruff check tests/unit/conftest.py` → 0 errors

---

### Step 3: Write `TicketCategorizationService` in `src/services/ticket_categorization_service.py`

Implement the service class:

```python
# src/services/ticket_categorization_service.py
"""Ticket categorization service — LLM-based classification."""

from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.ticket import TicketModel
from db.models.ticket_categorization import TicketCategorizationModel
from internal.ai_gateway import AIChatGateway, AIResponse
from pkg.errors.app_exceptions import NotFoundException, ValidationException

# Known category keywords extracted from AI reply
_CATEGORY_KEYWORDS = {
    "billing": ["billing", "invoice", "payment", "charge", "refund"],
    "technical": ["technical", "bug", "error", "crash", "not working", "broken"],
    "sales": ["sales", "pricing", "quote", "demo", "purchase"],
    "feature_request": ["feature", "request", "suggest", "improve", "would like"],
    "account": ["account", "login", "password", "access", "permission"],
    "general": ["general", "other", "question", "inquiry"],
}

_DEFAULT_CATEGORY = "uncategorized"


def _parse_category_from_reply(reply: str) -> tuple[str, float]:
    """Extract category string and confidence from AI reply text.

    Returns (category, confidence) where confidence is 0.0–1.0.
    """
    reply_lower = reply.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in reply_lower:
                return category, 0.85
    return _DEFAULT_CATEGORY, 0.5


class TicketCategorizationService:
    def __init__(self, session: AsyncSession, gateway: AIChatGateway | None = None):
        """Initialize service.

        Args:
            session: SQLAlchemy async session (required, no default).
            gateway: AI gateway instance (defaults to AIChatGateway()).
        """
        self.session = session
        self.gateway = gateway or AIChatGateway()

    async def categorize_ticket(self, ticket_id: int, tenant_id: int) -> TicketCategorizationModel:
        """Classify a ticket using the LLM and persist the result.

        Fetches the ticket (raises NotFoundException if missing or wrong tenant),
        builds a prompt from subject + description, calls the AI gateway, parses
        the category, and persists a new TicketCategorizationModel row.

        Args:
            ticket_id: Primary key of the ticket to categorize.
            tenant_id: Tenant context.

        Returns:
            The newly created TicketCategorizationModel (persisted and refreshed).

        Raises:
            NotFoundException: Ticket does not exist or belongs to another tenant.
            ValidationException: AI response could not be parsed to a category string.
        """
        # Fetch ticket, verify tenant
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
            f"Classify this support ticket. Respond with only the category name "
            f"(billing, technical, sales, feature_request, account, or general).\n\n"
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

        now = datetime.now(UTC)
        record = TicketCategorizationModel(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            category=category,
            confidence=confidence,
            reasoning=ai_response.reply[:500] if ai_response.reply else None,
            created_at=now,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record
```

**完成判定**: `PYTHONPATH=src ruff check src/services/ticket_categorization_service.py` → 0 errors

---

### Step 4: Write unit tests in `tests/unit/test_ticket_categorization_service.py`

At minimum, cover these 3 cases using `make_mock_session` with `ticket_categorization_handler` and `ticket_handler`:

1. **Happy path** — mock `AIChatGateway` returns `"technical"` in the reply; assert returned `category == "technical"` and `confidence == 0.85`
2. **Ticket not found** — call `categorize_ticket(9999, tenant_id=1)`; assert `pytest.raises(NotFoundException)`
3. **Unknown category** — mock `AIChatGateway` returns `"please contact support"` (no known keyword); assert returned `category == "uncategorized"` and `confidence == 0.5`

```python
# tests/unit/test_ticket_categorization_service.py
import pytest
from unittest.mock import AsyncMock
from datetime import UTC, datetime

from tests.unit.conftest import make_mock_session, make_ticket_categorization_handler, make_ticket_handler, MockState
from src.services.ticket_categorization_service import TicketCategorizationService
from src.internal.ai_gateway import AIResponse
from src.pkg.errors.app_exceptions import NotFoundException


@pytest.fixture
def mock_db_session():
    state = MockState()
    state._tickets = [
        {"id": 10, "tenant_id": 1, "subject": "Login broken", "description": "Cannot log in", "status": "open"},
    ]
    return make_mock_session([make_ticket_handler(state), make_ticket_categorization_handler(state)])


@pytest.fixture
def mock_gateway():
    gw = AsyncMock()
    return gw


@pytest.fixture
def service(mock_db_session, mock_gateway):
    return TicketCategorizationService(mock_db_session, mock_gateway)


class TestCategorizeTicket:
    async def test_happy_path_parses_technical(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="technical — the login page crashes on load", suggestions=[], actions=[])
        result = await service.categorize_ticket(ticket_id=10, tenant_id=1)
        assert result.category == "technical"
        assert result.confidence == 0.85
        assert result.ticket_id == 10
        assert result.tenant_id == 1

    async def test_not_found_raises(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="billing", suggestions=[], actions=[])
        with pytest.raises(NotFoundException):
            await service.categorize_ticket(ticket_id=9999, tenant_id=1)

    async def test_unknown_category_falls_back_to_uncategorized(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="I am not sure how to answer that", suggestions=[], actions=[])
        result = await service.categorize_ticket(ticket_id=10, tenant_id=1)
        assert result.category == "uncategorized"
        assert result.confidence == 0.5

    async def test_empty_ai_reply_raises_validation(self, service, mock_gateway):
        mock_gateway.chat.return_value = AIResponse(reply="", suggestions=[], actions=[])
        from src.pkg.errors.app_exceptions import ValidationException
        with pytest.raises(ValidationException):
            await service.categorize_ticket(ticket_id=10, tenant_id=1)
```

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_service.py -v` → `4 passed`

---

## 6. 验收

- [ ] `ruff check src/services/ticket_categorization_service.py` → 0 errors
- [ ] `ruff check src/db/models/ticket_categorization.py` → 0 errors
- [ ] `ruff check tests/unit/test_ticket_categorization_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_service.py -v` → `4 passed`
- [ ] `PYTHONPATH=src ruff format --check src/services/ticket_categorization_service.py src/db/models/ticket_categorization.py tests/unit/test_ticket_categorization_service.py` → all pass

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#602` not landed before this work starts — `TicketCategorizationModel` doesn't exist | 中 | 高 | Import `TicketCategorizationModel` from `src.db.models.ticket_categorization` in Step 1; if the module doesn't exist yet, write the model inline and note that it must be aligned with #602's schema once merged |
| LLM prompt produces unstable categories across runs (non-deterministic gateway) | 低 | 中 | `_parse_category_from_reply` uses keyword matching on the reply string; deterministic stub in tests ensures stable unit coverage; production instability handled by falling back to `"uncategorized"` |
| `session.flush()` in service conflicts with outer transaction in integration tests | 低 | 中 | `TicketCategorizationService.categorize_ticket` flushes and refreshes; if outer code rolls back, the categorization row is rolled back too — no orphan rows |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/ticket_categorization_service.py
git add src/db/models/ticket_categorization.py
git add tests/unit/test_ticket_categorization_service.py
git add tests/unit/conftest.py
git commit -m "feat(tickets): add TicketCategorizationService with LLM categorization logic"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(tickets): TicketCategorizationService (#603)" --body "Closes #603"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/ticket_service.py`](../../../src/services/ticket_service.py) — service pattern (constructor with `AsyncSession`, `_fetch` helper, returns ORM object, raises `NotFoundException`)
- 同类参考实现：[`src/services/ai_service.py`](../../../src/services/ai_service.py) — `AIChatGateway` injection pattern
- 同类参考实现：[`src/internal/ai_gateway.py`](../../../src/internal/ai_gateway.py) — `AIResponse` dataclass and `AIChatGateway.chat()` interface
- 第三方文档：[AIChatGateway stub pattern](https://docs.sqlalchemy.org/en/20/orm/quickstart.html) — SQLAlchemy async ORM patterns
- 父 issue / 关联：TBD - 待验证：parent epic #45 (predecessor), #602 (predecessor — `TicketCategorizationModel`)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
