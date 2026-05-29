# 后台重试调度器（指数退避）· 实现 Webhook 失败自动重试调度器

| 元数据 | 值 |
|---|---|
| Issue | #721 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 2-2.5 工作日 |
| 依赖 | [0720-retry-webhook-upon-failure-atomic-compare-and-swap](../0720-retry-webhook-upon-failure-atomic-compare-and-swap.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 Webhook 投递失败后无自动重试机制，一旦终端服务暂时不可达，投递即永久失败。业务上要求对临时性网络超时、5xx 等可重试错误做指数退避重试，以提升下游系统的可达性和健壮性。作为 #496 统一事件投递改造的拆分之一，本板块聚焦在调度器基础设施，实现独立的异步后台循环。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯后台基础设施。
- **开发者视角**：`start_scheduler()` 可在应用启动时注册，调度器将持续自动重试失败的 Webhook 投递，最多重试 5 次（1m → 5m → 30m → 1h → 24h），无需任何人工介入。

### 1.3 不做什么（剔除）

- [ ] Webhook 投递逻辑本身（POST 请求构建、重试触发条件判断）不在本板块实现 — 由 #720 提供- [ ] 不实现即时重试（仅后台定时循环，不在投递失败后立即触发）
- [ ] 不实现告警 /通知（Slack / Email 不在本板块范围）
- [ ] 不实现调度器的多实例选举（单实例运行；后续如有需要再单独开板块）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_webhook_scheduler.py -v` → ≥8 passed
- `PYTHONPATH=src pytest tests/integration/test_webhook_scheduler_integration.py -v` → ≥ 4 passed（如 CI 环境有 DB）
- `ruff check src/services/webhook_scheduler.py src/services/webhook_delivery_service.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0（如有 migration）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/webhook_delivery_service.py L? —现有 WebhookDeliveryService 服务，定义投递状态枚举和方法`
TBD - 待验证：`src/db/models/webhook_delivery.py L? — 现有 webhook_deliveries 表 schema，包含 status / attempts / next_retry_at 列`
TBD - 待验证：`src/db/models/webhook.py L? — 现有 webhooks 表 schema，包含 url / secret 列`

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/services/webhook_delivery_service.py` — 重试状态更新逻辑由 #720 提供，本板块引用  - TBD - 待验证：`src/services/webhook_scheduler.py` — 新增调度器服务  - TBD - 待验证：`src/main.py` — 应用启动时注册调度器
- 要建：
  - `src/services/webhook_scheduler.py` — `_retry_scheduler()` 后台循环 + `start_scheduler()` 暴露入口
  - `alembic/versions/<id>_add_next_retry_at_to_webhook_deliveries.py` — 若表已缺列则新建 migration（若已有则跳过）
  - `tests/unit/test_webhook_scheduler.py` — 调度器单元测试（MockDB）
  - `tests/integration/test_webhook_scheduler_integration.py` —调度器集成测试（Real DB）

### 2.3 缺什么

- [ ] 后台调度器循环：定时查询 `status='failed' AND attempts < MAX_RETRIES AND next_retry_at <= now()` 的待重试记录
- [ ] 指数退避延迟策略：`RETRY_DELAYS = [1m, 5m, 30m, 1h, 24h]`，按 `attempts` 下标取值
- [ ] 单次调度周期使用独立 Fresh Session（open/close 模式，不复用长连接 session）
- [ ] `start_scheduler()` 协程入口供 `asyncio.create_task()` 在应用启动时注册
- [ ] 批量处理（每次循环最多处理 50 条记录）
- [ ] 永久失败状态：`attempts >= MAX_RETRIES` 时将 `status` 设为 `'failed'` 并不再重试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/webhook_scheduler.py` | 后台重试调度器：`_retry_scheduler()`循环 + `start_scheduler()` 启动入口 |
| `alembic/versions/<id>_add_next_retry_at_to_webhook_deliveries.py` | 为 `webhook_deliveries` 表添加 `next_retry_at` 列（如列已存在则跳过此 migration） |
| `tests/unit/test_webhook_scheduler.py` | 调度器单元测试：MockDB session，覆盖重试逻辑、退避延迟、批量上限 |
| `tests/integration/test_webhook_scheduler_integration.py` | 调度器集成测试：Real DB fixture，验证状态流转正确性 |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../src/main.py) | 在 lifespan startup事件中调用 `start_scheduler()` 注册后台任务 |

### 3.3 新增能力

- **New Service module**：`src/services/webhook_scheduler.py` 暴露 `start_scheduler() -> Coroutine` 供 app启动时注册
- **Background task**：`async def _retry_scheduler()` 定时循环，每次获取 Fresh Session，批量查询待重试记录，执行重试后更新状态
- **Retry strategy**：指数退避 `RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=1), timedelta(hours=24))`，`MAX_RETRIES = 5`
- **Permanent failure**：`attempts >= MAX_RETRIES` 时 `status = 'failed'`（不再设 `next_retry_at`）
- **Batch limit**：每轮循环最多处理 50 条记录，防止锁竞争---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **独立 Fresh Session 而非复用长会话**：调度器循环周期较长（最低 30s），复用同一个 AsyncSession 会导致 Session 过期（事务超时）；每次 open/close 是行业标准做法。
- **定时轮询而非事件驱动**：即使用户在 #720 中已实现触发式重试，调度器仍作为兜底机制，确保即使进程重启后也能自动恢复重试队列。
- **批量50 条，不做并发 POST**：避免对下游服务产生突发压力；每批内顺序执行，单次失败不影响其他记录。

### 4.2 版本约束

|依赖 | 版本 | 理由 |
|------|------|------|
| `asyncio` | 标准库 | Python3.11+ 内置，无需额外安装 |
| `pyyaml` | `>=6.0` | 仅用于配置如需要；已在本项目依赖中 |

### 4.3 兼容性约束

- 多租户：调度器的轮询 SQL 必须包含 `WHERE tenant_id = :tenant_id`（按租户隔离）
- Service 返回 ORM 对象，不调用 `.to_dict()`；调度器作为 Router 同级的服务层，同样遵守此约定
- Service 错误抛 `AppException` 子类，不返回 `ApiResponse.error()`
- Async Session注入使用 `Depends(get_db)`，调度器中手动 open/close 时仍使用同一 `get_db_session()`上下文管理器
- 表列名避免使用 `metadata`（与 SQLAlchemy `Base.metadata` 冲突），本板块假设列名为 `event_metadata` 或 `payload`

### 4.4 已知坑

1. **Alembic autogenerate 把 TIMESTAMPTZ 写成 DateTime，不带 `timezone=True`** → 手动修改 migration 文件中的列类型为 `DateTime(timezone=True)` 或 `DateTime`
2. **Alembic autogenerate 把 JSONB 写成 JSON** → 手动将 `sa.JSON()` 改为 `sa.JSONB()`
3. **调度器首次启动不能阻塞应用** → 使用 `asyncio.create_task(start_scheduler(), name="webhook-retry-scheduler")` 在 lifespan startup 中启动，不 await4. **轮询频率过高导致 DB负载** →初始轮询间隔设为 30s，可配置；在调度器入口暴露 `SCHEDULE_INTERVAL =30` 常量

---

## 5. 实现步骤（按顺序）

### Step 1: 添加数据库列（如尚未存在）

检查 `webhook_deliveries` 表是否已有 `next_retry_at` 和 `attempts` 列。若无，执行以下步骤。

操作：

a) 通过 `docker compose` 启动本地开发数据库：

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
```

