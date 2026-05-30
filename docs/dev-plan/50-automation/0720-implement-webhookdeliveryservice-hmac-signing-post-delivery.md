# WebhookDeliveryService · Implement HMAC-signed POST delivery

| 元数据 | 值 |
|---|---|
| Issue | #720 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [#719](./0720-implement-webhookdeliveryservice-hmac-signing-post-delivery.md) (webhook model + service skeleton) |
| 启用后赋能 | 无 — 本板块为叶子服务，被 `WebhookService` 或调度层调用 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Without a dedicated delivery service, each caller that needs to fire webhooks must individually implement HMAC signing, the async POST, timeout handling, and result logging — leading to code duplication and inconsistent retry/signature behaviour across the codebase. The webhook infra built in #719 provides the ORM model and subscription registry; this板块 bridges the gap to an operational delivery engine.

### 1.2 做完后

- **用户视角**：无用户可见 changes — 纯 back-end service component.
- **开发者视角**：`WebhookDeliveryService(session).deliver(event_type, payload, tenant_id)` is available; callers pass an `event_type` string and a serialisable `payload` dict, and the service handles signing, delivery, and persistence atomically.

### 1.3 不做什么（剔除）

- [ ] No retry / exponential back-off — this板块 implements single-shot delivery with immediate success/failure recording. Retry scheduling is owned by a separate板块 (TBD in #496).
- [ ] No webhook registration / management API — those live in #719.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_webhook_delivery_service.py -v` → `≥ 4 passed`
- `PYTHONPATH=src pytest tests/integration/test_webhook_delivery_service_integration.py -v` → `≥ 3 passed` (uses real DB, real HTTP via `respx` or similar)
- `ruff check src/services/webhook_delivery_service.py src/models/webhook_delivery.py` → `0 errors`
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → all exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/` 下是否有 `webhook_service.py` 或 `webhook_delivery_service.py` — #719 may have created an initial stub; check `src/services/webhook*.py` and `src/db/models/webhook*.py`.

TBD - 待验证：`src/db/models/webhook.py` L? — existing `WebhookModel` schema (tenant_id, url, secret, subscribed_events …) needs to be confirmed before writing the subscription query.

TBD - 待验证：`src/db/models/webhook_delivery.py` L? — #719 may have created the `WebhookDeliveryModel` stub; confirm fields before writing the insert logic.

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/services/webhook_service.py` — may need a `get_active_webhooks(event_type, tenant_id)` helper if not already present in #719
- 要建：
  - `src/services/webhook_delivery_service.py` — core delivery engine (HMAC sign + async POST + result logging)
  - `src/db/models/webhook_delivery.py` — `WebhookDeliveryModel` ORM (status, delivered_at, error_message …)
  - `alembic/versions/<id>_create_webhook_delivery_table.py` — migration for `webhook_delivery` table
  - `tests/unit/test_webhook_delivery_service.py` — mock-based unit tests
  - `tests/integration/test_webhook_delivery_service_integration.py` — real-DB integration tests

### 2.3 缺什么

- [ ] No `WebhookDeliveryService` class — callers cannot invoke structured delivery
- [ ] No HMAC-SHA256 signing utility — each hypothetical caller would re-implement `HMAC.new(..., hashlib.sha256).hexdigest()`
- [ ] No `WebhookDeliveryModel` row creation on delivery attempt (success or failure)
- [ ] No async HTTP delivery with `httpx.AsyncClient` — no timeout, no signature header injection
- [ ] No per-tenant webhook subscription query (filter by `tenant_id` + `event_type`)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/webhook_delivery_service.py` | `WebhookDeliveryService(session)` with `deliver(event_type, payload, tenant_id)` |
| `src/db/models/webhook_delivery.py` | `WebhookDeliveryModel` ORM (id, webhook_id, tenant_id, event_type, status, delivered_at, response JSON, payload) — place alongside `WebhookModel` in `webhook.py` OR in this separate file; if separate, also add import to `alembic/env.py` |
| `alembic/versions/<id>_create_webhook_delivery_table.py` | Creates `webhook_delivery` table with tenant_id index |
| `tests/unit/test_webhook_delivery_service.py` | Unit tests: mock session + mock HTTP, verify signing + POST + ORM insert |
| `tests/integration/test_webhook_delivery_service_integration.py` | Integration tests: real DB + `respx` mock endpoint, verify row persists |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/services/webhook_service.py` | May need `get_active_webhooks(event_type, tenant_id)` query helper; confirm with #719 |
| TBD - 待验证：`src/db/models/webhook.py` | May need `subscribed_events` column type (JSONB vs text[]); confirm with #719 |

### 3.3 新增能力

- **Service class**：`WebhookDeliveryService(session: AsyncSession)` — no default for session; raises `AppException` subclasses on error; returns nothing from `deliver()`
- **ORM model**：`WebhookDeliveryModel` in `src/db/models/webhook_delivery.py` with fields: `id`, `webhook_id`, `tenant_id`, `event_type`, `status` (`Literal['pending','success','failed']`), `delivered_at` (nullable UTC datetime), `error_message` (nullable text), `request_payload` (JSONB), `response_status_code` (nullable int)
- **Migration**：`alembic/versions/<id>_create_webhook_delivery_table.py` — creates table with `tenant_id` index and `webhook_id` FK
- **HTTP client**：`httpx.AsyncClient(timeout=30.0)` — 30-second per-request timeout
- **Signature format**：`X-Webhook-Signature: sha256=<hex_digest>` header on every outbound request

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **HMAC-SHA256 with `hashlib.sha256` + `hmac`** — Python stdlib; no extra package needed. Chosen over `hmac` module alone for clarity of `.hexdigest()` output.
- **`json.dumps(payload, sort_keys=True).encode()`** as the canonical payload bytes — sort_keys ensures deterministic body for reproducible signature across Python processes.
- **`httpx.AsyncClient` over `aiohttp.ClientSession`** — httpx is already the HTTP client used elsewhere in this codebase (verify in `pyproject.toml`); `aiohttp` would add a second dependency.
- **`timeout=30.0`** — fixed 30-second timeout per request; prevents indefinite hangs on slow endpoints.
- **Return nothing** — aligns with the service convention: raise on error, return nothing on success. Callers inspect `WebhookDeliveryModel` rows to confirm delivery outcome if needed.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `httpx` | `≥ 0.25` | async client with timeout param; confirmed in `pyproject.toml` |
| `pytest-asyncio` | `≥ 0.21` | async test support |

### 4.3 兼容性约束

- Multi-tenant：every SQL query includes `WHERE tenant_id = :tenant_id`
- Service `__init__` takes `session: AsyncSession` with NO default
- Service returns ORM objects + raises `AppException` subclasses; router serialises via `.to_dict()` — never call `.to_dict()` inside the service
- Import paths: `from db.models.webhook_delivery import WebhookDeliveryModel` (PYTHONPATH=src, no `src.` prefix)
- `WebhookDeliveryModel` column names: **never** use `metadata` — it collides with `Base.metadata`; use `event_metadata` or `request_payload` for payload storage

### 4.4 已知坑

1. **Alembic autogenerate emits `sa.JSON()` instead of `sa.JSONB()`** → after autogenerate, manually edit `alembic/versions/<id>_create_webhook_delivery_table.py` to replace `sa.JSON()` with `sa.JSONB()` for the `request_payload` and `error_message` columns (JSONB is preferred for indexed JSON storage in Postgres).
2. **Alembic drops `timezone=True` on DateTime columns** → after autogenerate, add `timezone=True` to `delivered_at` column (must be TIMESTAMPTZ not TIMESTAMP to avoid timezone ambiguity in multi-region deployments).
3. **`hmac` module `hexdigest()` returns raw hex, no `sha256=` prefix** → the `sha256=` prefix must be prepended manually when setting the `X-Webhook-Signature` header: `f"sha256={hmac.new(...).hexdigest()}"` — not just the raw hex.

---

## 5. 实现步骤（按顺序）

### Step 1: Confirm #719 outputs and import existing models

Read the output of #719 (or check the working tree) to confirm:
- Whether `src/db/models/webhook.py` exists and what columns it has (url, secret, subscribed_events type)
- Whether `src/db/models/webhook_delivery.py` already exists (it shouldn't — this is the new model this板块 creates)
- Whether `src/services/webhook_service.py` has a `get_active_webhooks(event_type, tenant_id)` method

操作：
- a) `ls src/db/models/webhook*.py src/services/webhook*.py 2>/dev/null` — confirm which files #719 produced
- b) If `webhook_service.py` has a suitable query method, note its exact signature for Step 3
- c) If no suitable method, plan to add one in `webhook_service.py` (or inline the query in `webhook_delivery_service.py`)

