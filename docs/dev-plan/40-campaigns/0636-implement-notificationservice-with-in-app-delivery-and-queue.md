# 通知服务 · 实现多通道分发与投递状态

| 元数据 | 值 |
|---|---|
| Issue | #636 |
| 分类 | [40-campaigns](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `NotificationService.send_notification()` 只做 in_app 存储（DB 写一条 `NotificationModel`），没有任何通道分发抽象，也没有投递状态跟踪。Issue #636 要求在发送层加入 channel 分发（in_app / queued）、队列钩子（Celery task stub）和完整投递状态机（queued→sent→delivered→read）。不做这些，系统无法支持后续 Email/SMS/Push 通道扩展，也无法向调用方报告真实的投递结果。

### 1.2 做完后

- **用户视角**：无可见变化 — 纯后端基础设施增强。
- **开发者视角**：`NotificationService` 新增 `dispatch_notification()` 方法，按 `channel` 参数分发；`NotificationModel` 增加 `delivery_status` 字段；`send_notification()` 签名不变但内部通过 dispatcher 路由；队列任务以 stub 接口存在（`enqueue_task` 占位函数，不依赖真实 Celery 集群）。

### 1.3 不做什么（剔除）

- [ ] 真实的 Email / SMS / Push 集成（留待后续 issue）
- [ ] Celery 集群或 broker 配置（只写 stub interface，不连接 RabbitMQ/Redis）
- [ ] `notification_preferences` 表的读写（router 中两处 `# TODO` 不在本板块解决）
- [ ] 修改 `ReminderModel` 相关逻辑

### 1.4 关键 KPI

- `ruff check src/services/notification_service.py src/db/models/notification.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → ≥ 8 passed
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/notification_service.py`](../../../src/services/notification_service.py) L23-L47

```23:47:src/services/notification_service.py
    async def send_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        content: str,
        tenant_id: int = 0,
        **kwargs,
    ) -> NotificationModel:
        """发送通知"""
        notification = NotificationModel(
            tenant_id=tenant_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            content=content,
            is_read=False,
            related_type=kwargs.get("related_type"),
            related_id=kwargs.get("related_id"),
            created_at=datetime.now(UTC),
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification
```

`NotificationModel` 当前字段（缺 `delivery_status`）：

主入口：[`src/db/models/notification.py`](../../../src/db/models/notification.py) L11-L25

