# 40-campaigns · Add email and SMS delivery integrations

| 元数据 | 值 |
|---|---|
| Issue | #637 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0648-add-notification-api-router](../40-campaigns/0648-add-notification-api-router.md), [0649-add-template-engine-and-email-delivery](../40-campaigns/0649-add-template-engine-and-email-delivery.md), #636 (queue hook infrastructure) |
| 启用后赋能 | 营销活动触达（#40-series），告警通知，唤醒沉睡客户 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `NotificationService` 仅将通知记录写入 `notifications` 表，没有真正的外部渠道分发能力（email / SMS）。营销活动（#40-series）和告警系统（#39）均依赖邮件和短信触达用户，而这两块完全缺失，成为阻塞项。此外，即使渠道服务商临时不可用（如 SMTP 超时、Twilio 限速），系统也缺乏重试机制，导致通知永久丢失。

### 1.2 做完后

- **用户视角**：无直接可见变化 — 纯后端服务增强。
- **开发者视角**：`EmailService` 提供 `send_email()` 方法，支持 SMTP + HTML/plain-text；`SMSService` 提供 `send_sms()` 方法，兼容 Twilio 和 SendGrid 两套 SDK；`RetryableDelivery` 装饰器为所有外部调用注入 3 次 + 指数退避重试；`NotificationService` 在 `channel=email/sms` 时自动路由到对应 handler。

### 1.3 不做什么（剔除）

- [ ] 异步任务队列（Celery / BG Job — 由 #650 单独覆盖）
- [ ] Push 推送通知（APNs / FCM — future work）
- [ ] 邮件/SMS 模板管理（由 #662 / #664 覆盖）
- [ ] 多语言 / i18n 渲染（future work）

### 1.4 关键 KPI

