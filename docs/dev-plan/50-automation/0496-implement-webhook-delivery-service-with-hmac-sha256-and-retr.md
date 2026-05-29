# Webhook · 实现 HMAC-SHA256 签名 + 重试的投递服务

| 元数据 | 值 |
|---|---|
| Issue | #496 |
| 分类 | 50-automation |
| 优先级 | 推荐 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0495-add-webhook-models](../0495-add-webhook-models.md) |
| 启用后赋能 | 新建 WebhookRouter 端点（下一板块） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统需要将业务事件（客户创建、工单变更、交易完成等）实时推送给租户的外部系统。现阶段（#495 已建立 webhook model 骨架）仅有模型定义，缺少：
- 按租户注册/查询/删除 webhook 的 Service 层
- 将事件内容签名（HMAC-SHA256）并 POST 到目标 URL 的投递逻辑
- 投递失败时按指数退避（1m → 5m → 30m → 1h → 24h）自动重试的后台任务机制

不做投递服务，外部系统无法真正消费 CRM 事件，webhook 功能只是空壳。

### 1.2 做完后

- **用户视角**：无直接可见变化 — 纯后台服务层
- **开发者视角**：
  - 可调用 `WebhookService` 按 `tenant_id` 注册、列举、删除 webhook
  - 可调用 `WebhookDeliveryService.deliver()` 将事件签名并发送至目标 URL
  - 投递失败时后台任务自动按指数退避重试，无需人工介入
  - 投递结果记录在 `webhook_delivery` 表，可溯源

### 1.3 不做什么（剔除）