**完成判定**：`ls src/db/models/webhook.py src/services/webhook_service.py` → files exist / `echo "confirmed"`

### Step 2: Create WebhookDeliveryModel ORM

在 `src/db/models/` 下新建 `webhook_delivery.py`：

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base

class WebhookDeliveryModel(Base):
    __tablename__ = "webhook_delivery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    webhook_id: Mapped[int] = mapped_column(Integer, ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # 'pending' | 'success' | 'failed'
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {'status_code': int, 'body': str} or {'error': str}
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
```

注意：不使用 `metadata` 作为列名（与 `Base.metadata` 冲突）。

**完成判定**：`PYTHONPATH=src python -c "from db.models.webhook_delivery import WebhookDeliveryModel; print(WebhookDeliveryModel.__tablename__)"` → `webhook_delivery`

### Step 3: Add migration for webhook_delivery table

操作：
- a) 启动 clean DB：`docker compose -f configs/docker-compose.test.yml up -d test-db && docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;" && docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
- b) 确保 `#719` migration 已 applied：`alembic upgrade head`
- c) 生成：`alembic revision --autogenerate -m "create_webhook_delivery_table"`
- d) 手动修正 autogenerated file：将 `sa.JSON()` 改为 `sa.JSONB()`, 将 `DateTime` 改为 `DateTime(timezone=True)`（见 §4.4）
- e) 验证：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0