- [ ] `PYTHONPATH=src pytest tests/unit/test_email_service.py tests/unit/test_sms_service.py tests/unit/test_retry_delivery.py -v` → ≥ 9 passed（每套 3 个 case）
- [ ] `ruff check src/services/channels/` → 0 errors
- [ ] `ruff check src/services/notification_service.py` → 0 errors（引入 channel dispatch 后）
- [ ] `PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v` → 全 passed（dispatch 路由不破坏现有 API）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/notification_service.py`](../../src/services/notification_service.py) L{1}-L{50}

```python
#:1-30:src/services/notification_service.py
class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def send_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        content: str,
        tenant_id: int = 0,
        **kwargs,
    ) -> NotificationModel:
        notification = NotificationModel(
            tenant_id=tenant_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            content=content,
            is_read=False,
            ...
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification
```

当前 `send_notification` 只写 DB，不调用任何外部服务。Router 在 [`src/api/routers/notifications.py`](../../src/api/routers/notifications.py) L{37}-L{43} 定义了 `NotificationCreate` schema，但无 channel 分发逻辑。

### 2.2 涉及文件清单

- 要改：
  - [`src/services/notification_service.py`](../../src/services/notification_service.py) — 新增 `channel` 参数，路由到 EmailService / SMSService
- 要建：
  - `src/services/channels/email_service.py` — SMTP 邮件发送
  - `src/services/channels/sms_service.py` — Twilio / SendGrid SMS 发送
  - `src/services/channels/base.py` — 抽象基类 + RetryableDelivery 重试装饰器
  - `src/services/channels/__init__.py` — 模块导出
  - `tests/unit/test_email_service.py` — EmailService 单元测试
  - `tests/unit/test_sms_service.py` — SMSService 单元测试
  - `tests/unit/test_retry_delivery.py` — 重试逻辑单元测试

### 2.3 缺什么

- [ ] `EmailService`：SMTP 连接、认证、HTML/plain-text 邮件发送，无 retry
- [ ] `SMSService`：Twilio SDK 和 SendGrid SDK 双后端支持，无 retry
- [ ] `RetryableDelivery` 装饰器：3 次重试 + 指数退避（base=2，max=30s）
- [ ] `NotificationService.send_notification` 的 channel 分发路由（`email`/`sms` → 对应 service）
- [ ] Queue hook 集成点（`on_delivery_failure` callback 注册机制）
- [ ] 单元测试覆盖（mock SMTP / Twilio SDK 调用）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/channels/base.py` | 抽象 `ChannelHandler` 基类 + `RetryableDelivery` 装饰器（3 次重试，exp backoff） |
| `src/services/channels/email_service.py` | `EmailService`：SMTP HTML/plain-text 邮件发送，实现 `ChannelHandler` |
| `src/services/channels/sms_service.py` | `SMSService`：Twilio / SendGrid 双后端，实现 `ChannelHandler` |
| `src/services/channels/__init__.py` | 导出 `EmailService`、`SMSService`、`ChannelHandler` |
| `tests/unit/test_email_service.py` | EmailService 单元测试（mock SMTP） |
| `tests/unit/test_sms_service.py` | SMSService 单元测试（mock Twilio SDK） |
| `tests/unit/test_retry_delivery.py` | RetryableDelivery 重试行为测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/notification_service.py`](../../src/services/notification_service.py) | 新增 `channel: str | None = None` 参数；`channel in ("email", "sms")` 时注入对应 handler；其余 channel 仍写 DB |
| [`src/api/routers/notifications.py`](../../src/api/routers/notifications.py) | `NotificationCreate` schema 增加 `channel: str | None = None`；传递给 service |

### 3.3 新增能力

- **Service class**：`EmailService(session: AsyncSession)` — `async def send_email(to: str, subject: str, html_body: str, plain_body: str | None = None) -> None`
- **Service class**：`SMSService(session: AsyncSession)` — `async def send_sms(to: str, body: str, provider: Literal["twilio", "sendgrid"] = "twilio") -> None`
- **Decorator**：`@RetryableDelivery(max_attempts=3, base_delay=2.0, max_delay=30.0)` — 包装任意 async 函数，失败时指数退避重试
- **Queue hook**：`ChannelHandler.on_failure(callback)` 注册 delivery failure callback，供 #650 Celery 队列集成
- **API field**：`POST /api/v1/notifications/send` 新增 `channel?: string`（`email` | `sms` | `in_app`，默认 `in_app`）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Twilio + SendGrid 双 SDK 而非单一 provider**：客户可能已有其中一种合同；双后端通过 `provider: Literal["twilio", "sendgrid"]` 切换，无需 fork 代码。
- **RetryableDelivery 用装饰器而非中间件**：装饰器直接内联在每个 handler 方法上，可读性强，pytest mock 友好；中间件会隐藏调用路径，测试难度高。
- **SMTP 用 aiosmtpd 而非直接 smtplib**：aiosmtpd 支持异步上下文，与 FastAPI/SQLAlchemy async 生态完全对齐，避免阻塞事件循环。
- **channel dispatch 放在 NotificationService 而非 Router**：保持 router 只做序列化 / 鉴权，业务路由在内核（service）是 CLAUDE.md 规范。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `aiosmtpd` | `>=1.4,<2.0` | async SMTP server/client，与 SQLAlchemy async 兼容 |
| `twilio` | `>=8.0,<9.0` | 当前 Twilio REST API 最新稳定 SDK |
| `sendgrid` | `>=6.0,<7.0` | SendGrid Python SDK v6，官方推荐 |

> 如果 project 暂不引入真实 SDK，可先以 `unstructured` 接口（httpx 直调 Twilio/SendGrid REST API）替代真实 SDK 依赖，待 #650 再锁定正式 SDK 版本。

### 4.3 兼容性约束

- 多租户：SMTP 发件人 / SMS sender ID 均按 tenant_id 隔离（从 `tenants` 表读取各租户的配置）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`ValidationException` — channel 配置错误；`ForbiddenException` — provider credential 缺失）
- Retry 装饰器捕获所有 `Exception`，并在最后一次重试失败后将原始异常重新抛出（不吞掉错误）
- 不允许在 `NotificationService.send_notification` 中同步调用 SMTP/SMS（必须 `await`，保持 async 链路）

### 4.4 已知坑

1. **SMTP 连接复用（connection pool exhaustion）** → 规避：每次发送创建独立 SMTP 连接，发送完成后立即 `smtp.quit()`，不使用连接池
2. **Twilio Rate Limit 时返回 429，但不抛异常** → 规避：`RetryableDelivery` 装饰器检测 HTTP 429 状态码，将 `DeliveryRateLimited` 转为可重试异常
3. **SQLAlchemy AsyncSession 在多线程（同步 SMTP）中被锁死** → 规避：所有 channel handler 必须 `async def`，用 `aiosmtpd` 或 `httpx.AsyncClient`；禁止在 handler 内调用同步 `smtplib.SMTP`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 channels 模块基类

在 `src/services/channels/base.py` 定义 `ChannelHandler` 抽象基类和 `@RetryableDelivery` 装饰器。

操作：
- 新建 `src/services/channels/__init__.py`（空，仅做 `__all__` 导出）
- 新建 `src/services/channels/base.py`

```python
#:1-25:src/services/channels/base.py
import asyncio
import logging
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class DeliveryError(Exception):
    """Raised when a channel delivery fails after all retries."""


class DeliveryRateLimited(Exception):
    """Raised on 429 from provider — treated as retryable by RetryableDelivery."""


def RetryableDelivery(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], Callable[..., Coroutine[Any, Any, Any]]]:
    def decorator(fn: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(fn)
        async def wrapper(*args, **kwargs) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except DeliveryRateLimited as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                except DeliveryError as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                except Exception as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                logger.warning("RetryableDelivery attempt %d/%d failed for %s, sleeping %ss", attempt, max_attempts, fn.__name__, delay)
                await asyncio.sleep(delay)
            raise last_exc from None
        return wrapper
    return decorator


class ChannelHandler(ABC):
    """Abstract base for all delivery channels."""

    @abstractmethod
    async def send(self, recipient: str, subject: str | None, body: str, *, extra: dict | None = None) -> None:
        """Send a message. Raises DeliveryError on final failure."""
        ...

    def on_failure(self, callback: Callable[[Exception, dict], Coroutine[Any, Any, None]]) -> None:
        """Register a failure callback (used by queue integration, #650)."""
        ...
```

**完成判定**：`ruff check src/services/channels/base.py` → 0 errors

---

### Step 2: 实现 EmailService

在 `src/services/channels/email_service.py` 实现 `EmailService`。

操作：
- 新建 `src/services/channels/email_service.py`
- SMTP 配置从环境变量读取（`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`）

```python
#:1-45:src/services/channels/email_service.py
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from aiosmtplib import SMTP

from sqlalchemy.ext.asyncio import AsyncSession

from .base import ChannelHandler, DeliveryError, RetryableDelivery


class EmailService(ChannelHandler):
    def __init__(self, session: AsyncSession, tenant_id: int = 0):
        self.session = session
        self.tenant_id = tenant_id
        self._failure_callbacks: list = []

    @RetryableDelivery(max_attempts=3, base_delay=2.0, max_delay=30.0)
    async def send(self, recipient: str, subject: str | None, body: str, *, extra: dict | None = None) -> None:
        html_body = body
        plain_body = extra.get("plain_body") if extra else None
        await self._send_via_smtp(recipient, subject or "(no subject)", html_body, plain_body)

    async def _send_via_smtp(self, to: str, subject: str, html_body: str, plain_body: str | None) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = os.getenv("SMTP_FROM", "noreply@example.com")
        msg["To"] = to
        msg.attach(MIMEText(plain_body or html_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        smtp = SMTP(
            hostname=os.getenv("SMTP_HOST", "localhost"),
            port=int(os.getenv("SMTP_PORT", "587")),
        )
        await smtp.connect()
        if os.getenv("SMTP_USER"):
            await smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
        await smtp.send_message(msg)
        await smtp.quit()
```

**完成判定**：`ruff check src/services/channels/email_service.py` → 0 errors；`PYTHONPATH=src pytest tests/unit/test_email_service.py -v` → 3 passed

---

### Step 3: 实现 SMSService

在 `src/services/channels/sms_service.py` 实现 `SMSService`，支持 Twilio 和 SendGrid 两个 provider。

操作：
- 新建 `src/services/channels/sms_service.py`
- Provider 通过 `SMS_PROVIDER` 环境变量选择（`twilio` 或 `sendgrid`）

```python
#:1-40:src/services/channels/sms_service.py
import os
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from .base import ChannelHandler, DeliveryError, DeliveryRateLimited, RetryableDelivery


class SMSService(ChannelHandler):
    def __init__(self, session: AsyncSession, tenant_id: int = 0):
        self.session = session
        self.tenant_id = tenant_id
        self.provider: Literal["twilio", "sendgrid"] = os.getenv("SMS_PROVIDER", "twilio")
        self._failure_callbacks: list = []

    @RetryableDelivery(max_attempts=3, base_delay=2.0, max_delay=30.0)
    async def send(self, recipient: str, subject: str | None, body: str, *, extra: dict | None = None) -> None:
        if self.provider == "twilio":
            await self._send_twilio(recipient, body)
        else:
            await self._send_sendgrid(recipient, body)

    async def _send_twilio(self, to: str, body: str) -> None:
        from twilio.rest import Client as TwilioClient
        client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        client.messages.create(body=body, from_=os.getenv("TWILIO_FROM"), to=to)

    async def _send_sendgrid(self, to: str, body: str) -> None:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        msg = Mail(from_email=os.getenv("SENDGRID_FROM"), to_emails=to, plain_text_content=body, subject="(no subject)")
        sg.send(msg)
```

> 注意：Twilio `_send_twilio` 和 SendGrid `sg.send` 均为同步 SDK 方法，需要用 `await asyncio.to_thread(client.messages.create, ...)` 包装以避免阻塞事件循环。

**完成判定**：`ruff check src/services/channels/sms_service.py` → 0 errors；`PYTHONPATH=src pytest tests/unit/test_sms_service.py -v` → 3 passed

---

### Step 4: 更新 NotificationService 增加 channel dispatch

在 [`src/services/notification_service.py`](../../src/services/notification_service.py) 的 `send_notification` 方法中新增 channel 参数和分发逻辑。

操作：
- 在文件顶部添加 channel handler import

在 `send_notification` 方法中，新增收参 `channel: str | None = None`，方法体内插入：

```python
# 在 flush() 之后、return 之前插入（位置：原 L46 之后）
if channel == "email":
    from services.channels.email_service import EmailService
    svc = EmailService(self.session, tenant_id=tenant_id)
    await svc.send(
        recipient=kwargs.get("email_to", ""),
        subject=title,
        body=content,
        extra={"plain_body": kwargs.get("plain_body")},
    )
elif channel == "sms":
    from services.channels.sms_service import SMSService
    svc = SMSService(self.session, tenant_id=tenant_id)
    await svc.send(
        recipient=kwargs.get("phone_to", ""),
        subject=None,
        body=content,
    )
# channel=None 时不调用外部服务，仅写 DB（现有行为）
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors；`PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v` → 全 passed

---

### Step 5: 更新 Notifications router

在 [`src/api/routers/notifications.py`](../../src/api/routers/notifications.py) 的 `NotificationCreate` schema 中添加 `channel` 字段。

操作：
- 在 `NotificationCreate` 类中增加 `channel: str | None = Field(None, description="'email' | 'sms' | 'in_app'")`

在 router handler 中，将 `channel` 参数透传给 `NotificationService.send_notification`：

```python
# 在 send_notification 调用处（第 N 行）添加 channel=notification.channel
notification = await svc.send_notification(
    user_id=notification.user_id,
    notification_type=notification.notification_type,
    title=notification.title,
    content=notification.content,
    channel=notification.channel,  # 新增
    **kwargs,
)
```

**完成判定**：`ruff check src/api/routers/notifications.py` → 0 errors

---

### Step 6: 编写单元测试

操作：
- 新建 `tests/unit/test_email_service.py`
- 新建 `tests/unit/test_sms_service.py`
- 新建 `tests/unit/test_retry_delivery.py`

```python
#:1-40:tests/unit/test_email_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.channels.email_service import EmailService

@pytest.fixture
def mock_session():
    return MagicMock()

class TestEmailService:
    @pytest.mark.asyncio
    async def test_send_email_success(self, mock_session):
        with patch("services.channels.email_service.aiosmtplib.SMTP") as mock_smtp_cls:
            mock_smtp = AsyncMock()
            mock_smtp_cls.return_value = mock_smtp
            svc = EmailService(mock_session, tenant_id=1)
            await svc.send("user@example.com", "Hello", "<h1>Hi</h1>")
            mock_smtp.connect.assert_called_once()
            mock_smtp.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_retries_on_connection_error(self, mock_session):
        with patch("services.channels.email_service.aiosmtplib.SMTP") as mock_smtp_cls:
            mock_smtp = AsyncMock()
            mock_smtp.connect.side_effect = [ConnectionError("timeout"), ConnectionError("timeout"), None]
            mock_smtp.send_message = AsyncMock()
            mock_smtp.quit = AsyncMock()
            mock_smtp_cls.return_value = mock_smtp
            svc = EmailService(mock_session, tenant_id=1)
            await svc.send("user@example.com", "Hello", "<h1>Hi</h1>")
            assert mock_smtp.connect.call_count == 3

    @pytest.mark.asyncio
    async def test_send_email_raises_after_all_retries_fail(self, mock_session):
        with patch("services.channels.email_service.aiosmtplib.SMTP") as mock_smtp_cls:
            mock_smtp = AsyncMock()
            mock_smtp.connect.side_effect = ConnectionRefusedError("refused")
            mock_smtp.quit = AsyncMock()
            mock_smtp_cls.return_value = mock_smtp
            svc = EmailService(mock_session, tenant_id=1)
            with pytest.raises(Exception):
                await svc.send("user@example.com", "Hello", "<h1>Hi</h1>")
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_email_service.py tests/unit/test_sms_service.py tests/unit/test_retry_delivery.py -v` → ≥ 9 passed

---

## 6. 验收

- [ ] `ruff check src/services/channels/` → 0 errors
- [ ] `ruff check src/services/notification_service.py` → 0 errors
- [ ] `ruff check src/api/routers/notifications.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_email_service.py -v` → 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_sms_service.py -v` → 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_retry_delivery.py -v` → 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v` → 全 passed
- [ ] `PYTHONPATH=src mypy src/services/channels/ --ignore-missing-imports` → 0 errors（类型检查通过）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| SMTP provider（SendGrid SES / 第三方）持续不可达，所有重试耗尽后通知丢失 | 低 | 高 | `NotificationService` 在 channel dispatch 异常时 fallback 到 DB 写入（现有行为），不抛出；通知在 in_app 中仍可见 |
| Twilio / SendGrid SDK 升级破坏 API（v8 → v9 breaking change） | 中 | 中 | `SMSService` 抽象 provider 调用到独立 `_send_twilio` / `_send_sendgrid` 方法；仅改这两个方法，不动调用方 |
| 重试风暴：大量通知积压时，指数退避导致后续通知延迟超过 SLA | 中 | 中 | `#650 Celery` 引入死信队列（DLQ），超时通知不无限重试而进入 DLQ；`RetryableDelivery` 不做 queue 直接在进程内重试，是临时方案 |
| Tenant 无 email/sms 配置时，handler 抛 `ValidationException` 导致整个通知发送失败（DB 写入被回滚） | 低 | 中 | channel dispatch wrapped in `try/except` 并 fallback 到 in_app；不阻断 DB 写入事务 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/channels/ src/services/notification_service.py src/api/routers/notifications.py tests/unit/test_email_service.py tests/unit/test_sms_service.py tests/unit/test_retry_delivery.py
git commit -m "feat(campaigns): add EmailService and SMSService with 3x retry (exp backoff)

Closes #637"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#637): email and SMS delivery integrations" --body "Closes #637

## Summary
- Add `src/services/channels/` with `EmailService` (SMTP via aiosmtpd) and `SMSService` (Twilio/SendGrid)
- `@RetryableDelivery` decorator: 3 attempts, exponential backoff (base=2s, max=30s)
- `NotificationService.send_notification` routes `channel=email/sms` to corresponding handler
- `NotificationCreate` schema gains optional `channel` field

## Test plan
- [x] ruff check src/services/channels/ → 0 errors
- [x] pytest tests/unit/test_email_service.py tests/unit/test_sms_service.py tests/unit/test_retry_delivery.py → ≥ 9 passed
- [x] pytest tests/unit/test_notifications_router.py → full pass

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/notification_service.py`](../../src/services/notification_service.py) — 现有通知服务，所有新 channel handler 的调用方
- 同类参考实现：[`src/api/routers/notifications.py`](../../src/api/routers/notifications.py) — router，serialization 规范
- 第三方文档：[Twilio Python SDK](https://www.twilio.com/docs/libraries/python)
- 第三方文档：[SendGrid Python SDK](https://github.com/sendgrid/sendgrid-python)
- 第三方文档：[aiosmtplib](https://aiosmtpd.readthedocs.io/)
- 父 issue：#39
- 关联：#636 (queue hook infrastructure), #649 (TemplateService and EmailService basic delivery), #650 (Celery queue integration)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