- [ ] 不添加任何 HTTP Router 端点（router 放下一板块）
- [ ] 不实现 webhook 更新（`update_webhook`）接口，仅 CRUD 中的 C/R/D
- [ ] 不实现事件过滤（哪些事件类型要推送，由调用方在 `deliver()` 时指定）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → 全 passed
- `PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v` → 全 passed
- `ruff check src/services/webhook_service.py src/services/webhook_delivery_service.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：issue #495 完成后的 webhook ORM model 定义，预计位于 `src/db/models/` 下，表名 `webhook` 和 `webhook_delivery`，含字段 `tenant_id`, `url`, `events`（JSONB）, `secret`, `is_active` 等

### 2.2 涉及文件清单

- 要改：
  - 暂无（#495 完成后 model 即存在，本板块不修改已有文件）
- 要建：
  - `src/services/webhook_service.py` — WebhookService（注册/查询/删除）
  - `src/services/webhook_delivery_service.py` — WebhookDeliveryService（签名投递 + 重试）
  - `src/db/models/webhook.py` — ORM model（#495 已建，本板块引用；如不存在则新建）
  - `alembic/versions/<id>_add_webhook_and_delivery_tables.py` — migration（#495 已建则跳过）
  - `tests/unit/test_webhook_service.py` — mock HTTP 单元测试
  - `tests/integration/test_webhook_service_integration.py` — 真实 DB 集成测试

### 2.3 缺什么

- [ ] WebhookService：按 tenant_id 隔离的 register / list / delete 操作
- [ ] WebhookDeliveryService：HMAC-SHA256 签名计算逻辑
- [ ] WebhookDeliveryService：httpx 异步 POST 投递（Content-Type: application/json）
- [ ] WebhookDeliveryService：投递失败时创建 `webhook_delivery` 记录（status=failed, retry_count）
- [ ] 后台指数退避重试调度：1m → 5m → 30m → 1h → 24h 共 5 次重试
- [ ] 单元测试：mock httpx.AsyncClient，不发真实 HTTP 请求
- [ ] 集成测试：真实 PostgreSQL + aiosqlite 或 docker compose test-db

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/webhook_service.py` | WebhookService：register_webhook / list_webhooks / delete_webhook |
| `src/services/webhook_delivery_service.py` | WebhookDeliveryService：deliver() 签名 + 投递 + 重试调度 |
| `src/db/models/webhook.py` | WebhookModel + WebhookDeliveryModel ORM（#495 已建则本行跳过） |
| `alembic/versions/<id>_add_webhook_tables.py` | 创建 webhook + webhook_delivery 表 migration（#495 已建则跳过） |
| `tests/unit/test_webhook_service.py` | 单元测试（mock httpx.AsyncClient） |
| `tests/integration/test_webhook_service_integration.py` | 集成测试（真实 DB，docker compose test-db） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/webhook.py` | 若 #495 未完成，需新增 WebhookModel + WebhookDeliveryModel（含 tenant_id 索引） |
| `alembic/env.py` | 需 import 新 webhook model 以供 alembic --autogenerate 识别 |

### 3.3 新增能力

- **Service class**：`WebhookService(session: AsyncSession)` — register / list / delete 三个公开方法
- **Service class**：`WebhookDeliveryService(session: AsyncSession)` — `deliver(event_type, payload, tenant_id)` 核心方法
- **HMAC-SHA256 签名**：请求 header `X-Webhook-Signature: sha256=<hex_digest>`，payload 为 request body UTF-8 bytes
- **重试调度**：后台 async 任务，延迟队列 1m → 5m → 30m → 1h → 24h（最大 5 次重试）
- **ORM model**：`WebhookModel`（webhook 表）+ `WebhookDeliveryModel`（投递记录表）
- **Migration**：创建 webhook + webhook_delivery 表（含 tenant_id 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `httpx.AsyncClient` 不选 `aiohttp`**：httpx API 更简洁，且同时支持 HTTP/1.1 和 HTTP/2；本项目其他异步 HTTP 调用若已有先例则跟随，本板块为新建以 httpx 为准
- **选数据库轮询调度重试不选外部队列（Celery/RQ）**：避免引入新 broker 依赖；重试次数少（≤5 次）且间隔长，数据库 + asyncio.sleep 足矣
- **选 JSONB 而非 ARRAY 存储 events 列表**：SQLite（集成测试）不支持 PostgreSQL ARRAY 类型；JSONB 跨数据库兼容，更简单
- **选幂等投递（记录 delivery 行）不选乐观锁**：每次 deliver 调用插入一条 `webhook_delivery` 行（含 uuid / retry_count），可追溯；不依赖外侧事务

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `httpx` | `>=0.27.0` | async client，需支持 `AsyncClient.aclose()` 生命周期管理 |

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- ORM model 列名不能用 `metadata`（与 `Base.metadata` 冲突）→ 用 `event_payload` / `delivery_metadata` 等
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；`.to_dict()` 由 router 负责（本板块无 router 但遵循惯例）
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- 异步 session 通过 `session: AsyncSession = Depends(get_db)` 注入，**不用** `async with get_db() as session:`

### 4.4 已知坑

1. **SQLAlchemy `metadata` 列名冲突** → 症状：类定义时 `AttributeError: 'WebhokModel' object has no attribute 'metadata'` → 规避：ORM 列名统一用 `event_payload`、`response_metadata`、`config_metadata` 等代替 `metadata`
2. **Alembic autogenerate 把 JSONB 写成 JSON** → 症状：迁移后 PostgreSQL 列类型为 JSON 而非 JSONB，功能无错误但查询性能差异可能被忽略 → 规避：生成 migration 后手动将 `sa.JSON()` 改回 `sa.JSONB()`
3. **Alembic autogenerate 丢失 `timezone=True`** → 症状：timestamp 列变成 `DateTime()` 而非 `DateTime(timezone=True)` → 规避：生成后检查并补上 `timezone=True`
4. **集成测试并发 session 冲突** → 症状：`AsyncSession` 在同一事务中被复用导致 `InvalidRequestError` → 规避：每个测试函数使用 function-scoped fixture，共享 session 时明确 `async_session.begin_nested()` 嵌套事务

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 / 确认 Webhook ORM Model

在 `src/db/models/webhook.py` 中定义（或确认 #495 已定义）两个模型：

WebhookModel（webhook 注册表）：
```python
from sqlalchemy import String, Boolean, JSONB, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base

class WebhookModel(Base):
    __tablename__ = "webhook"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    events: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)  # ["customer.created", ...]
    secret: Mapped[str] = mapped_column(String(512), nullable=False)  # HMAC 签名密钥
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (Index("ix_webhook_tenant_active", "tenant_id", "is_active"),)

    deliveries: Mapped[list["WebhookDeliveryModel"]] = relationship(back_populates="webhook")
