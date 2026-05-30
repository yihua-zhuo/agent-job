# 40-campaigns · Add TemplateService and EmailService

| 元数据 | 值 |
|---|---|
| Issue | #649 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [0642-notification-infrastructure](../0642-notification-infrastructure.md), #662 (NotificationTemplateModel), #664 (NotificationLogModel) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `NotificationService.send_notification` 仅将通知记录写入 `notifications` 表，没有任何渠道分发能力。当 `channel=email` 时，需要加载邮件模板（从 `notification_templates` 表，按 name + channel 查询），替换变量（`str.format`），然后通过 SMTP 发送 HTML 邮件。现阶段两件事都完全缺失。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯后端服务增强。
- **开发者视角**：`TemplateService(session)` 可通过 name + channel 加载模板并渲染变量；`EmailService` 可发送 HTML 邮件；`NotificationService.send_notification` 在 `channel=email` 时自动调用 `EmailService`。

### 1.3 不做什么（剔除）

- [ ] 邮件发送的重试机制（future work）
- [ ] 异步队列（future work，#650 Celery 单独覆盖）
- [ ] 短信 / Push 渠道实现（仅实现 email channel）
- [ ] Router 层 API 端点（本板块仅实现 Service 层）
- [ ] SMTP 连接池或长连接复用（单次 `aiosmtplib.SMTP` 连接，用完即关）

### 1.4 关键 KPI

- 指标 1：`ruff check src/services/template_service.py src/services/email_service.py` → 0 errors
- 指标 2：`PYTHONPATH=src pytest tests/unit/test_template_service.py tests/unit/test_email_service.py -v` → ≥ 6 passed
- 指标 3：`PYTHONPATH=src pytest tests/integration/test_notification_service_integration.py -v` → 全 passed（notification channel=email 路径）
- 指标 4：`ruff check src/configs/settings.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

`NotificationService.send_notification` 只写 DB，不做任何渠道分发：

[`src/services/notification_service.py`](../../../src/services/notification_service.py) L{23}-L{47}

```python
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

`NotificationTemplateModel`（#662 已建）：

[`src/db/models/notification_template.py`](../../src/db/models/notification_template.py)

```python
class NotificationTemplateModel(Base):
    __tablename__ = "notification_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/notification_service.py`](../../../src/services/notification_service.py) — `send_notification` 增加 email channel 分发逻辑
  - [`src/configs/settings.py`](../../../src/configs/settings.py) — 增加 SMTP 配置字段
  - [`alembic/env.py`](../../../alembic/env.py) — 确认 `NotificationTemplateModel` 已在 import 列表（如未添加需补入）
- 要建：
  - `src/services/template_service.py` — `TemplateService`（load_template + render）
  - `src/services/email_service.py` — `EmailService`（send_email_html）
  - `tests/unit/test_template_service.py` — `TemplateService` 单元测试（3 cases）
  - `tests/integration/test_notification_service_integration.py` — `send_notification channel=email` 集成测试（如不存在）

### 2.3 缺什么

- [ ] `TemplateService`：无 — 需要新建，加载模板（name+channel）并渲染变量
- [ ] `EmailService`：无 — 需要新建，基于 aiosmtplib 发送 SMTP 邮件
- [ ] SMTP 配置字段：`SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` 未在 `Settings` 中定义
- [ ] `NotificationService.send_notification`：缺少 channel 参数和 email 渠道分发逻辑
- [ ] 发送失败时写入 `notification_logs`（status=failed，error=异常信息）— 由 #664 NotificationLogModel 支持

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/template_service.py` | `TemplateService`：通过 name + channel 从 `notification_templates` 表加载模板，提供 `render(variables: dict)` 变量替换（`str.format`） |
| `src/services/email_service.py` | `EmailService`：使用 aiosmtplib 异步发送 HTML 邮件；`send_email_html(to, subject, html_body, from_addr=None)` 包装 `TemplateService.render` |
| `tests/unit/test_template_service.py` | `TemplateService` 单元测试：load_template 命中/未命中、render 变量替换、缺失变量不抛异常 |
| `tests/unit/test_email_service.py` | `EmailService` 单元测试：SMTP 配置缺失抛 `ValidationException`、正常调用 aiosmtplib.send_message |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/notification_service.py`](../../../src/services/notification_service.py) | `send_notification` 新增 `channel: str = "in_app"` 参数；`channel == "email"` 时调用 `EmailService.send_email_html`，异常时写 `NotificationLogModel`（status=failed） |
| [`src/configs/settings.py`](../../../src/configs/settings.py) | 新增 `smtp_host / smtp_port / smtp_user / smtp_password / smtp_from` 字段（全部 `Field(default=None)`，可选配置） |