b) 创建临时 alembic_dev 数据库（见 CLAUDE.md）：

```bash
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
```

c) 设置环境变量并 autogenerate：

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
alembic upgrade head
alembic revision --autogenerate -m "add next_retry_at and attempts to webhook_deliveries"
```

d) 编辑生成的 migration 文件，修正 autogenerate 缺陷（DateTime → DateTime(timezone=True)，JSON → JSONB），在 `upgrade()` 中填入正确的列定义，在 `downgrade()` 中写可逆的回退逻辑。

e) 验证 migration：

```bash
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

**完成判定**：`alembic upgrade head` exit 0，`alembic downgrade -1` exit 0，`alembic history --verbose` 可见新 revision

### Step 2: 创建调度器服务模块

在 `src/services/webhook_scheduler.py` 编写 `_retry_scheduler()` 循环和 `start_scheduler()`入口。

操作：

a) 创建文件 `src/services/webhook_scheduler.py`：

```python
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncGeneratorfrom sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from db.base import async_session_factory
from db.models import WebhookDeliveryModel, WebhookModel
from services.webhook_delivery_service import WebhookDeliveryService

RETRY_DELAYS: tuple[timedelta, ...] = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=1),
    timedelta(hours=24),
)
MAX_RETRIES = 5
BATCH_SIZE = 50
SCHEDULE_INTERVAL = 30  # seconds


async def _get_fresh_session() -> AsyncGenerator[AsyncSession, None]:
    @asynccontextmanager
    def _factory():
        session: AsyncSession = async_session_factory()
        try:
            yield session
        finally:
            await session.close()
    return _factory()


async def _retry_scheduler() -> None:
    factory = _get_fresh_session()
    async with factory() as session:
        svc = WebhookDeliveryService(session)
        now = datetime.now(timezone.utc)
        stmt = (
            select(WebhookDeliveryModel)
            .where(
                WebhookDeliveryModel.status == "failed",
                WebhookDeliveryModel.attempts < MAX_RETRIES,
                WebhookDeliveryModel.next_retry_at <= now,
            )
            .order_by(WebhookDeliveryModel.next_retry_at)
            .limit(BATCH_SIZE)
        )
        result = await session.execute(stmt)
        deliveries = result.scalars().all()
    # TODO: fetch parent webhook URL/secret; POST retry; update status/next_retry_at # (refinement in subsequent steps)


async def start_scheduler() -> None:
    import asyncio
    while True:
        try:
            await _retry_scheduler()
        except Exception:
            import logging            logging.getLogger(__name__).exception("Scheduler cycle failed")
        await asyncio.sleep(SCHEDULE_INTERVAL)
```