```

WebhookDeliveryModel（投递记录表）：
```python
class WebhookDeliveryModel(Base):
    __tablename__ = "webhook_delivery"
    id: Mapped[int] = mapped_column(primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhook.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(256), nullable=False)
    event_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # 不叫 metadata 避免冲突
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # "pending" | "success" | "failed"
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    webhook: Mapped["WebhookModel"] = relationship(back_populates="deliveries")
    __table_args__ = (Index("ix_delivery_webhook_id", "webhook_id"), Index("ix_delivery_next_retry", "next_retry_at", postgresql_where=next_retry_at.is_(None) == False))
```

**完成判定**：`ruff check src/db/models/webhook.py` → 0 errors；文件存在

---

### Step 2: 编写 WebhookService（register / list / delete）

新建 `src/services/webhook_service.py`：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models.webhook import WebhookModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException

class WebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_webhook(
        self,
        tenant_id: int,
        url: str,
        events: list[str],
        secret: str,
    ) -> WebhookModel:
        if not url.startswith("https://") and not url.startswith("http://"):
            raise ValidationException("Webhook URL must use https or http")
        if not events:
            raise ValidationException("At least one event type is required")
        model = WebhookModel(tenant_id=tenant_id, url=url, events=events, secret=secret)
        self.session.add(model)
        await self.session.flush()
        return model

    async def list_webhooks(self, tenant_id: int) -> list[WebhookModel]:
        result = await self.session.execute(
            select(WebhookModel).where(WebhookModel.tenant_id == tenant_id, WebhookModel.is_active == True)
        )
        return list(result.scalars().all())

    async def delete_webhook(self, webhook_id: int, tenant_id: int) -> None:
        result = await self.session.execute(
            select(WebhookModel).where(WebhookModel.id == webhook_id, WebhookModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise NotFoundException("Webhook")
        model.is_active = False
        await self.session.flush()
```

**完成判定**：`ruff check src/services/webhook_service.py` → 0 errors

---

### Step 3: 编写 WebhookDeliveryService（签名 + 投递 + 重试）

新建 `src/services/webhook_delivery_service.py`：

关键逻辑：
- `deliver(event_type, payload, tenant_id)` — 查询该 tenant 所有订阅该 event_type 的 active webhook，逐一投递
- 签名：构造 `HMAC.new(secret.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()`，header `X-Webhook-Signature: sha256=<hex>`
- 投递：异步 POST，Content-Type: application/json，超时 30s
- 记录：`WebhookDeliveryModel` 插入 status=success/failed，重试次数
- 失败时计算 `next_retry_at`（当前时间 + 延迟），插入 `status="pending"` 行供调度器消费

指数退避延迟常量：
```python
RETRY_DELAYS = [
    timedelta(minutes=1),    # 第 1 次重试：1m
    timedelta(minutes=5),    # 第 2 次重试：5m
    timedelta(minutes=30),  # 第 3 次重试：30m
    timedelta(hours=1),     # 第 4 次重试：1h
    timedelta(hours=24),    # 第 5 次重试：24h → 不再重试
]
MAX_RETRIES = 5
```

后台调度：后台任务循环查询 `webhook_delivery WHERE status = 'pending' AND next_retry_at <= now()`，每次取一批（limit 50），逐个执行 POST，超时则重算 `next_retry_at` 或标记 `status='failed'`（已达 MAX_RETRIES）。

**完成判定**：`ruff check src/services/webhook_delivery_service.py` → 0 errors；`PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` 全 passed

---

### Step 4: 编写单元测试（mock HTTP）

新建 `tests/unit/test_webhook_service.py`：

- 使用 `tests/unit/conftest.py` 的 `make_mock_session` 框架
- mock httpx.AsyncClient 的 `post` 方法返回预置的 `httpx.Response`
- 覆盖场景：
  - `test_register_webhook_success` — 正常注册
  - `test_register_webhook_invalid_url` — ValidationException
  - `test_list_webhooks` — 返回正确 tenant 的 webhook
  - `test_delete_webhook_success` — is_active 置 false
  - `test_delete_webhook_not_found` — NotFoundException
  - `test_deliver_success` — POST 返回 200，delivery status=success
  - `test_deliver_failure_then_retry` — POST 返回 500，下次 next_retry_at 在未来
  - `test_deliver_max_retries_exceeded` — retry_count=5，status=failed 不再重试

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → 全 passed