### 3.3 新增能力

- **Service method**：`TemplateService.load_template(self, name: str, channel: str, tenant_id: int) -> NotificationTemplateModel`
- **Service method**：`TemplateService.render(self, template: NotificationTemplateModel, variables: dict) -> tuple[str | None, str | None]`（返回 (subject, body_html)）
- **Service method**：`EmailService.send_email_html(self, to: str, subject: str, html_body: str, from_addr: str | None = None) -> None`
- **Service method**：`NotificationService.send_notification` 新增 `channel` 参数，email 渠道触发 `EmailService`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `aiosmtplib` 不选 `smtplib`**：项目已全面 async，`smtplib.SMTP` 是同步阻塞 API，会卡住 ASGI event loop。
- **选 `str.format` 不选 Jinja2**：issue 明确要求 `str.format`，Jinja2 增加额外依赖且超出需求范围。
- **选 `Field(default=None)` SMTP 配置不选必填**：允许在 SMTP 未配置时启动服务，发送邮件时抛 `ValidationException`，与"开发/测试环境可能无邮件服务器"的实际场景一致。
- **SMTP 配置存 `Settings` 不存 DB**：邮件发送配置属于应用级全局设置，不是多租户数据，Settings 比 DB 更合适。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `aiosmtplib` | `>=3.0` | 项目已使用 asyncpg；aiosmtplib 3.x 是最新稳定版，支持 Python 3.10+ async context manager |

### 4.3 兼容性约束

- 多租户：`load_template` 查询必须 `WHERE tenant_id = :tenant_id AND name = :name AND channel = :channel`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`ValidationException` / `NotFoundException`），**不**返回 `ApiResponse.error()`
- `email_service.py` 在 `send_email_html` 失败时仅 `log.exception()`，不向上抛（保证通知记录仍能写入 DB）

### 4.4 已知坑

1. **`aiosmtplib.SMTP` 在 `finally` 块中 `await smtp.quit()` 可能抛异常** → 症状：`quit()` 在连接已断开时（如服务器强制关闭）抛 `aiosmtplib.SMTPServerDisconnected` → 规避：使用 `await smtp.aclose()`（async context manager `async with SMTP(...) as smtp:` 自动处理优雅关闭）
2. **`str.format` 对缺失变量默认抛 `KeyError`** → 症状：`render` 时若模板有 `{missing_var}` 会崩溃 → 规避：使用 `string.Template(template_str).substitute(variables)`（缺失 key 抛 `KeyError`），或捕获并以原占位符字符串保留未填充变量
3. **`aiosmtplib` 连接超时默认值过长（120s）** → 症状：SMTP 服务器无响应时线程卡住 → 规避：`SMTP(..., timeout=30)` 显式传 30s 超时
4. **SMTP_PASSWORD 在 .env 明文存储** → 症状：密码泄露风险 → 规避：仅在本板块做技术实现；密码管理（vault/secrets manager）属于 future work

---

## 5. 实现步骤（按顺序）

### Step 1: 添加 SMTP 配置字段到 Settings

在 `Settings` 类中新增 5 个 SMTP 相关字段，支持从 `.env` 加载。