b) 运行 ruff check：

```bash
ruff check src/services/webhook_scheduler.py
```

**完成判定**：`ruff check src/services/webhook_scheduler.py` exit 0

### Step 3: 实现重试核心逻辑

完善 `src/services/webhook_scheduler.py` 中的 `_retry_scheduler()`，加入：
- 按 tenant_id 逐条查询父 Webhook 的 URL/secret
- 对每条记录发起 HTTP POST 重试（使用 `httpx.AsyncClient`）
- 成功时更新 `status='success'`，`delivered_at=now`
- 失败时 `attempts += 1`；若 `attempts >= MAX_RETRIES` 则 `status='failed'`；否则 `next_retry_at = now + RETRY_DELAYS[attempts-1]`

操作：

在 `_retry_scheduler()` 中逐条处理（而非批量 POST）：

```python
import httpx


async def _send_webhook(url: str, payload: dict, secret: str) -> bool:
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        return 200 <= resp.status_code < 300


async def _retry_scheduler() -> None:
    factory = _get_fresh_session()
    async with factory() as session:
        now = datetime.now(timezone.utc)
        stmt = (
            select(WebhookDeliveryModel)
            .where(
                WebhookDeliveryModel.status == "failed",
                WebhookDeliveryModel.attempts < MAX_RETRIES,
                WebhookDeliveryModel.next_retry_at <= now,
            )
            .order_by(WebhookDeliveryModel.next_retry_at)
            .limit(BATCH_SIZE)
        )
        result = await session.execute(stmt)
        deliveries: list[WebhookDeliveryModel] = list(result.scalars().all())

 for delivery in deliveries:
            webhook_stmt = select(WebhookModel).where(
                WebhookModel.id == delivery.webhook_id,
                WebhookModel.tenant_id == delivery.tenant_id,
            )
            wh_result = await session.execute(webhook_stmt)
            webhook = wh_result.scalar_one_or_none()
            if webhook is None:
                continue

 payload = delivery.event_metadata or {}
            ok = await _send_webhook(webhook.url, payload, webhook.secret)

            if ok:
                delivery.status = "success"
                delivery.delivered_at = now
            else:
                delivery.attempts += 1
                if delivery.attempts >= MAX_RETRIES:
                    delivery.status = "failed"
                    delivery.next_retry_at = None
                else:
                    delay = RETRY_DELAYS[delivery.attempts - 1]
                    delivery.next_retry_at = now + delay
            await session.commit()
```

**完成判定**：`ruff check src/services/webhook_scheduler.py` exit 0

### Step 4: 在应用启动时注册调度器

在 `src/main.py` 的 lifespan startup 事件中注册调度器任务。

操作：

a) 在 `src/main.py` 中 import：

```python
from services.webhook_scheduler import start_scheduler
```

b) 在 lifespan startup 中插入：