```11:25:src/db/models/notification.py
class NotificationModel(Base):
    """Notification entity mapped to the `notifications` table."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

Router 已存在：[`src/api/routers/notifications.py`](../../../src/api/routers/notifications.py)

单元测试仅覆盖 router，不覆盖 service： [`tests/unit/test_notifications_router.py`](../../../tests/unit/test_notifications_router.py)

### 2.2 涉及文件清单

- 要改：
  - [`src/services/notification_service.py`](../../../src/services/notification_service.py) — 增加 channel 分发逻辑、队列钩子、投递状态机
  - [`src/db/models/notification.py`](../../../src/db/models/notification.py) — 增加 `delivery_status` 列、`sent_at`/`delivered_at` 时间戳列
- 要建：
  - `tests/unit/test_notification_service.py` — 针对 NotificationService 各方法的单元测试（mock DB）
  - `alembic/versions/<id>_add_notification_delivery_status.py` — 增加 `delivery_status`/`sent_at`/`delivered_at` 列

### 2.3 缺什么

- [ ] `NotificationModel` 无 `delivery_status` 字段，无法表示 queued / sent / delivered 状态
- [ ] `send_notification()` 无 channel 分发抽象，所有通知硬写 DB，不支持 Email/SMS/Push
- [ ] 无队列任务钩子，无法把耗时操作（外部 API 调用）从同步路径剥离
- [ ] 无 `sent_at`/`delivered_at` 时间戳，无法追踪投递耗时
- [ ] 无 `tests/unit/test_notification_service.py`，service 层缺少独立单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_notification_service.py` | 覆盖 NotificationService 所有核心方法的单元测试（mock DB） |
| `alembic/versions/<id>_add_notification_delivery_status.py` | 为 `notifications` 表增加 `delivery_status`、`sent_at`、`delivered_at` 列 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/notification_service.py`](../../../src/services/notification_service.py) | 新增 `DeliveryStatus` 枚举；新增 `dispatch_notification()` 通道分发入口；新增 `enqueue_task()` Celery stub；`send_notification()` 改为通过 dispatcher 路由；新增 `update_delivery_status()` 方法 |
| [`src/db/models/notification.py`](../../../src/db/models/notification.py) | 新增 `delivery_status: Mapped[str]` 列（default="queued"）；新增 `sent_at`、`delivered_at: Mapped[datetime | None]` 列；更新 `to_dict()` 包含新字段 |

### 3.3 新增能力

- **ORM model**：`NotificationModel` 新增 `delivery_status` / `sent_at` / `delivered_at` 字段
- **Service method**：`NotificationService.dispatch_notification(...)` — 入口方法，按 channel 分发
- **Service method**：`NotificationService.update_delivery_status(notification_id, status, tenant_id) -> NotificationModel`
- **Enum**：`DeliveryStatus` = `queued | sent | delivered`
- **Stub**：`enqueue_task(queue_name: str, task_name: str, **kwargs) -> None`（占位，不连 broker）
- **Migration**：`alembic upgrade head` 新增 3 列（delivery_status / sent_at / delivered_at）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **channel 用字符串枚举而非 Enum 类**：`Literal["in_app", "email", "sms", "push"]` 作为 Pydantic/FastAPI 类型约束；数据库存字符串；Python 运行时用 `DeliveryStatus` 枚举类校验值域。理由：保持与现有 `type: str` 字段一致，无需改迁移 Schema。
- **队列用 stub 不引入 Celery 依赖**：当前无需真实 worker，故 `enqueue_task` 只打日志 (`logger.info`)，不 import celery。后续在启用后赋能板块替换为真实 task decorator。
- **dispatcher 模式**：新增 `dispatch_notification()` 替代直接写 DB；router 仍调用 `send_notification()`（保持签名兼容），内部路由到 `_deliver_in_app()` 或 `_enqueue_channel()`。

### 4.2 版本约束

无新依赖引入。所有改动依赖现有 `ruff`、`pytest`、`sqlalchemy`、`alembic` 版本。

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- `send_notification()` 保持原签名（参数顺序不变），router 无需修改
- `NotificationModel.to_dict()` 新增字段需向后兼容（`sent_at`/`delivered_at` 允许为 None）

### 4.4 已知坑

1. **SQLAlchemy Base 子类的列名不能用 `metadata`** → 新增字段全部避免与 Base 冲突的属性名
2. **Alembic autogen 会把 String 列的 `length` 去掉** → 手动审查迁移文件，确保 `String(20)` 不变成无长度 Text
3. **PYTHONPATH=src，import 路径写 `from db.models...`** → 本板块 service 新增 import 使用相对 `from db.models.notification import ...`，不写 `from src.db.models...`
4. **Async session 不要用 `async with get_db()`，用 `Depends(get_db)`** → router 已正确使用；service 不涉及 session 创建

---

## 5. 实现步骤（按顺序）

### Step 1: 修改 NotificationModel — 增加投递状态列

在 `src/db/models/notification.py` 中：

在 `import` 区增加 `Enum` 或使用 `str` 配合 `Literal`（本板块定义 `DeliveryStatus` 枚举放在 service 文件中，model 只存字符串）。

在 `NotificationModel` 类中，`created_at` 后新增三列：

```python
from enum import Enum

class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"   # is_read 兼容，read > delivered
```

在 `Base` 子类中（在 `created_at` 之后）插入：

```python
    delivery_status: Mapped[str] = mapped_column(
        String(20), default=DeliveryStatus.QUEUED.value, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

在 `to_dict()` 中增加：

```python
            "delivery_status": self.delivery_status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
```

**完成判定**：`ruff check src/db/models/notification.py` → 0 errors

---

### Step 2: 生成 Alembic 迁移

确保 `alembic/env.py` 已 import `NotificationModel`（应该已有）。

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic revision --autogenerate -m "add notification delivery_status sent_at delivered_at"
```

在 `alembic/versions/<new_rev>_add_notification_delivery_status_sent_at_delivered_at.py` 中：

- `op.add_column("notifications", sa.Column("delivery_status", sa.String(length=20), nullable=False, server_default="queued"))`
- `op.add_column("notifications", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))`
- `op.add_column("notifications", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))`
- `downgrade()` 三个 `op.drop_column(...)`

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 3: 重构 NotificationService — 增加 dispatcher 和队列 stub

在 `src/services/notification_service.py` 中：

文件顶部增加导入：

```python
import logging
from enum import Enum
from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification import NotificationModel
from db.models.reminder import ReminderModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


# ---------------------------------------------------------------------------
# Queue stub — replace body with real Celery task dispatch in a later issue
# ---------------------------------------------------------------------------

def enqueue_task(queue_name: str, task_name: str, **kwargs) -> None:
    """Stub: log the enqueue intent without touching a real broker."""
    logger.info(
        "QUEUE STUB enqueue task: queue=%s task=%s kwargs=%s",
        queue_name,
        task_name,
        kwargs,
    )