操作：
- a) 在 `src/configs/settings.py` 的 `Settings` 类中，`openapi_enabled` 字段之后新增：

```python
    # SMTP / Email
    smtp_host: str | None = Field(default=None, description="SMTP server host (e.g. smtp.example.com)")
    smtp_port: int = Field(default=587, description="SMTP port (default 587 for TLS)")
    smtp_user: str | None = Field(default=None, description="SMTP username")
    smtp_password: str | None = Field(default=None, description="SMTP password")
    smtp_from: str | None = Field(default=None, description="Default From address (e.g. noreply@example.com)")
```

**完成判定**：`ruff check src/configs/settings.py` → 0 errors

---

### Step 2: 创建 TemplateService

`TemplateService` 从 `notification_templates` 表加载模板（按 name + channel + tenant_id），提供 `render` 方法做 `str.format` 变量替换。

操作：
- a) 新建 `src/services/template_service.py`：

```python
"""Template service — load and render notification templates."""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification_template import NotificationTemplateModel
from pkg.errors.app_exceptions import NotFoundException

logger = logging.getLogger(__name__)


class TemplateService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def load_template(
        self, name: str, channel: str, tenant_id: int
    ) -> NotificationTemplateModel:
        stmt = select(NotificationTemplateModel).where(
            NotificationTemplateModel.tenant_id == tenant_id,
            NotificationTemplateModel.name == name,
            NotificationTemplateModel.channel == channel,
        )
        result = await self.session.execute(stmt)
        template = result.scalar_one_or_none()
        if template is None:
            raise NotFoundException(f"Template: {name} ({channel})")
        return template

    def render(
        self, template: NotificationTemplateModel, variables: dict
    ) -> tuple[str | None, str | None]:
        subject = None
        body_html = None
        if template.subject:
            subject = template.subject.format_map(variables)
        if template.body_html:
            body_html = template.body_html.format_map(variables)
        return subject, body_html
```

**完成判定**：`ruff check src/services/template_service.py` → 0 errors

---

### Step 3: 创建 EmailService

`EmailService` 使用 aiosmtplib 异步发送 HTML 邮件；`send_email_html` 内部调用 `TemplateService.render`（可选），SMTP 配置缺失时抛 `ValidationException`。

操作：
- a) 新建 `src/services/email_service.py`：

```python
"""Email service — send HTML emails via aiosmtplib."""

import logging
from email.base64mime import body_encode
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import settings
from pkg.errors.app_exceptions import ValidationException

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def send_email_html(
        self,
        to: str,
        subject: str,
        html_body: str,
        from_addr: str | None = None,
    ) -> None:
        if not settings.smtp_host or not settings.smtp_user:
            raise ValidationException(
                "SMTP configuration is missing. Set SMTP_HOST and SMTP_USER in .env"
            )

        sender = from_addr or settings.smtp_from or settings.smtp_user

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            smtp = aiosmtplib.SMTP(
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                timeout=30,
            )
            await smtp.connect()
            try:
                await smtp.send_message(msg)
            finally:
                await smtp.quit()
        except Exception as exc:
            logger.exception("Failed to send email to %s: %s", to, exc)
            raise
```

**完成判定**：`ruff check src/services/email_service.py` → 0 errors

---

### Step 4: 更新 NotificationService — 支持 channel=email 分发

在 `send_notification` 中新增 `channel` 参数，当 `channel == "email"` 时调用 `EmailService` 发送邮件。

操作：
- a) 在 `notification_service.py` 文件顶部新增 import：

```python
from src.services.email_service import EmailService
from src.services.template_service import TemplateService
from db.models.notification_log import NotificationLogModel
```

- b) 修改 `send_notification` 方法签名，在 `tenant_id` 之后新增 `channel: str = "in_app"` 参数

- c) 在 `self.session.add(notification)` 之后、`await self.session.flush()` 之前插入 email 分发逻辑：

