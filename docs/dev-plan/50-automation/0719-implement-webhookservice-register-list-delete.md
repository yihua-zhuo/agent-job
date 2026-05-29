# WebhookService · 实现 register / list / delete 三合一

| 元数据 | 值 |
|---|---|
| Issue | #719 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0718 - 添加重试调度列到 WebhookDeliveryModel](0718-add-retry-scheduling-columns-to-webhookdeliverymodel-and-mig.md) |
| 启用后赋能 | [0720 - 实现 HMAC 签名与投递](0720-implement-webhookdeliveryservice-hmac-signing-post-delivery.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统需要向外部系统分发事件通知（客户创建、商机状态变更、工单关闭等），但目前没有统一的 Webhook 管理机制。缺少 `WebhookService` 导致：
- 事件消费者无法注册感兴趣的 webhook endpoint
- 没有办法列出给定租户已注册的 webhook
- 没有安全的删除（软删）接口，存量数据无法清理

`WebhookService` 是 webhook 分发链路的起点，上游（事件触发）和下游（delivery + retry）都依赖它。

### 1.2 做完后

- **用户视角**：管理员可以在 CRM 中注册一个 webhook URL，指定感兴趣的事件类型，系统记住这个订阅关系；也可以查看和删除已注册的 webhook。
- **开发者视角**：`WebhookService` 是一个标准的领域 service，遵循 `__init__(session: AsyncSession)` 模式，返回 `WebhookModel` ORM 对象，错误时抛 `AppException` 子类，无需调用 `.to_dict()`。

### 1.3 不做什么（剔除）

- [ ] Webhook delivery（实际 HTTP POST 到 endpoint）不在本板块——属于 #720 WebhookDeliveryService
- [ ] HMAC 签名不在本板块——属于 #720
- [ ] 重试 / 指数退避不在本板块——属于 #721 BackgroundRetryScheduler
- [ ] WebhookModel 本身不在本板块——属于依赖项 #718

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → ≥ 6 passed（每个方法至少 2 个用例）
- `PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v` → 全 passed
- `ruff check src/services/webhook_service.py` → 0 errors
- `ruff check tests/unit/test_webhook_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/` 下是否有 `webhook.py` 及 `WebhookModel`（由 #718 创建）

```python:src/db/models/webhook.py（预期结构，由 #718 提供）
# TBD — #718 完成后补充具体 schema
class WebhookModel(Base):
    __tablename__ = "webhooks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    events: Mapped[List[str]] = mapped_column(JSONB, nullable=False)  # 或 ARRAY[String]
    secret: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
```

### 2.2 涉及文件清单

- 要改：无
- 要建：
  - `src/services/webhook_service.py` — WebhookService 核心实现
  - `tests/unit/test_webhook_service.py` — 单元测试（mock session）
  - `tests/integration/test_webhook_service_integration.py` — 集成测试（真实 DB）

### 2.3 缺什么

- [ ] `WebhookService` 类本身不存在
- [ ] 没有 `register_webhook` 方法（URL scheme + events 非空校验缺失）
- [ ] 没有 `list_webhooks` 方法（按 tenant_id 过滤查询缺失）
- [ ] 没有 `delete_webhook` 方法（软删 + NotFoundException 缺失）
- [ ] 没有对应的单元测试覆盖率

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| [`src/services/webhook_service.py`](../../src/services/webhook_service.py) | WebhookService：register / list / delete 三个方法 |
| [`tests/unit/test_webhook_service.py`](../../tests/unit/test_webhook_service.py) | 单元测试，使用 mock session + MockState |
| [`tests/integration/test_webhook_service_integration.py`](../../tests/integration/test_webhook_service_integration.py) | 集成测试，真实 Postgres + db_schema fixture |

### 3.2 修改文件

（无修改文件）

### 3.3 新增能力

- **Service method**：`WebhookService.register_webhook(tenant_id: int, url: str, events: list[str], secret: str | None) -> WebhookModel` — 校验 URL scheme（http/https）+ events 非空，INSERT 并 flush
- **Service method**：`WebhookService.list_webhooks(tenant_id: int) -> list[WebhookModel]` — WHERE is_active=True AND tenant_id=:tenant_id，返回 ORM 对象列表
- **Service method**：`WebhookService.delete_webhook(webhook_id: int, tenant_id: int) -> WebhookModel` — 软删 is_active=False，NotFoundException 如不存在
- **API endpoint（不在本板块）**：在 router 层调用上述 service，由后续板块补充

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **软删不选硬删**：删除操作使用 `is_active=False` 而非 `DELETE`，保留审计线索；如需真正清理，用 `is_active=False` 标记，由 DB retention policy 处理。
- **URL 校验仅校验 scheme**：不校验域名可达性（DNS/网络不可控）；仅要求以 `http://` 或 `https://` 开头。
- **secret 在 service 层接受但不使用**：HMAC 签名在 #720 WebhookDeliveryService 中实现；本 service 仅存储明文 secret 供 downstream 使用。

### 4.2 版本约束

（无新增依赖）

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`；禁止全局查询
- Service 层不调用 `.to_dict()`，返回 ORM 对象；序列化由 router 负责
- Service 层不返回 `ApiResponse`，错误时抛 `AppException` 子类
- `session.flush()` 用于 INSERT 后立即获取自增 ID，不等待 commit

### 4.4 已知坑

1. **Alembic autogenerate 生成 `sa.JSON()` 而非 `sa.JSONB()`** → 规避：手动将 `JSON()` 改为 `JSONB()`，并在 migration 中加 `server_default='[]'` 让空数组有类型
2. **`metadata` 列名与 `Base.metadata` 冲突** → 规避：Webhooks 表若有 metadata 列，改用 `event_metadata` / `payload` / `attrs` 等名称；目前 WebhookModel Schema 由 #718 定义，需确认未使用 `metadata`
3. **PYTHONPATH=src，import 路径不带 `src.` 前缀** → 规避：`from db.models.webhook import WebhookModel`，**不是** `from src.db.models.webhook import WebhookModel`
4. **Async session 不要用 `async with get_db()`** → 规避：router 层用 `session: AsyncSession = Depends(get_db)` 注入；service 层不要自己打开 session

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/webhook_service.py`

在 `src/services/` 下新建 `webhook_service.py`，实现 `WebhookService` 类骨架：

```python:src/services/webhook_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from db.models.webhook import WebhookModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException

class WebhookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register_webhook(
        self,
        tenant_id: int,
        url: str,
        events: list[str],
        secret: str | None = None,
    ) -> WebhookModel:
        # URL scheme 校验：只接受 http / https
        if not url.startswith(("http://", "https://")):
            raise ValidationException("Webhook URL must start with http:// or https://")
        # events 非空校验
        if not events:
            raise ValidationException("Events list must not be empty")
        # INSERT + flush
        webhook = WebhookModel(
            tenant_id=tenant_id,
            url=url,
            events=events,
            secret=secret,
            is_active=True,
        )
        self.session.add(webhook)
        await self.session.flush()
        return webhook

    async def list_webhooks(self, tenant_id: int) -> list[WebhookModel]:
        stmt = select(WebhookModel).where(
            WebhookModel.tenant_id == tenant_id,
            WebhookModel.is_active == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_webhook(self, webhook_id: int, tenant_id: int) -> WebhookModel:
        stmt = (
            update(WebhookModel)
            .where(
                WebhookModel.id == webhook_id,
                WebhookModel.tenant_id == tenant_id,
                WebhookModel.is_active == True,
            )
            .values(is_active=False)
            .returning(WebhookModel)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundException("Webhook")
        # 软删返回的对象 is_active 已为 False
        return row
```

**完成判定**：`ruff check src/services/webhook_service.py` → 0 errors

---

### Step 2: 创建单元测试 `tests/unit/test_webhook_service.py`

参照 `tests/unit/conftest.py` 的 `make_mock_session` + `MockState` 模式，新建 `test_webhook_service.py`：

```python:tests/unit/test_webhook_service.py（骨架）
import pytest
from unittest.mock import AsyncMock
from services.webhook_service import WebhookService
from pkg.errors.app_exceptions import NotFoundException, ValidationException
from tests.unit.conftest import MockState, make_mock_session, make_webhook_handler

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_webhook_handler(state)])

@pytest.fixture
def webhook_service(mock_db_session):
    return WebhookService(mock_db_session)

class TestRegisterWebhook:
    async def test_register_valid_https(self, webhook_service, mock_db_session):
        result = await webhook_service.register_webhook(
            tenant_id=1, url="https://example.com/hook", events=["customer.created"], secret="s3cr3t"
        )
        assert result.url == "https://example.com/hook"
        assert result.is_active is True

    async def test_rejects_http(self, webhook_service):
        with pytest.raises(ValidationException) as exc:
            await webhook_service.register_webhook(tenant_id=1, url="ftp://bad.com", events=["x"])
        assert "http:// or https://" in str(exc.value)

    async def test_rejects_empty_events(self, webhook_service):
        with pytest.raises(ValidationException) as exc:
            await webhook_service.register_webhook(tenant_id=1, url="https://x.com", events=[])
        assert "must not be empty" in str(exc.value)

class TestListWebhooks:
    async def test_list_filters_by_tenant(self, webhook_service):
        webhooks = await webhook_service.list_webhooks(tenant_id=1)
        assert isinstance(webhooks, list)

    async def test_list_returns_only_active(self, webhook_service):
        webhooks = await webhook_service.list_webhooks(tenant_id=1)
        for wh in webhooks:
            assert wh.is_active is True

class TestDeleteWebhook:
    async def test_soft_delete_sets_inactive(self, webhook_service):
        # 先注册，再删除
        created = await webhook_service.register_webhook(1, "https://x.com", ["c"], "s")
        deleted = await webhook_service.delete_webhook(created.id, tenant_id=1)
        assert deleted.is_active is False

    async def test_delete_nonexistent_raises(self, webhook_service):
        with pytest.raises(NotFoundException):
            await webhook_service.delete_webhook(webhook_id=9999, tenant_id=1)
```

> **注意**：如 `conftest.py` 尚无 `make_webhook_handler`，需先在 `conftest.py` 中参照 `make_customer_handler` 新增一个。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → ≥ 6 passed

---

### Step 3: 创建领域专属 handler 文件

在 `tests/unit/domain_handlers/` 下新建 `webhook.py`（不修改共享的 `conftest.py`）：

```python:tests/unit/domain_handlers/webhook.py
from tests.unit.conftest import MockRow, MockResult

def make_webhook_handler(state):
    """state.webhooks: list[dict] with keys id, tenant_id, url, events, secret, is_active"""
    state.webhooks = []
    def handle(method, sql, params=None):
        if method == "insert":
            row = {"id": state.next_id(), **(params or {})}
            state.webhooks.append(row)
            return MockResult([MockRow(row)])
        if method == "select":
            rows = [r for r in state.webhooks if r.get("tenant_id") == params.get("tenant_id")]
            return MockResult([MockRow(r) for r in rows])
        return MockResult([])
    return handle
```

测试文件中引用时：

```python
from tests.unit.domain_handlers.webhook import make_webhook_handler
```

**完成判定**：`ruff check tests/unit/domain_handlers/webhook.py` → 0 errors

---

### Step 4: 创建集成测试 `tests/integration/test_webhook_service_integration.py`

```python:tests/integration/test_webhook_service_integration.py（骨架）
import pytest
from services.webhook_service import WebhookService
from pkg.errors.app_exceptions import NotFoundException, ValidationException

@pytest.mark.integration
class TestWebhookServiceIntegration:
    async def test_register_and_list(self, db_schema, tenant_id, async_session):
        svc = WebhookService(async_session)
        created = await svc.register_webhook(
            tenant_id=tenant_id,
            url="https://example.com/webhook",
            events=["customer.created", "ticket.closed"],
            secret="test_secret",
        )
        assert created.id is not None
        webhooks = await svc.list_webhooks(tenant_id=tenant_id)
        assert len(webhooks) == 1
        assert webhooks[0].url == "https://example.com/webhook"

    async def test_delete_soft_deletes(self, db_schema, tenant_id, async_session):
        svc = WebhookService(async_session)
        created = await svc.register_webhook(tenant_id, "https://x.com", ["c"], None)
        deleted = await svc.delete_webhook(created.id, tenant_id=tenant_id)
        assert deleted.is_active is False
        # list 不返回已删除
        remaining = await svc.list_webhooks(tenant_id=tenant_id)
        assert len(remaining) == 0

    async def test_delete_unknown_raises(self, db_schema, tenant_id, async_session):
        svc = WebhookService(async_session)
        with pytest.raises(NotFoundException):
            await svc.delete_webhook(webhook_id=123456, tenant_id=tenant_id)
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/services/webhook_service.py` → 0 errors
- [ ] `ruff check tests/unit/test_webhook_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → ≥ 6 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如 #718 包含 migration，需确认）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #718 WebhookModel schema 与 service 期望不一致（如 column 名不同、缺少 is_active 等） | 中 | 高 | 在 `webhook_service.py` 中用 `hasattr` 防御，或在 Step 1 前先确认 #718 模型；不影响下游板块，service 层可延迟合并 |
| `make_webhook_handler` mock 与真实 DB 行为不符（e.g. JSONB 序列化差异） | 低 | 中 | 直接运行集成测试覆盖，单元测试降级为 "仅验证方法签名" |
| #718 尚未完成导致 `from db.models.webhook` import 失败 | 中 | 中 | 先完成 #718 再合并本 PR；PR 保持 Draft 状态直到上游合入 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/webhook_service.py \
       tests/unit/test_webhook_service.py \
       tests/integration/test_webhook_service_integration.py \
       tests/unit/conftest.py  # 如有新增 handler
git commit -m "feat(webhooks): implement WebhookService with register/list/delete"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(webhooks): implement WebhookService" --body "Closes #719"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — 标准 service 模式（`__init__(session)`, `tenant_id` 过滤, ORM 返回）
- 父 issue / 关联：#496（webhook 系统父 epic）、#718（WebhookModel，依赖项）
- 错误处理规范：[`pkg/errors/app_exceptions.py`](../../pkg/errors/app_exceptions.py) — `NotFoundException` / `ValidationException` 定义

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