在 `alembic/env.py` 中确保已 import `WebhookDeliveryModel`（否则 autogenerate 看不到它）。

**完成判定**：`alembic upgrade head` exit 0 AND `alembic history --verbose | tail -3` shows new revision

### Step 4: Implement WebhookDeliveryService

新建 `src/services/webhook_delivery_service.py`：

```python
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.webhook import WebhookModel, WebhookDeliveryModel

class WebhookDeliveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def deliver(
        self,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: int,
    ) -> None:
        # 1. Query active webhooks subscribed to event_type for this tenant.
        # Use SQL-level JSONB containment as primary filter; Python filter
        # is the safety net.
        # NOTE: WebhookModel.is_active and WebhookModel.events (list[str])
        # must be confirmed from #719 model before running.
        stmt = select(WebhookModel).where(
            WebhookModel.tenant_id == tenant_id,
            WebhookModel.is_active == True,  # noqa: E712 — confirm from #719
        )
        result = await self.session.execute(stmt)
        webhooks = result.scalars().all()

        # Safety-net filter in Python (primary filter should be SQL-level
        # via func.jsonb_exists if the query engine supports it)
        subscribed = [
            w for w in webhooks
            if event_type in (getattr(w, "events", []) or [])
        ]

        for webhook in subscribed:
            await self._deliver_to_webhook(webhook, event_type, payload, tenant_id)

    async def _deliver_to_webhook(
        self,
        webhook: WebhookModel,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: int,
    ) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        secret = webhook.secret or ""
        signature = f"sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}"

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(webhook.url, content=body, headers=headers)
                status_code = response.status_code
                if 200 <= status_code < 300:
                    response_body = {"status_code": status_code, "body": response.text[:500]}
                    error_msg = None
                else:
                    response_body = {"status_code": status_code, "error": response.text[:500]}
                    error_msg = response.text[:500]
        except httpx.TimeoutException as exc:
            status_code = None
            error_msg = str(exc)
            response_body = {"error": str(exc)}
        except Exception as exc:
            status_code = None
            error_msg = str(exc)
            response_body = {"error": str(exc)}

        # Persist delivery record
        delivery = WebhookDeliveryModel(
            webhook_id=webhook.id,
            tenant_id=tenant_id,
            event_type=event_type,
            status="success" if status_code and 200 <= status_code < 300 else "failed",
            delivered_at=datetime.now(timezone.utc) if status_code and 200 <= status_code < 300 else None,
            response=response_body,
            payload=payload,
        )
        self.session.add(delivery)
        await self.session.flush()  # router-layer get_db dependency commits on normal exit
```

