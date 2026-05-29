# 通知路由服务 · 实现基于规则的多渠道通知分发

| 元数据 | 值 |
|---|---|
| Issue | #594 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [#593](../30-tickets/0593-implement-smart-notification-model.md) |
| 启用后赋能 | [通知投递服务](), [数据分析模块]() |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The SmartNotification model (#593) provides a structured record describing each notification event with priority and metadata. Without a routing service, the notification pipeline has no mechanism to determine *which delivery channels* a given notification should use — a hard requirement before any delivery engine can send anything. This gap blocks all downstream notification work.

### 1.2 做完后

- **用户视角**: 无用户-visible changes — this is a pure-backend service that powers future notification delivery.
- **开发者视角**: Other services can call `NotificationRoutingService.route(notification: SmartNotification, tenant_id: int)` and receive a list of `ChannelDelivery` records to pass to a delivery handler. The routing logic is centralized and testable.

### 1.3 不做什么（剔除）

- [ ] Do NOT call any LLM — routing is rule-based only (urgent/normal/low dispatch).
- [ ] Do NOT implement delivery itself (sending email, persisting in-app notification). This service returns delivery *intent* records; a separate delivery service handles actual dispatch.
- [ ] Do NOT implement batching logic — low-priority records are marked for batch; a separate scheduler handles grouping.
- [ ] Do NOT handle retry or backoff logic; that belongs in the delivery layer.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_notification_routing.py -v` → 6+ passed
- `ruff check src/services/notification_routing_service.py` → 0 errors
- `ruff check tests/unit/test_notification_routing.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

> SmartNotification model is being introduced in #593. This service depends on that model existing. Until #593 is merged, the unit tests will mock the SmartNotification record. Once #593 lands, the mock can be replaced with a real model import.

### 2.2 涉及文件清单

- 要改：
  - `src/services/notification_routing_service.py` — new file; routing logic
- 要建：
  - `src/services/notification_routing_service.py` — NotificationRoutingService class
  - `src/models/channel_delivery.py` — ChannelDelivery dataclass/Pydantic model (return type)
  - `tests/unit/test_notification_routing.py` — unit tests using mock session pattern
  - `tests/unit/conftest.py` — add handler(s) for ChannelDelivery if needed

### 2.3 缺什么

- [ ] No `NotificationRoutingService` — no rule-based routing for SmartNotification records
- [ ] No `ChannelDelivery` model/dataclass — the return type for routing decisions
- [ ] No unit tests for routing logic (urgent → in-app + email, normal → in-app, low → batch)
- [ ] No mock fixtures for SmartNotification or ChannelDelivery in the unit test harness

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/notification_routing_service.py` | NotificationRoutingService with rule-based routing |
| `src/models/channel_delivery.py` | ChannelDelivery dataclass (channel, status, record_id) |
| `tests/unit/test_notification_routing.py` | Unit tests with mock session pattern |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/conftest.py` | Add mock handler for SmartNotification queries (if not present from #593) |

### 3.3 新增能力

- **Service class**: `NotificationRoutingService(session: AsyncSession)` — takes session, no default
- **Service method**: `NotificationRoutingService.route(self, notification: SmartNotification, tenant_id: int) -> list[ChannelDelivery]`
- **Pydantic model**: `ChannelDelivery` with fields `channel: str`, `target: str`, `priority: str`, `status: str`
- **Routing rules** (rule-based, no LLM):
  - `urgent` → in-app + email
  - `normal` → in-app only
  - `low` → batch (daily digest)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Return dataclass over ORM model** — ChannelDelivery is a routing decision record, not a database entity. Using a Pydantic dataclass avoids coupling to the DB layer and keeps the service output serializable without a round-trip.
- **Rule-based over LLM** — per issue requirement: routing uses priority enum matching, no LLM call. This keeps routing synchronous, fast, and testable.
- **No batch processing in this service** — low-priority records are tagged `batch`; a separate scheduler service (not in this scope) will read batch-tagged records and group them into a daily digest.

### 4.2 版本约束

> No new external dependencies. Uses only existing `SmartNotification` model from #593 and Python stdlib.

### 4.3 兼容性约束

- Multi-tenant: `tenant_id` must be accepted by the service and used for any future DB reads (even though routing is currently stateless — the signature must be compatible for multi-tenant context propagation).
- Service accepts `session: AsyncSession` with **no default** — follow the service pattern from CLAUDE.md.
- Service returns domain objects (`list[ChannelDelivery]` dataclass), **does not** call `.to_dict()`.
- Service raises `AppException` subclasses on errors (e.g. `ValidationException` if priority is unrecognized), **does not** return `ApiResponse`.
- Session is injected via `Depends(get_db)` in any router that calls this service; do NOT use `async with get_db() as session:`.

### 4.4 已知坑

1. **SmartNotification model not yet merged** — until #593 lands, unit tests must mock `SmartNotification` as a plain dataclass (not an ORM model). Write the mock to be drop-in replaceable once the ORM model exists.
2. **SQLAlchemy Base column named `metadata` collision** — if ChannelDelivery model or any future ORM version of it lands in `src/db/models/`, the column must NOT be named `metadata`. Use `event_metadata`, `payload`, or `attrs` instead.

---

## 5. 实现步骤（按顺序）

### Step 1: Create ChannelDelivery model

Create `src/models/channel_delivery.py` with a Pydantic dataclass representing a single routing decision.

```python
from pydantic import BaseModel, Field


class ChannelDelivery(BaseModel):
    """Represents a single routing decision — which channel to deliver a notification on."""

    channel: str = Field(description="Delivery channel: in_app | email | batch")
    target: str = Field(description="Recipient address: user_id for in_app, email addr for email, 'daily_digest' for batch")
    priority: str = Field(description="Original notification priority: urgent | normal | low")
    status: str = Field(default="pending", description="Routing status: pending | routed")
    tenant_id: int = Field(description="Tenant for multi-tenant isolation")
```

**完成判定**: `ruff check src/models/channel_delivery.py` → 0 errors

---

### Step 2: Implement NotificationRoutingService

Create `src/services/notification_routing_service.py` with the routing class and rule-based logic.

```python
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.channel_delivery import ChannelDelivery
from pkg.errors.app_exceptions import ValidationException


class NotificationRoutingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def route(
        self,
        notification: Any,  # SmartNotification from #593; mock-able before merge
        tenant_id: int,
    ) -> list[ChannelDelivery]:
        """
        Apply rule-based routing for a SmartNotification record.

        Rules:
          urgent  -> in_app + email
          normal  -> in_app only
          low     -> batch (daily digest)

        Returns a list of ChannelDelivery records, one per channel decision.
        """
        priority = getattr(notification, "priority", None)
        user_id = getattr(notification, "user_id", None)
        email = getattr(notification, "email", None)

        if priority not in ("urgent", "normal", "low"):
            raise ValidationException(f"Unknown notification priority: {priority}")

        records: list[ChannelDelivery] = []

        if priority == "urgent":
            if user_id is not None:
                records.append(ChannelDelivery(
                    channel="in_app",
                    target=str(user_id),
                    priority=priority,
                    status="routed",
                    tenant_id=tenant_id,
                ))
            if email is not None:
                records.append(ChannelDelivery(
                    channel="email",
                    target=str(email),
                    priority=priority,
                    status="routed",
                    tenant_id=tenant_id,
                ))
        elif priority == "normal":
            if user_id is not None:
                records.append(ChannelDelivery(
                    channel="in_app",
                    target=str(user_id),
                    priority=priority,
                    status="routed",
                    tenant_id=tenant_id,
                ))
        elif priority == "low":
            records.append(ChannelDelivery(
                channel="batch",
                target="daily_digest",
                priority=priority,
                status="pending",
                tenant_id=tenant_id,
            ))

        return records
```

**完成判定**: `ruff check src/services/notification_routing_service.py` → 0 errors

---

### Step 3: Add unit tests with mock session pattern

Create `tests/unit/test_notification_routing.py` with tests for all three routing paths plus the error case.

Tests must use `make_mock_session` from `tests/unit/conftest.py` with a handler that returns the mocked SmartNotification record. At this stage (before #593), mock SmartNotification as a simple object with attributes (`priority`, `user_id`, `email`).

```python
# tests/unit/test_notification_routing.py
from unittest.mock import MagicMock
import pytest

from tests.unit.conftest import make_mock_session, MockState
from src.services.notification_routing_service import NotificationRoutingService


def _mock_notification(priority: str, user_id: int = 42, email: str = "user@example.com"):
    n = MagicMock()
    n.priority = priority
    n.user_id = user_id
    n.email = email
    return n


class TestNotificationRoutingService:
    @pytest.fixture
    def mock_db_session(self):
        return make_mock_session([])

    @pytest.fixture
    def svc(self, mock_db_session):
        return NotificationRoutingService(mock_db_session)

    async def test_urgent_routes_to_in_app_and_email(self, svc):
        notif = _mock_notification("urgent")
        result = await svc.route(notif, tenant_id=1)
        assert len(result) == 2
        channels = {r.channel for r in result}
        assert channels == {"in_app", "email"}

    async def test_normal_routes_to_in_app_only(self, svc):
        notif = _mock_notification("normal")
        result = await svc.route(notif, tenant_id=1)
        assert len(result) == 1
        assert result[0].channel == "in_app"

    async def test_low_routes_to_batch(self, svc):
        notif = _mock_notification("low")
        result = await svc.route(notif, tenant_id=1)
        assert len(result) == 1
        assert result[0].channel == "batch"
        assert result[0].target == "daily_digest"
        assert result[0].status == "pending"

    async def test_unknown_priority_raises(self, svc):
        notif = _mock_notification("invalid_priority")
        with pytest.raises(Exception):  # ValidationException once import is available
            await svc.route(notif, tenant_id=1)

    async def test_tenant_id_carried_on_all_records(self, svc):
        notif = _mock_notification("urgent")
        result = await svc.route(notif, tenant_id=99)
        for record in result:
            assert record.tenant_id == 99

    async def test_normal_without_user_id_returns_empty_list(self, svc):
        notif = _mock_notification("normal", user_id=None)
        result = await svc.route(notif, tenant_id=1)
        assert result == []
```

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_notification_routing.py -v` → 6 passed

---

### Step 4: Lint and type-check the new files

Run ruff and mypy on all new files.

**完成判定**: `ruff check src/services/notification_routing_service.py src/models/channel_delivery.py tests/unit/test_notification_routing.py` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/services/notification_routing_service.py src/models/channel_delivery.py` → 0 errors
- [ ] `ruff check tests/unit/test_notification_routing.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_routing.py -v` → 6 passed
- [ ] Service `__init__` takes `session: AsyncSession` with no default — verified by mypy if configured, otherwise by code review
- [ ] Service raises `ValidationException` for unknown priority — verified by unit test `test_unknown_priority_raises`
- [ ] Routing returns `list[ChannelDelivery]` — verified by return type annotation and test assertions

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| SmartNotification model from #593 is delayed, blocking real ORM integration | 中 | 中 | Keep notification mocked as plain object with attrs; swap mock for ORM import once #593 lands — no service signature change needed |
| Routing rules need to expand (e.g. SMS channel) | 低 | 中 | Routing logic is data-driven via a dict; adding a channel is a config change, not a code rewrite |
| ChannelDelivery return type needs to persist to DB | 低 | 中 | Dataclass is serializable; add an ORM mapper in a follow-up issue without changing the service interface |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/notification_routing_service.py src/models/channel_delivery.py tests/unit/test_notification_routing.py
git commit -m "feat(notification): implement rule-based NotificationRoutingService

- NotificationRoutingService.route() dispatches SmartNotification by priority:
  urgent -> in_app + email, normal -> in_app, low -> batch
- ChannelDelivery dataclass as return type (no ORM coupling)
- 6 unit tests covering all routing paths + error case
- Closes #594"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(notification): implement NotificationRoutingService" --body "Closes #594"

# 2. Update progress
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/customer_service.py` L? — 现有 service 模式（session injection, raise AppException）
- 父 issue / 关联：#47 (parent epic), #593 (SmartNotification model, dependency)
- Mock session pattern：TBD - 待验证：`tests/unit/conftest.py` L? — make_mock_session / MockState 使用示例

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