```

在 `NotificationService` 类中，新增通道分发入口方法：

```python
    async def dispatch_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        content: str,
        channel: str = "in_app",
        tenant_id: int = 0,
        **kwargs,
    ) -> NotificationModel:
        """Dispatch a notification through the appropriate channel.

        channel — "in_app" writes to DB immediately.
                  "email" / "sms" / "push" enqueue a queue task stub
                  and persist with status=queued.
        """
        if channel == "in_app":
            return await self._deliver_in_app(
                user_id, notification_type, title, content, tenant_id, **kwargs
            )
        else:
            return await self._enqueue_channel(
                user_id, notification_type, title, content, channel, tenant_id, **kwargs
            )
```

新增内部辅助方法：

```python
    async def _deliver_in_app(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        content: str,
        tenant_id: int,
        **kwargs,
    ) -> NotificationModel:
        notification = NotificationModel(
            tenant_id=tenant_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            content=content,
            is_read=False,
            delivery_status=DeliveryStatus.DELIVERED.value,
            related_type=kwargs.get("related_type"),
            related_id=kwargs.get("related_id"),
            created_at=datetime.now(UTC),
            delivered_at=datetime.now(UTC),
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def _enqueue_channel(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        content: str,
        channel: str,
        tenant_id: int,
        **kwargs,
    ) -> NotificationModel:
        notification = NotificationModel(
            tenant_id=tenant_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            content=content,
            is_read=False,
            delivery_status=DeliveryStatus.QUEUED.value,
            related_type=kwargs.get("related_type"),
            related_id=kwargs.get("related_id"),
            created_at=datetime.now(UTC),
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)

        enqueue_task(
            queue_name=f"notifications.{channel}",
            task_name=f"deliver_{channel}",
            notification_id=notification.id,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        return notification

    async def update_delivery_status(
        self,
        notification_id: int,
        status: DeliveryStatus,
        tenant_id: int,
    ) -> NotificationModel:
        """Update the delivery status of an existing notification.

        Allowed transitions: queued→sent→delivered.
        Transitions to READ are handled by mark_as_read() separately.
        """
        result = await self.session.execute(
            select(NotificationModel).where(
                and_(
                    NotificationModel.id == notification_id,
                    NotificationModel.tenant_id == tenant_id,
                )
            )
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise NotFoundException("通知")

        now = datetime.now(UTC)
        notification.delivery_status = status.value
        if status == DeliveryStatus.SENT:
            notification.sent_at = now
        elif status == DeliveryStatus.DELIVERED:
            notification.delivered_at = now

        await self.session.flush()
        await self.session.refresh(notification)
        return notification
```

**保留原有 `send_notification()`**：内部直接调用 `dispatch_notification(..., channel="in_app", ...)`，保持 router 不变。

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

---

### Step 4: 编写单元测试 tests/unit/test_notification_service.py

创建 `tests/unit/test_notification_service.py`，使用与 `test_customer_service.py` 相同的 mock session 模式。

文件结构：

```python
"""Unit tests for NotificationService — mocks DB, no real SQL executed."""
from unittest.mock import AsyncMock, MagicMock
import pytest
from services.notification_service import NotificationService, DeliveryStatus
from db.models.notification import NotificationModel
from pkg.errors.app_exceptions import NotFoundException
from datetime import datetime, timezone


def _make_mock_session():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=None)
    mock_result.scalar_one = AsyncMock(return_value=0)
    mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    mock_result.rowcount = 0
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
def svc():
    return NotificationService(_make_mock_session())


class TestDispatchInApp:
    def test_dispatch_in_app_sets_delivered_status(self, svc):
        # arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        svc.session.execute = AsyncMock(return_value=mock_result)
        # act
        result = svc.dispatch_notification(
            user_id=1, notification_type="info", title="Hi", content="Hello",
            channel="in_app", tenant_id=42,
        )
        # assert (sync caller — verify add was called with status delivered)
        svc.session.add.assert_called_once()
        added: NotificationModel = svc.session.add.call_args[0][0]
        assert added.delivery_status == DeliveryStatus.DELIVERED.value
        assert added.delivered_at is not None

    def test_dispatch_in_app_preserves_related_fields(self, svc):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        svc.session.execute = AsyncMock(return_value=mock_result)
        result = svc.dispatch_notification(
            user_id=1, notification_type="deal", title="Deal closed",
            content="...", channel="in_app", tenant_id=1,
            related_type="opportunity", related_id=99,
        )
        added: NotificationModel = svc.session.add.call_args[0][0]
        assert added.related_type == "opportunity"
        assert added.related_id == 99


class TestDispatchQueuedChannel:
    def test_dispatch_email_enqueues_task_stub(self, svc):
        import unittest.mock as umock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        svc.session.execute = AsyncMock(return_value=mock_result)
        with umock.patch("services.notification_service.enqueue_task") as mock_enqueue:
            svc.dispatch_notification(
                user_id=1, notification_type="alert", title="Alert",
                content="Check this", channel="email", tenant_id=1,
            )
            mock_enqueue.assert_called_once()
            call_kwargs = mock_enqueue.call_args[1]
            assert call_kwargs["queue_name"] == "notifications.email"
            assert call_kwargs["task_name"] == "deliver_email"

    def test_dispatch_email_sets_queued_status(self, svc):
        import unittest.mock as umock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        svc.session.execute = AsyncMock(return_value=mock_result)
        with umock.patch("services.notification_service.enqueue_task"):
            svc.dispatch_notification(
                user_id=1, notification_type="alert", title="Alert",
                content="Check", channel="email", tenant_id=1,
            )
        added: NotificationModel = svc.session.add.call_args[0][0]
        assert added.delivery_status == DeliveryStatus.QUEUED.value
        assert added.sent_at is None


class TestUpdateDeliveryStatus:
    def test_update_to_sent_sets_sent_at(self, svc):
        existing = MagicMock(spec=NotificationModel)
        existing.delivery_status = DeliveryStatus.QUEUED.value
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=existing)
        svc.session.execute = AsyncMock(return_value=mock_result)

        updated = await svc.update_delivery_status(
            notification_id=5, status=DeliveryStatus.SENT, tenant_id=1
        )
        assert existing.sent_at is not None
        assert existing.delivery_status == DeliveryStatus.SENT.value

    def test_update_to_delivered_sets_delivered_at(self, svc):
        existing = MagicMock(spec=NotificationModel)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=existing)
        svc.session.execute = AsyncMock(return_value=mock_result)

        updated = await svc.update_delivery_status(
            notification_id=5, status=DeliveryStatus.DELIVERED, tenant_id=1
        )
        assert existing.delivered_at is not None
        assert existing.delivery_status == DeliveryStatus.DELIVERED.value

    @pytest.mark.asyncio
    async def test_update_status_not_found_raises(self, svc):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        svc.session.execute = AsyncMock(return_value=mock_result)
        with pytest.raises(NotFoundException):
            await svc.update_delivery_status(
                notification_id=9999, status=DeliveryStatus.SENT, tenant_id=1
            )