**完成判定**：`ruff check src/services/webhook_delivery_service.py` → 0 errors

### Step 5: Write unit tests

新建 `tests/unit/test_webhook_delivery_service.py`：

操作：
- a) 用 `make_mock_session` 配合一个 handler 返回预配置的 webhook list
- b) 用 `respx` 或 `httpx.AsyncClient` mock via `asyncmock` to capture outbound requests
- c) Assert: `X-Webhook-Signature` header present and starts with `sha256=`
- d) Assert: `WebhookDeliveryModel` row inserted with correct `tenant_id`, `event_type`, `status`
- e) Assert: on HTTP 2xx → status='success' + delivered_at set; on non-2xx → status='failed' + error_message set

```python
# Key test cases:
# 1. single webhook, 2xx response → status='success', delivered_at set
# 2. single webhook, 500 response → status='failed', error_message populated
# 3. two webhooks, one succeeds one fails → two rows inserted
# 4. no webhooks subscribed → no HTTP call, no rows inserted
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_delivery_service.py -v` → `≥ 3 passed`

### Step 6: Write integration tests

新建 `tests/integration/test_webhook_delivery_service_integration.py`：

操作：
- a) `db_schema` fixture creates all tables including `webhook_delivery`
- b) Seed a `WebhookModel` row with known `tenant_id`, `url` (pointing to `respx` mock endpoint), `secret`
- c) Call `WebhookDeliveryService(session).deliver("order.created", {...}, tenant_id)`
- d) Commit and query `WebhookDeliveryModel` — assert row present with correct status

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_webhook_delivery_service_integration.py -v` → `≥ 3 passed`

---

## 6. 验收

- [ ] `ruff check src/services/webhook_delivery_service.py` → 0 errors
- [ ] `ruff check src/db/models/webhook_delivery.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.webhook_delivery import WebhookDeliveryModel; print('ok')"` → `ok`
- [ ] `PYTHONPATH=src pytest tests/unit/test_webhook_delivery_service.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_webhook_delivery_service_integration.py -v` → all passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → all exit 0 (migration verified)
- [ ] `ruff check src/services/webhook_delivery_service.py src/db/models/webhook_delivery.py` → 0 errors (combined check)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #719 not merged before this板块 starts — `WebhookModel` schema unknown | 中 | 高 | Block this板块 until #719 lands; document the block in the依赖 row |
| `webhook.secret` is `NULL` in DB — HMAC fails with `TypeError` | 低 | 高 | Guard with `secret or ""` (already in code) so NULL → empty-key HMAC; add DB constraint NOT NULL in a follow-up migration |
| httpx times out on slow endpoints → 30s block per webhook | 低 | 中 | `timeout=30.0` is fixed; no dynamic retry in this板块; downstream retry板块 handles back-off |
| Migration conflict: #719 migration also touches `webhook_delivery` table | 低 | 高 | If alembic autogenerate produces an empty diff after merging #719, the conflict is resolved; review alembic history before merging |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/webhook_delivery_service.py \
        src/db/models/webhook_delivery.py \
        alembic/versions/<id>_create_webhook_delivery_table.py \
        tests/unit/test_webhook_delivery_service.py \
        tests/integration/test_webhook_delivery_service_integration.py
git commit -m "feat(webhook): implement WebhookDeliveryService with HMAC-SHA256 signing"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#720): WebhookDeliveryService HMAC-signed POST delivery" --body "Closes #720"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/` 下是否有类似的 HTTP-firing + ORM-logging service（如通知发送服务）；用于参考 service 结构和测试模式
- 父 issue / 关联：#496 (parent epic), #719 (webhook model + service skeleton — 依赖)
- HMAC spec：webhook signature standard — `sha256=<hex>` prefix on `X-Webhook-Signature` header; canonical body is `json.dumps(payload, sort_keys=True)`

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
