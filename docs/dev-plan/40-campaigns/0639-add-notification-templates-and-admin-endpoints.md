# 通知管理 · Add NotificationTemplateModel and admin router endpoints

| 元数据 | 值 |
|---|---|
| Issue | #639 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `NotificationService.send_notification()` 仅接收固定 title/content 字符串，无法基于模板批量发送差异化通知。业务方要求按渠道（email/sms/push）维护多套通知模板，并在发送时注入客户变量（`{{customer_name}}`、`{{deal_amount}}` 等）。同时，管理员需要通过 API 查看发送日志和编辑模板列表，但目前没有 admin 专属端点。

### 1.2 做完后

- **用户视角**：无直接可见变化 — 纯底层能力，为后续运营自动化（按模板触发通知）提供基础。
- **开发者视角**：`NotificationService` 新增 `send_from_template()` 方法；新增 `admin_notifications_router` 提供 `GET /admin/notifications/logs`、`GET /admin/templates`、`POST /admin/templates` 三个端点；新增 `NotificationTemplateModel` 含 `vars` JSONB 字段存储模板变量定义。

### 1.3 不做什么（剔除）

- [ ] 不实现物理邮件/SMS 发送通道（由外部集成层负责）
- [ ] 不实现模板版本管理（仅单模板 latest 概念）
- [ ] 不实现权限控制粒度细分（admin 路由仅做 auth 验证，不做细粒度 RBAC）

### 1.4 关键 KPI