```python
async def lifespan(app: FastAPI):
    asyncio.create_task(start_scheduler(), name="webhook-retry-scheduler")
    yield
```

（若 lifespan 已存在，则将 `asyncio.create_task(...)` 加入现有 startup块）

**完成判定**：`ruff check src/main.py` exit 0，`grep -n "start_scheduler" src/main.py` 有输出

### Step 5: 编写单元测试

创建 `tests/unit/test_webhook_scheduler.py`，使用 `tests/unit/conftest.py` 的 Mock 工具。

操作：

a) 使用 `MockState` + `make_mock_session` 构建 mock DB session

b) 测试用例覆盖：
- `test_retry_delays_exponential_backoff`：验证 `RETRY_DELAYS`长度 = `MAX_RETRIES`
- `test_scheduler_queries_failed_deliveries_only`：验证 SQL 语句不含 `status='success'` 行
- `test_scheduler_respects_batch_size`：验证 LIMIT = BATCH_SIZE- `test_scheduler_sets_next_retry_at_on_failure`：验证 `next_retry_at` 被正确计算
- `test_scheduler_permanent_failure_at_max_retries`：验证 `attempts >= MAX_RETRIES` 时 `status='failed'`
- `test_scheduler_updates_status_on_success`：验证成功时 `status='success'` + `delivered_at`
- `test_fresh_session_per_cycle`：验证每轮调度器使用独立的 session.close() 调用模式

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_scheduler.py -v` → ≥ 8 passed

### Step 6: 编写集成测试

创建 `tests/integration/test_webhook_scheduler_integration.py`，使用 `db_schema` / `async_session` fixtures。

操作：

a) 创建 `TestWebhookSchedulerIntegration` 测试类

b) 测试用例覆盖：
- 插入一条 `status='failed'` 记录，调度器运行后应变为 `status='success'`
- 插入 `MAX_RETRIES` 次失败的记录，调度器运行后应变为 `status='failed'` 且 `next_retry_at=None`
- `next_retry_at` 在未来时间的记录不应被调度器处理- 多租户隔离：租户 A 的失败记录不应被租户 B 的调度器处理（调度器按 tenant_id 过滤）

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_webhook_scheduler_integration.py -v` → ≥ 4 passed

---

## 6. 验收

- [ ] `ruff check src/services/webhook_scheduler.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_webhook_scheduler.py -v` → ≥ 8 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_webhook_scheduler_integration.py -v` → ≥ 4 passed（DB 可用时）
- [ ] `ruff format --check src/services/webhook_scheduler.py src/main.py` → exit 0
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0（如涉及 migration）
- [ ] `grep -n "start_scheduler" src/main.py` 输出包含 `asyncio.create_task(start_scheduler()` 行---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `httpx.AsyncClient` POST 超时导致单轮调度器异常崩溃，后续循环停止 | 低 | 高 | 在 `start_scheduler()` 外层 try/except 包裹 `_retry_scheduler()`整个调用，确保一次循环失败不会阻止后续循环 |
| Fresh Session 频繁 open/close 在高并发写入场景下引发连接池耗尽 | 中 | 中 | 通过配置 `POOL_SIZE` 和 `MAX_OVERFLOW` 控制；或在 scheduler 中加互斥锁（单进程单调度器实例天然隔离） |
| `next_retry_at` 列不存在导致 migration失败或运行时错误 | 低 | 高 | 在 Step 1 先检查列是否存在（SELECT column_name FROM information_schema.columns WHERE ...），列已存在则跳过该 migration |
| 调度器与投递服务同时修改同一条记录，产生竞争条件 | 中 | 中 | 调度器使用 `SELECT ... FOR UPDATE SKIP LOCKED` 锁定正在处理的行；由 #720 提供原子 compare-and-swap 保障 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/webhook_scheduler.py src/main.py
git add alembic/versions/
git add tests/unit/test_webhook_scheduler.py tests/integration/test_webhook_scheduler_integration.py
git commit -m "feat(webhook): implement background retry scheduler with exponential backoff"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#721): background retry scheduler with exponential backoff" --body "Closes #721"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/<现有定时任务服务>` — 参考其 session open/close 模式
- 第三方文档： httpx 官方文档 — AsyncClient 用法；SQLAlchemy 2.x async session 管理- 父 issue / 关联：#496（Webhooks投递统一改造父 issue）
- 依赖板块：#720（提供 WebhookDeliveryService 重试相关方法）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