```python
        if channel == "email":
            try:
                tmpl_svc = TemplateService(self.session)
                template = await tmpl_svc.load_template(
                    name=notification_type, channel="email", tenant_id=tenant_id
                )
                subject, body_html = tmpl_svc.render(
                    template, {"title": title, "content": content}
                )
                email_svc = EmailService(self.session)
                await email_svc.send_email_html(
                    to=kwargs.get("recipient_email", ""),
                    subject=subject or title or "Notification",
                    html_body=body_html or content or "",
                )
            except Exception as exc:
                logger.exception("Email send failed for notification %s: %s", notification.id, exc)
                log_entry = NotificationLogModel(
                    tenant_id=tenant_id,
                    notification_id=notification.id,
                    channel="email",
                    status="failed",
                    attempts=1,
                    error=str(exc),
                )
                self.session.add(log_entry)
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

---

### Step 5: 编写 TemplateService 单元测试

操作：
- a) 新建 `tests/unit/test_template_service.py`：

```python
"""Unit tests for TemplateService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.template_service import TemplateService
from db.models.notification_template import NotificationTemplateModel
from pkg.errors.app_exceptions import NotFoundException


class TestTemplateService:
    def _make_template(self, **overrides):
        attrs = {
            "id": 1, "tenant_id": 10, "name": "welcome", "channel": "email",
            "subject": "Hello {name}", "body_html": "<p>Welcome, {name}!</p>",
            "body_text": None, "created_at": None,
        }
        attrs.update(overrides)
        obj = NotificationTemplateModel.__new__(NotificationTemplateModel)
        for k, v in attrs.items():
            setattr(obj, k, v)
        return obj

    @pytest.mark.asyncio
    async def test_load_template_found(self):
        mock_session = AsyncMock()
        row = MagicMock()
        row.scalar_one_or_none.return_value = self._make_template()
        mock_session.execute.return_value = row

        svc = TemplateService(mock_session)
        result = await svc.load_template("welcome", "email", tenant_id=10)
        assert result.name == "welcome"

    @pytest.mark.asyncio
    async def test_load_template_not_found_raises(self):
        mock_session = AsyncMock()
        row = MagicMock()
        row.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = row

        svc = TemplateService(mock_session)
        with pytest.raises(NotFoundException):
            await svc.load_template("missing", "email", tenant_id=10)

    def test_render_substitutes_variables(self):
        tmpl = self._make_template(subject="Hi {name}", body_html="<p>{msg}</p>")
        svc = TemplateService(AsyncMock())
        subject, body = svc.render(tmpl, {"name": "Alice", "msg": "Hello!"})
        assert subject == "Hi Alice"
        assert body == "<p>Hello!</p>"

    def test_render_preserves_missing_vars(self, caplog):
        tmpl = self._make_template(subject="Hi {name}", body_html="<p>{missing}</p>")
        svc = TemplateService(AsyncMock())
        subject, body = svc.render(tmpl, {"name": "Bob"})
        assert subject == "Hi Bob"
        assert body == "<p>{missing}</p>"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_template_service.py -v` → 4 passed

---

### Step 6: 编写 EmailService 单元测试

操作：
- a) 新建 `tests/unit/test_email_service.py`：

```python
"""Unit tests for EmailService."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.email_service import EmailService
from pkg.errors.app_exceptions import ValidationException