- 指标 1：`ruff check src/services/notification_service.py src/api/routers/admin_notifications.py` → 0 errors
- 指标 2：`PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → ≥ 5 passed（含新增 cases）
- 指标 3：`PYTHONPATH=src pytest tests/integration/test_notification_admin_integration.py -v` → ≥ 4 passed（如 integration 测试存在）
- 指标 4：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如有 migration）

---

## 2. 当前现状（起点）

### 2.1 现有实现

`NotificationService.send_notification()` 的签名如下：

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

`NotificationTemplateModel` 目前仅含 id, name, channel, subject, body_html, body_text, created_at；缺少 `vars` 字段来声明模板变量列表。

`admin_notifications.py` 路由文件尚不存在。

### 2.2 涉及文件清单

- 要改：
  - [`src/services/notification_service.py`](../../../src/services/notification_service.py) — 添加 `send_from_template()` 方法（含占位符替换逻辑）
  - [`src/db/models/notification_template.py`](../../../src/db/models/notification_template.py) — 新增 `vars: Mapped[dict | None]` JSONB 列
  - [`src/api/routers/notifications.py`](../../../src/api/routers/notifications.py) — 如需在 notifications_router 中注册 admin 子路由（按项目路由结构决定）
- 要建：
  - `src/api/routers/admin_notifications.py` — admin 通知管理路由（logs 列表 + templates CRUD）
  - `alembic/versions/<id>_add_vars_to_notification_templates.py` — vars 列迁移
  - `tests/unit/test_notification_service.py` — 新增 template substitution 测试 cases
  - `tests/unit/test_admin_notifications.py` — admin 路由端点测试

### 2.3 缺什么

- [ ] `vars` JSONB 列不存在，模板无法声明支持哪些变量
- [ ] `send_from_template()` 方法不存在，无法按模板发送含变量的通知
- [ ] `GET /admin/notifications/logs` 端点不存在，管理员无法查看发送历史
- [ ] `GET /admin/templates` 端点不存在，管理员无法列出模板
- [ ] `POST /admin/templates` 端点不存在，管理员无法创建模板
- [ ] `DELETE /admin/templates/{id}` 端点不存在，管理员无法删除模板（推荐实现）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/api/routers/admin_notifications.py` | Admin 通知管理路由，含 logs 列表和 templates CRUD |
| `alembic/versions/<id>_add_vars_to_notification_templates.py` | 迁移：在 `notification_templates` 表添加 `vars` JSONB 列 |
| `tests/unit/test_admin_notifications.py` | Admin 路由单元测试（mock service，验证端点行为） |
| `tests/unit/test_notification_service.py` | 新增 template substitution 测试 cases（现有文件扩写） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/notification_service.py`](../../../src/services/notification_service.py) | 新增 `send_from_template()` 方法；新增 `get_templates()`、`create_template()`、`delete_template()` |
| [`src/db/models/notification_template.py`](../../../src/db/models/notification_template.py) | 新增 `vars: Mapped[dict | None]` JSONB 列，升级 `to_dict()` 输出 vars 字段 |
| [`src/main.py`](../../../src/main.py) | 注册 `admin_notifications_router`（挂载至 `/admin` 路径） |

### 3.3 新增能力

- **Service method**：`NotificationService.send_from_template(self, template_id: int, user_id: int, vars: dict, tenant_id: int) -> NotificationModel`
- **Service method**：`NotificationService.get_templates(self, tenant_id: int, page: int, page_size: int) -> tuple[list[NotificationTemplateModel], int]`
- **Service method**：`NotificationService.create_template(self, data: dict, tenant_id: int) -> NotificationTemplateModel`
- **Service method**：`NotificationService.delete_template(self, template_id: int, tenant_id: int) -> dict`
- **API endpoint**：`GET /admin/notifications/logs` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`GET /admin/templates` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`POST /admin/templates` → `{"success": true, "data": {...}}`
- **API endpoint**：`DELETE /admin/templates/{template_id}` → `{"success": true, "data": {"id": N}}`
- **ORM model**：`NotificationTemplateModel.vars: Mapped[dict | None]`（JSONB）
- **Migration**：`alembic upgrade head` 添加 `vars` 列到 `notification_templates`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **vars 选 JSONB 而非单独关联表**：模板变量个数不固定（可能 2 个也可能 10 个），JSONB 支持灵活 Schema，无需 migration 变更即可增删变量定义。与本项目 `ChurnPredictionModel.event_metadata`（JSONB）的处理方式一致。
- **占位符替换选 `str.replace()` 简单实现，不引入 Jinja2**：当前阶段模板变量简单（`{{var}}` 替换），引入 Jinja2 会增加测试复杂度和外部依赖。后续如需条件判断/循环，再升级为 Jinja2。
- **admin 路由独立注册到 `/admin` 前缀**：与现有 `rbac_router`（`/rbac`）、`reports_router`（`/reports`）保持一致的风格，admin 专属路径便于 Nginx 层做权限隔离。

### 4.2 版本约束

无新增外部依赖（Python 标准库 `str.replace` 实现占位符替换）。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- Router 中 session 使用 `Depends(get_db)`，不使用 `async with get_db()`
- 禁止在 ORM 模型列名中使用 `metadata`（与 `Base.metadata` 冲突）→ 本板块 vars 字段不冲突

### 4.4 已知坑

1. **Alembic autogen 把 JSONB 写成 JSON** → 规避：迁移文件中手动将 `sa.JSON()` 改为 `sa.JSONB()`，`created_at` 列保持 `DateTime(timezone=True)` 而非 `DateTime`
2. **Jinja2 占位符 `{{` 在 HTML body 中与浏览器 JS 框架冲突** → 规避：本板块仅替换文本变量，不做完整 Jinja2 渲染；HTML 模板中的 JS 框架使用 `${}` 语法避免冲突（在业务层面约束）
3. **vars 字段为 JSONB，可为 null 或空 dict `{}`** → 规避：`send_from_template()` 中对 `vars is None` 按空 dict 处理：`vars or {}`

---

## 5. 实现步骤（按顺序）

### Step 1: 在 NotificationTemplateModel 添加 vars JSONB 列

参考 CLAUDE.md §Alembic Migrations，用独立 disposable DB 生成迁移。

操作：
- a) 在 `src/db/models/notification_template.py` 的 `NotificationTemplateModel` 类中，`created_at` 字段后添加：

```python
    vars: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- b) 更新 `to_dict()` 方法，追加 `"vars": self.vars` 字段输出。

完整改动后模型片断：

```python
from sqlalchemy import JSONB

class NotificationTemplateModel(Base):
    __tablename__ = "notification_templates"
    # ... existing fields ...
    vars: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "channel": self.channel,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "vars": self.vars,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`ruff check src/db/models/notification_template.py` → 0 errors

---

### Step 2: 生成 Alembic 迁移脚本（vars 列）

操作：
- a) 启动数据库容器：
  ```bash
  docker compose -f configs/docker-compose.test.yml up -d test-db
  ```
- b) 重置独立数据库：
  ```bash
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
  ```
- c) 将数据库升至最新迁移头：
  ```bash
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head
  ```
- d) 生成迁移 diff：
  ```bash
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic revision --autogenerate -m "add_vars_to_notification_templates"
  ```
- e) 审查 `alembic/versions/<id>_add_vars_to_notification_templates.py`：
  - 确认 `vars` 列为 `sa.JSONB()` 而非 `sa.JSON()`
  - 确认 `nullable=True`
  - 确认 `down_revision` 指向当前最新迁移
- f) 验证迁移双向可用：
  ```bash
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic downgrade -1
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head
  ```

**完成判定**：三次命令均 exit 0；第二次 autogenerate 产生空迁移

---

### Step 3: 在 NotificationService 添加 send_from_template() 及模板 CRUD 方法

操作：
- a) 在 `src/services/notification_service.py` 顶部添加导入：
  ```python
  from sqlalchemy import JSONB
  from db.models.notification_template import NotificationTemplateModel
  ```
- b) 在 `NotificationService` 类中添加以下方法：

```python
def _substitute_vars(self, text: str | None, vars_dict: dict) -> str | None:
    """Replace {{key}} placeholders in text with vars_dict values."""
    if not text:
        return text
    result = text
    for key, val in (vars_dict or {}).items():
        result = result.replace("{{" + key + "}}", str(val))
    return result

async def send_from_template(
    self,
    template_id: int,
    user_id: int,
    vars_dict: dict,
    tenant_id: int = 0,
) -> NotificationModel:
    """Fetch template by id, substitute vars into subject/body, then send notification."""
    result = await self.session.execute(
        select(NotificationTemplateModel).where(
            and_(
                NotificationTemplateModel.id == template_id,
                NotificationTemplateModel.tenant_id == tenant_id,
            )
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise NotFoundException("通知模板")
    subject = self._substitute_vars(template.subject, vars_dict)
    content = self._substitute_vars(
        template.body_text or template.body_html, vars_dict
    )
    return await self.send_notification(
        user_id=user_id,
        notification_type=f"template:{template.channel}",
        title=subject or "(无主题)",
        content=content or "",
        tenant_id=tenant_id,
    )

async def get_templates(
    self,
    tenant_id: int = 0,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[NotificationTemplateModel], int]:
    """List notification templates for tenant."""
    conditions = [NotificationTemplateModel.tenant_id == tenant_id]
    count_result = await self.session.execute(
        select(func.count(NotificationTemplateModel.id)).where(and_(*conditions))
    )
    total = count_result.scalar_one()
    offset = (page - 1) * page_size
    result = await self.session.execute(
        select(NotificationTemplateModel)
        .where(and_(*conditions))
        .order_by(NotificationTemplateModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return result.scalars().all(), total

async def create_template(
    self,
    name: str,
    channel: str,
    tenant_id: int = 0,
    subject: str | None = None,
    body_html: str | None = None,
    body_text: str | None = None,
    vars_dict: dict | None = None,
) -> NotificationTemplateModel:
    """Create a new notification template."""
    template = NotificationTemplateModel(
        tenant_id=tenant_id,
        name=name,
        channel=channel,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        vars=vars_dict,
    )
    self.session.add(template)
    await self.session.flush()
    await self.session.refresh(template)
    return template

async def delete_template(self, template_id: int, tenant_id: int = 0) -> dict:
    """Delete a notification template by id."""
    result = await self.session.execute(
        delete(NotificationTemplateModel).where(
            and_(
                NotificationTemplateModel.id == template_id,
                NotificationTemplateModel.tenant_id == tenant_id,
            )
        )
    )
    if (result.rowcount or 0) == 0:
        raise NotFoundException("通知模板")
    await self.session.flush()
    return {"id": template_id}
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

---

### Step 4: 创建 admin_notifications.py 路由文件

操作：
- 创建 `src/api/routers/admin_notifications.py`，内容如下：

```python
"""Admin notifications router — /admin/notifications/logs and /admin/templates endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router wraps service return values in success envelopes.
"""

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.notification_service import NotificationService

admin_notifications_router = APIRouter(prefix="/admin", tags=["admin-notifications"])


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    channel: str = Field(..., min_length=1, max_length=20)
    subject: str | None = Field(None, max_length=255)
    body_html: str | None = None
    body_text: str | None = None
    vars: dict | None = None


@admin_notifications_router.get(
    "/notifications/logs",
    summary="Admin: list all notification logs",
)
async def list_notification_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Admin: paginated list of all notification logs for the tenant."""
    svc = NotificationService(session)
    # NotificationLogModel 已在 #664 定义，此处复用其查询
    from db.models.notification_log import NotificationLogModel
    from sqlalchemy import and_, func, select

    conditions = [NotificationLogModel.tenant_id == ctx.tenant_id]
    count_result = await session.execute(
        select(func.count(NotificationLogModel.id)).where(and_(*conditions))
    )
    total = count_result.scalar_one()
    offset = (page - 1) * page_size
    result = await session.execute(
        select(NotificationLogModel)
        .where(and_(*conditions))
        .order_by(NotificationLogModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {
        "success": True,
        "data": {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@admin_notifications_router.get(
    "/templates",
    summary="Admin: list notification templates",
)
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Admin: paginated list of notification templates."""
    svc = NotificationService(session)
    items, total = await svc.get_templates(
        tenant_id=ctx.tenant_id, page=page, page_size=page_size
    )
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": [t.to_dict() for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@admin_notifications_router.post(
    "/templates",
    summary="Admin: create a notification template",
)
async def create_template(
    body: TemplateCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Admin: create a new notification template."""
    svc = NotificationService(session)
    template = await svc.create_template(
        name=body.name,
        channel=body.channel,
        tenant_id=ctx.tenant_id,
        subject=body.subject,
        body_html=body.body_html,
        body_text=body.body_text,
        vars_dict=body.vars,
    )
    return {"success": True, "data": template.to_dict(), "message": "模板创建成功"}


@admin_notifications_router.delete(
    "/templates/{template_id}",
    summary="Admin: delete a notification template",
)
async def delete_template(
    template_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Admin: delete a notification template by id."""
    svc = NotificationService(session)
    result = await svc.delete_template(template_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result, "message": "模板已删除"}
```

- b) 在 `src/main.py` 中注册路由（查找 `include_router` 调用，在 router 注册区添加）：

在文件顶部（已有导入）：
```python
from api.routers.admin_notifications import admin_notifications_router
```

在 router 注册区（已有 `app.include_router(...)` 调用的位置）：
```python
app.include_router(admin_notifications_router)
```

**完成判定**：`ruff check src/api/routers/admin_notifications.py src/main.py` → 0 errors

---

### Step 5: 编写单元测试

操作：
- a) 扩展 `tests/unit/test_notification_service.py`（文件已存在），添加以下测试 cases：

```python
class TestSendFromTemplate:
    @pytest.fixture
    def svc(self, mock_db_session):
        return NotificationService(mock_db_session)

    def test_substitute_vars_replaces_placeholders(self, svc):
        result = svc._substitute_vars("Hello {{name}}, your order #{{order_id}} is ready", {"name": "Alice", "order_id": "123"})
        assert result == "Hello Alice, your order #123 is ready"

    def test_substitute_vars_returns_none_if_text_none(self, svc):
        assert svc._substitute_vars(None, {"name": "Bob"}) is None

    def test_substitute_vars_handles_missing_keys(self, svc):
        result = svc._substitute_vars("Hello {{name}}", {})
        assert result == "Hello {{name}}"

    def test_send_from_template_raises_if_template_not_found(self, svc, mock_db_session):
        # mock session returns no template
        with pytest.raises(NotFoundException):
            # Note: actual test needs proper mock for select() call
            pass  # placeholder — implement with make_mock_session handlers
```

- b) 创建 `tests/unit/test_admin_notifications.py`：

```python
"""Unit tests for admin_notifications router."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from api.routers.admin_notifications import admin_notifications_router
from services.notification_service import NotificationService
from db.models.notification_template import NotificationTemplateModel


class TestAdminNotificationsRouter:
    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_ctx(self):
        ctx = MagicMock()
        ctx.tenant_id = 1
        ctx.user_id = 1
        return ctx

    @pytest.mark.asyncio
    async def test_create_template_returns_envelope(self, mock_session, mock_ctx):
        # Mock NotificationService.create_template to return a fake template
        template = NotificationTemplateModel(
            id=1, tenant_id=1, name="welcome", channel="email",
            subject="Hello", body_html=None, body_text=None, vars=None
        )
        with patch("api.routers.admin_notifications.get_db", return_value=mock_session):
            with patch("api.routers.admin_notifications.require_auth", return_value=mock_ctx):
                with patch.object(NotificationService, "create_template", new_callable=AsyncMock) as mock_create:
                    mock_create.return_value = template
                    # ... full integration test via httpx AsyncClient ...
                    pass  # placeholder — implement with TestClient fixture
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_service.py tests/unit/test_admin_notifications.py -v` → ≥ 8 passed（5 existing + 3 new）

---

### Step 6: Drift check + lint 终检

操作：
```bash
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic revision --autogenerate -m "drift_check"
```
检查生成的迁移仅含 `pass` in both up/down。

```bash
ruff check src/db/models/notification_template.py src/services/notification_service.py src/api/routers/admin_notifications.py src/main.py
```

全部 exit 0。

**完成判定**：drift check 空迁移 + ruff 检查全 0 errors

---

## 6. 验收

- [ ] `ruff check src/db/models/notification_template.py src/services/notification_service.py src/api/routers/admin_notifications.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → ≥ 5 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_admin_notifications.py -v` → ≥ 3 passed
- [ ] `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head` → exit 0
- [ ] `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic downgrade -1` → exit 0
- [ ] `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head` → exit 0
- [ ] `alembic revision --autogenerate -m "drift_check"` → 空迁移（up/down 均仅 `pass`）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 模板 body_html 含 `{{` 但并非占位符（与 JS 框架冲突） | 低 | 低 | 文档约束模板编写规范，禁止在 HTML 中使用 `{{` 语法；如出现，运行 `UPDATE notification_templates SET vars=null WHERE ...` 回退 |
| migration 后 vars 列默认值不一致导致空模板查询异常 | 低 | 中 | `vars` 列声明 `nullable=True`，默认值由 DB NULL 而非空 dict 填充；`send_from_template` 中对 `vars or {}` 保证空值安全 |
| admin router 注册顺序导致路径冲突（`/admin` 前缀与其他路由重叠） | 低 | 高 | 在 `main.py` 中将 `admin_notifications_router` 注册在其他 router 之前；如冲突，切换至 `/api/v1/admin/...` 前缀 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/notification_template.py src/services/notification_service.py src/api/routers/admin_notifications.py src/main.py alembic/versions/<id>_add_vars_to_notification_templates.py tests/unit/test_notification_service.py tests/unit/test_admin_notifications.py
git commit -m "feat(40-campaigns): add notification template CRUD and admin router for #639"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(40-campaigns): add notification template admin endpoints (#639)" --body "Closes #639

## Summary
- Add `vars` JSONB column to NotificationTemplateModel
- Add `send_from_template()` with {{var}} substitution in NotificationService
- Add admin router with GET /admin/notifications/logs, GET/POST/DELETE /admin/templates

## Test plan
- [ ] ruff check 0 errors
- [ ] pytest tests/unit/test_notification_service.py -v → ≥ 5 passed
- [ ] pytest tests/unit/test_admin_notifications.py -v → ≥ 3 passed
- [ ] alembic upgrade/downgrade → exit 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 docs/dev-plan/40-campaigns/0639-add-notification-templates-and-admin-endpoints.md §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/notification_service.py`](../../../src/services/notification_service.py) — 本板块修改的基线文件
- 同类参考实现：[`src/db/models/notification_template.py`](../../../src/db/models/notification_template.py) — #662 的 NotificationTemplateModel，本板块在其上扩展 `vars` 字段
- 同类参考实现：[`src/api/routers/notifications.py`](../../../src/api/routers/notifications.py) — 现有 notifications 路由，本板块 admin 路由参照其 `_paginated_dicts` 工具函数风格
- 同类参考实现：[`src/api/routers/rbac.py`](../../../src/api/routers/rbac.py) — admin 路由注册方式参考
- 第三方文档：[SQLAlchemy JSONB column type](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON) — JSONB 与 JSON 的区别
- 父 issue / 关联：#39 (父), #638 (依赖，无板文档则填「TBD - 待补充：#638 依赖板块板文档尚未创建」), #662 (NotificationTemplateModel 基础), #664 (NotificationLogModel，logs 端点依赖)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |

---

**What changed:** All three occurrences of `../../src/db/models/notification_template.py` were corrected to `../../../src/db/models/notification_template.py`. The document lives in `docs/dev-plan/<category>/`, so three `../` are needed to reach the project root (not two). All other links in the file already use the correct `../../../src/` pattern, confirming this was the right fix.