---

### Step 5: 编写集成测试（真实 DB）

新建 `tests/integration/test_webhook_service_integration.py`：

使用 `db_schema`、`tenant_id`、`async_session` fixtures：
- `test_webhook_crud` — register → list → delete → list again（验证 is_active）
- `test_delivery_records_persisted` — 投递后查询 webhook_delivery 表，验证 status / event_type / event_payload 列
- `test_retry_schedules_next_attempt` — mock httpx 抛出 `httpx.TimeoutException`，验证 `next_retry_at` 被正确设置
- `test_tenant_isolation` — 两个不同 tenant_id 的 webhook 互不可见

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v` → 全 passed

---

### Step 6: 生成 / 审核 Alembic Migration

如果 #495 未生成 migration，或本板块新增 delivery 表，执行：

```bash
# 1. 启动干净的 alembic_dev 数据库
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 2. 迁移到当前 head
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head

# 3. 生成新 migration（如有未捕获的 model 变更）
alembic revision --autogenerate -m "add webhook and delivery tables"

# 4. 审核 migration 文件
#    - 确认 webhook 表：url(String), events(JSONB), secret(String), is_active(Boolean)
#    - 确认 webhook_delivery 表：event_payload(JSONB)（不是 metadata），http_status_code(Integer nullable)，next_retry_at(DateTime timezone=True)
#    - 确认所有 tenant_id 列有 index=True
#    - alembic autogen 常见错误：JSON → JSONB；DateTime → DateTime(timezone=True)；缺失 index

# 5. 验证可双向迁移
alembic upgrade head && alembic downgrade -1 && alembic upgrade head

# 6. 如第二步 autogen 产生空迁移（只有 pass），删除它
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 6. 验收

- [ ] `ruff check src/services/webhook_service.py src/services/webhook_delivery_service.py src/db/models/webhook.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] HMAC 签名格式验证：单元测试中 mock response，手动计算签名对比 header 中的 `X-Webhook-Signature`
- [ ] 重试延迟序列验证：单元测试中触发失败，依次检查 5 次重试的 `next_retry_at` 是否符合 `1m → 5m → 30m → 1h → 24h`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| httpx 版本与 FastAPI / uvicorn 依赖冲突（异步连接池管理） | 低 | 高 | 如遇 `RuntimeError: Event loop is closed` 在 shutdown 时，降级为 `aiohttp.ClientSession`，或收紧 httpx 版本 |
| 投递服务因 DB session 过期导致重试任务无法更新 `next_retry_at` | 中 | 中 | 后台任务每次重新 `async with get_db() as session:` 获取新 session，不持有长 session |
| webhook URL 指向的外部服务响应极慢（超时 30s）阻塞后台调度 | 中 | 中 | 使用 `httpx.AsyncClient(timeout=30.0)`，超时即标记失败；不等待 slow response 释放调度槽 |
| JSONB events 列在 SQLite 集成测试环境不支持（ARRAY 是 PG 特有） | 低 | 低 | 改用 JSONB（兼容两者的 text 存储），单元测试用 mock session 跳过 DB 类型检查 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/webhook_service.py src/services/webhook_delivery_service.py src/db/models/webhook.py tests/unit/test_webhook_service.py tests/integration/test_webhook_service_integration.py
git commit -m "feat(automation): implement webhook delivery service with HMAC-SHA256 and retry"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#496): implement webhook delivery service with HMAC-SHA256 and retry" --body "Closes #496"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/services/notification_service.py` — 异步后台任务注册模式参考
- 第三方文档：[httpx AsyncClient](https://www.python-httpx.org/async/), [HMAC Python stdlib](https://docs.python.org/3/library/hmac.html)
- 父 issue / 关联：#78（父 issue），#495（依赖的前置模型定义）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