class TestEmailService:
    @pytest.mark.asyncio
    async def test_send_email_html_raises_when_smtp_not_configured(self):
        with patch("services.email_service.settings") as mock_settings:
            mock_settings.smtp_host = None
            mock_settings.smtp_user = None
            svc = EmailService(AsyncMock())
            with pytest.raises(ValidationException) as exc_info:
                await svc.send_email_html(
                    to="user@example.com",
                    subject="Test",
                    html_body="<p>Hello</p>",
                )
            assert "SMTP configuration is missing" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_send_email_html_success(self):
        with patch("services.email_service.settings") as mock_settings:
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_user = "user"
            mock_settings.smtp_password = "pass"
            mock_settings.smtp_from = "noreply@test.com"

            mock_smtp = AsyncMock()
            mock_smtp.connect = AsyncMock()
            mock_smtp.send_message = AsyncMock()
            mock_smtp.quit = AsyncMock()

            with patch("services.email_service.aiosmtplib.SMTP", return_value=mock_smtp):
                svc = EmailService(AsyncMock())
                await svc.send_email_html(
                    to="user@example.com",
                    subject="Hello",
                    html_body="<p>Test</p>",
                )
                mock_smtp.connect.assert_called_once()
                mock_smtp.send_message.assert_called_once()
                mock_smtp.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_html_logs_and_raises_on_smtp_error(self):
        with patch("services.email_service.settings") as mock_settings:
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_user = "user"
            mock_settings.smtp_password = "pass"
            mock_settings.smtp_from = "noreply@test.com"

            mock_smtp = AsyncMock()
            mock_smtp.connect = AsyncMock(side_effect=OSError("Connection refused"))
            mock_smtp.quit = AsyncMock()

            with patch("services.email_service.aiosmtplib.SMTP", return_value=mock_smtp):
                svc = EmailService(AsyncMock())
                with pytest.raises(OSError):
                    await svc.send_email_html(
                        to="user@example.com",
                        subject="Hello",
                        html_body="<p>Test</p>",
                    )
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_email_service.py -v` → 3 passed

---

## 6. 验收

- [ ] `ruff check src/services/template_service.py src/services/email_service.py src/services/notification_service.py src/configs/settings.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_template_service.py -v` → 4 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_email_service.py -v` → 3 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_notification_service_integration.py -v` → 全 passed（如文件不存在，跳过）
- [ ] `PYTHONPATH=src mypy src/services/template_service.py src/services/email_service.py` → 0 errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `aiosmtplib` 连接失败（网络问题）导致 `send_notification` 事务回滚 | 低 | 中 | `email_service.py` 中捕获异常写 `NotificationLogModel`，`send_notification` 本身不抛异常；通知记录仍写入 DB，邮件失败有日志可查 |
| SMTP 配置缺失时服务启动成功但发送时抛 `ValidationException` | 中 | 低 | 配置缺失时异常信息清晰；建议在 .env.example 添加 SMTP 配置示例 |
| `aiosmtplib` 依赖引入与现有依赖冲突 | 极低 | 高 | 在 `pyproject.toml` 添加 `aiosmtplib>=3.0` 并运行 `pip install aiosmtplib`，如冲突在 PR 前解决 |
| `render` 中 `format_map` 对缺失 key 静默保留占位符（而非抛异常）| 低 | 低 | 当前设计如此（`KeyError` 的默认行为被 `format_map` 跳过）；如需严格校验，在 `render` 中先检查 `variables.keys() >= required_keys` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/template_service.py
git add src/services/email_service.py
git add src/services/notification_service.py
git add src/configs/settings.py
git add tests/unit/test_template_service.py
git add tests/unit/test_email_service.py
git commit -m "feat(campaigns): add TemplateService and EmailService for #649"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(campaigns): add TemplateService and EmailService (#649)" --body "Closes #649"

# 2. 更新进度
# - 在本板块文档 docs/dev-plan/40-campaigns/0649-add-template-engine-and-email-delivery.md §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/notification_service.py`](../../../src/services/notification_service.py) — 本板块修改的对象
- 同类参考实现：[`src/services/automation_rules.py`](../../../src/services/automation_rules.py) — RULES 中 `email.send` action 类型定义了模板引用方式
- 第三方文档：[aiosmtplib documentation](https://aiosmtplib.readthedocs.io/) — async SMTP client
- 第三方文档：[Python string.Template substitute](https://docs.python.org/3/library/string.html#string.Template) — 变量替换行为参考
- 父 issue / 关联：#39 (父), #648 (依赖，当前 repo 中无对应 doc), #662 (NotificationTemplateModel), #664 (NotificationLogModel), #650 (Celery queue — future work)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