class TestSendNotificationBackwardCompat:
    def test_send_notification_calls_dispatch_in_app(self, svc):
        import unittest.mock as umock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        svc.session.execute = AsyncMock(return_value=mock_result)
        with umock.patch.object(svc, "dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(spec=NotificationModel)
            await svc.send_notification(
                user_id=1, notification_type="info", title="T", content="C", tenant_id=1
            )
            mock_dispatch.assert_called_once()
            assert mock_dispatch.call_args[1]["channel"] == "in_app"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → ≥ 8 passed

---

## 6. 验收

- [ ] `ruff check src/services/notification_service.py src/db/models/notification.py` → 0 errors
- [ ] `ruff format --check src/services/notification_service.py src/db/models/notification.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → ≥ 8 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v` → 全 passed（向后兼容）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → 无新增 failures

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `delivery_status` 新列导致已有 `notification` 行 Schema 不一致（新老 notification 状态不同） | 低 | 中 | `server_default="queued"` 确保默认值；历史行保持 `is_read=False` 不变；router 中 `to_dict()` 兼容 None 值 |
| `dispatch_notification()` 新方法与旧 `send_notification()` 行为差异导致 router 测试失败 | 低 | 中 | 旧 `send_notification()` 内部调用 `dispatch_notification(..., channel="in_app")`，router 完全无感知；回归测试保证全绿 |
| Alembic 迁移在生产环境执行时间过长（大量历史 notification 行） | 低 | 高 | 迁移只加列不加数据写操作，执行极快；如遇锁问题在后续 issue 中添加 `ALTER TABLE ... SET (lock_timeout = '1s')` |
| 队列 stub `enqueue_task` 打日志但不报错，调用方无法感知任务是否真正入队 | 中 | 低 | 本板块为 stub，后续启用 Celery 真实 worker 时将 `enqueue_task` 替换为 `@celery_app.task` decorator；feature flag 控制开关 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/notification_service.py src/db/models/notification.py tests/unit/test_notification_service.py alembic/versions/
git commit -m "feat(campaigns): notification multi-channel dispatch and delivery status (#636)"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#636): NotificationService multi-channel dispatch and delivery status" --body "Closes #636"

# 2. 更新进度
# 在 docs/dev-plan/40-campaigns/0636-implement-notificationservice-with-in-app-delivery-and-queue.md §Changelog 表格新增一行
```

---

## 9. 参考

- 同类参考实现：[`src/services/automation_service.py`](../../../src/services/automation_service.py) — service 层 channel/action 分发模式参考
- 父 issue / 关联：#39（父 Epic），#635（前序板块）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
