# 40-campaigns · Create WhatsApp conversation service

| 元数据 | 值 |
|---|---|
| Issue | #526 |
| 分类 | [40-campaigns](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [#525](../50-automation/0525-create-whatsapp-api-wrapper.md), #71 |
| 启用后赋能 | [40-campaigns](../40-campaigns/) (WhatsApp campaign automation), [50-automation](../50-automation/) (trigger-based messaging) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The current CRM system has no WhatsApp messaging capability. Issue #525 provides a low-level HTTP wrapper for the WhatsApp Business API, but there is no service layer to store conversations, link tickets, or expose conversation history to callers. Without a dedicated `WhatsAppService`, every caller must speak to the raw HTTP wrapper directly — bypassing tenant scoping, auditing, and persistence — which makes multi-tenant operation and replay impossible.

### 1.2 做完后

- **用户视角**: Messages sent via the CRM are persisted and can be viewed in the conversation history. Support agents can link a WhatsApp conversation to a ticket for context. No user-facing UI is built in this step (scope only covers the service layer).
- **开发者视角**: Callers can `WhatsAppService.send_message()` with a tenant-scoped session and receive a persisted `WhatsAppConversation` record back. `link_ticket()` attaches a `ticket_id` to an existing conversation. `get_conversation_history()` returns all messages for a contact within a tenant.

### 1.3 不做什么（剔除）

- [ ] WhatsApp Business API credential management (secrets/vault handling is handled by #525)
- [ ] WhatsApp message templates or approval workflows (future scope)
- [ ] Frontend UI for conversation history or message composition
- [ ] Retry logic / dead-letter queue for failed sends (handled separately)

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_whatsapp_service.py -v` → ≥ 6 passed]
- [指标 2：`PYTHONPATH=src pytest tests/integration/test_whatsapp_service_integration.py -v` → ≥ 4 passed]
- [指标 3：`ruff check src/services/whatsapp_service.py src/db/models/whatsapp_conversation.py` → 0 errors]
- [指标 4：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`src/services/whatsapp_service.py` does not exist yet. The WhatsApp HTTP wrapper created by #525 provides the underlying `WhatsAppApiClient` but does not include persistence or tenant-scoped conversation management.

`TBD - 待验证：src/services/whatsapp_api_client.py L? — 现有 WhatsAppApiClient class 定义位置（#525 产出）`

### 2.2 涉及文件清单

- 要改：
  - `src/services/whatsapp_service.py` — 新建，暴露 `send_message` / `link_ticket` / `get_conversation_history`
- 要建：
  - `src/db/models/whatsapp_conversation.py` — ORM model for `whatsapp_conversations` table
  - `alembic/versions/<id>_create_whatsapp_conversations.py` — migration to create the table with `tenant_id` index
  - `src/api/routers/whatsapp.py` — FastAPI router with `POST /whatsapp/send`, `POST /whatsapp/{conversation_id}/link-ticket`, `GET /whatsapp/history/{contact_id}`
  - `tests/unit/test_whatsapp_service.py` — unit tests mocking HTTP wrapper
  - `tests/integration/test_whatsapp_service_integration.py` — integration tests with real DB

### 2.3 缺什么

- [ ] `WhatsAppConversation` ORM model scoped to `tenant_id`
- [ ] `WhatsAppService` with `send_message` that persists to DB and calls `WhatsAppApiClient`
- [ ] `WhatsAppService.link_ticket` to associate a ticket to an existing conversation
- [ ] `WhatsAppService.get_conversation_history` for multi-tenant contact message retrieval
- [ ] Alembic migration for `whatsapp_conversations` table
- [ ] FastAPI router endpoints for all three service methods
- [ ] Unit test suite mocking the HTTP wrapper
- [ ] Integration test suite verifying round-trip send → DB fetch

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/whatsapp_conversation.py` | `WhatsAppConversation` ORM model mapped to `whatsapp_conversations` table |
| `alembic/versions/<id>_create_whatsapp_conversations.py` | Migration creating `whatsapp_conversations` with `tenant_id` index |
| `src/services/whatsapp_service.py` | `WhatsAppService` class with `send_message`, `link_ticket`, `get_conversation_history` |
| `src/api/routers/whatsapp.py` | FastAPI router exposing WhatsApp endpoints |
| `tests/unit/test_whatsapp_service.py` | Unit tests mocking `WhatsAppApiClient` |
| `tests/integration/test_whatsapp_service_integration.py` | Integration tests with real DB and `WhatsAppApiClient` stub |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/__init__.py` | Export `WhatsAppConversation` from models package |
| `src/api/routers/__init__.py` | Include `whatsapp` router in API router bundle |
| `alembic/env.py` | Ensure `WhatsAppConversation` is imported so autogen picks it up |

### 3.3 新增能力

- **Service method**：`WhatsAppService.send_message(self, session, tenant_id, contact_id, message_body, message_type) -> WhatsAppConversation`
- **Service method**：`WhatsAppService.link_ticket(self, session, tenant_id, conversation_id, ticket_id) -> WhatsAppConversation`
- **Service method**：`WhatsAppService.get_conversation_history(self, session, tenant_id, contact_id, page, page_size) -> tuple[list[WhatsAppConversation], int]`
- **ORM model**：`WhatsAppConversation` in `src/db/models/whatsapp_conversation.py` with `tenant_id`, `contact_id`, `message_id` (WhatsApp message ID), `message_type`, `message_body`, `ticket_id` (nullable), `status`, `created_at`, `updated_at`
- **API endpoint**：`POST /whatsapp/send` → `{"success": true, "data": {...}}`
- **API endpoint**：`POST /whatsapp/{conversation_id}/link-ticket` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /whatsapp/history/{contact_id}` → `{"success": true, "data": {"items": [...], "total": N}}`
- **Migration**：`alembic upgrade head` creates `whatsapp_conversations` table with composite index on `(tenant_id, contact_id)`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `whatsapp_conversations` table 不选 on-demand API calls only**: Persisting every outbound message enables replay (failed send retry), audit trail, and contact history browsing. The WhatsApp Business API itself does not provide a durable conversation store that survives API key rotation.
- **选 `message_metadata` as JSONB column 不选 flat columns**: WhatsApp payloads include variable fields (buttons, templates, media). A JSONB column avoids schema churn as the API evolves; individual fields like `message_id`, `status`, `contact_id`, and `tenant_id` remain indexed columns for query performance.
- **选 service-then-router pattern 不选 router-only**: Keeping business logic in `WhatsAppService` (not in the router) ensures `link_ticket` and `get_conversation_history` are reusable from other services (e.g. an automation rule service that triggers on ticket events).

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `WhatsAppApiClient` | from `#525` | Interface contract; must expose `send_message(contact_id, body, message_type)`. No version pinning needed as it is an internal sibling module. |

### 4.3 兼容性约束

- Multi-tenancy: every SQL query must `WHERE tenant_id = :tenant_id` (see CLAUDE.md §Multi-Tenancy)
- Service returns ORM/dataclass objects, **does not** call `.to_dict()`; serialization is the router's responsibility
- Service errors raise `AppException` subclasses (`NotFoundException` / `ValidationException`), **do not** return `ApiResponse.error()`
- Session is injected via `session: AsyncSession = Depends(get_db)` — never use `async with get_db() as session:`
- `WhatsAppConversation` model column names must not shadow SQLAlchemy `Base.metadata` — avoid `metadata` as column name; use `message_metadata`

### 4.4 已知坑

1. **SQLAlchemy `Base.metadata` name collision** → 规避：Column named `message_metadata` (JSONB), not `metadata`
2. **Alembic autogenerate emits `sa.JSON()` instead of `sa.JSONB()`** → 规避：Manually edit migration to use `sa.JSONB()` for the `message_metadata` column; add `timezone=True` to `DateTime` columns
3. **`WhatsAppApiClient` may not yet exist if #525 is not merged** → 规避：Define a minimal interface stub in `tests/unit/conftest.py` until #525 lands; update the stub import path once #525 is merged
4. **No idempotency key on send** → 规避：`send_message` generates a client-side `idempotency_key` UUID and stores it in `message_metadata`; WhatsApp API accepts it as a header if the wrapper supports it (confirm with #525 wrapper implementation)

---

## 5. 实现步骤（按顺序）

### Step 1: Create `WhatsAppConversation` ORM model

Add `src/db/models/whatsapp_conversation.py` with the table definition. Include `tenant_id` (indexed), `contact_id` (indexed), `message_id` (WhatsApp's returned ID), `message_type` (string enum), `message_body` (text), `message_metadata` (JSONB, stores raw API response), `ticket_id` (nullable FK), `status` (string enum: `pending`/`sent`/`delivered`/`failed`), `created_at`, `updated_at`. Use `Mapped[]` type annotations throughout. Add `to_dict()` method for router serialization.

Export `WhatsAppConversation` from `src/db/models/__init__.py`.

**完成判定**：文件 `src/db/models/whatsapp_conversation.py` 存在；`ruff check src/db/models/whatsapp_conversation.py` → 0 errors

### Step 2: Create Alembic migration for `whatsapp_conversations` table

Generate migration using `alembic revision --autogenerate -m "create_whatsapp_conversations"`. Manually edit to:
- Use `sa.JSONB()` for `message_metadata` column (not `sa.JSON()`)
- Add `timezone=True` to `created_at` and `updated_at` columns
- Add `index=True` on `tenant_id` column
- Add composite index `ix_whatsapp_conversations_tenant_contact` on `(tenant_id, contact_id)`

Run `alembic upgrade head` against `alembic_dev` DB, then `alembic downgrade -1 && alembic upgrade head` to verify reversibility.

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0；`alembic/versions/<id>_create_whatsapp_conversations.py` 文件存在

### Step 3: Create `WhatsAppService` class

Create `src/services/whatsapp_service.py`. Import `WhatsAppApiClient` from `src.services.whatsapp_api_client` (or a local stub if #525 is not yet merged).

`send_message(session, tenant_id, contact_id, message_body, message_type="text")`:
- Calls `WhatsAppApiClient.send_message(contact_id, message_body, message_type)` (mockable in tests)
- Creates `WhatsAppConversation` record with `status="pending"`, persists to DB
- Updates `status` to `"sent"` or `"failed"` based on wrapper response
- Returns the ORM object

`link_ticket(session, tenant_id, conversation_id, ticket_id)`:
- Fetches `WhatsAppConversation` by `(conversation_id, tenant_id)`, raises `NotFoundException` if missing
- Sets `ticket_id` on the record, commits
- Returns updated ORM object

`get_conversation_history(session, tenant_id, contact_id, page=1, page_size=20)`:
- Queries `WhatsAppConversation` filtered by `(tenant_id, contact_id)`, ordered by `created_at DESC`
- Returns `tuple[list[WhatsAppConversation], int]`

**完成判定**：文件 `src/services/whatsapp_service.py` 存在；`PYTHONPATH=src ruff check src/services/whatsapp_service.py` → 0 errors

### Step 4: Create FastAPI router for WhatsApp endpoints

Create `src/api/routers/whatsapp.py`. Endpoints:

`POST /whatsapp/send`
- Body: `{"contact_id": int, "message_body": str, "message_type": "text"|"image"|"document"}`
- Calls `WhatsAppService(session).send_message(ctx.tenant_id, ...)`
- Returns `{"success": true, "data": conversation.to_dict()}`

`POST /whatsapp/{conversation_id}/link-ticket`
- Body: `{"ticket_id": int}`
- Calls `WhatsAppService(session).link_ticket(conversation_id, ctx.tenant_id, ticket_id)`
- Returns `{"success": true, "data": conversation.to_dict()}`

`GET /whatsapp/history/{contact_id}`
- Query params: `page=1`, `page_size=20`
- Calls `WhatsAppService(session).get_conversation_history(ctx.tenant_id, contact_id, page, page_size)`
- Returns `{"success": true, "data": {"items": [...], "total": N}}`

Include `whatsapp` router in `src/api/routers/__init__.py`.

**完成判定**：文件 `src/api/routers/whatsapp.py` 存在；`ruff check src/api/routers/whatsapp.py` → 0 errors

### Step 5: Write unit tests for `WhatsAppService`

Create `tests/unit/test_whatsapp_service.py`. Use `make_mock_session` from `tests/unit/conftest.py`. Add a `whatsapp_handler` that simulates `INSERT` / `SELECT` on `whatsapp_conversations`.

Test cases:
- `test_send_message_success`: mock `WhatsAppApiClient.send_message` to return `{"message_id": "wamid.xxx"}`; assert conversation persisted with `status="sent"`
- `test_send_message_failure`: mock wrapper to raise; assert conversation persisted with `status="failed"`
- `test_link_ticket`: insert conversation, call `link_ticket`, assert `ticket_id` set
- `test_link_ticket_not_found`: assert `NotFoundException` when conversation doesn't exist
- `test_get_conversation_history`: insert 3 conversations, assert pagination returns correct count
- `test_get_conversation_history_tenant_isolation`: assert cross-tenant queries return 0 results

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_whatsapp_service.py -v` → 6 passed

### Step 6: Write integration tests for `WhatsAppService`

Create `tests/integration/test_whatsapp_service_integration.py`. Use `db_schema`, `tenant_id`, `async_session` fixtures. Use a stub `WhatsAppApiClient` that returns a fake message ID (not real HTTP calls).

Test cases:
- `test_send_message_round_trip`: send message → query DB → assert fields match (tenant_id, contact_id, message_body, status)
- `test_link_ticket_integration`: create conversation in DB, call `link_ticket`, re-fetch → assert `ticket_id` populated
- `test_history_pagination`: seed 25 conversations, query page 2 size 10, assert 10 returned and total=25

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_whatsapp_service_integration.py -v` → 4 passed

### Step 7: Final verification

Run full lint check on all changed files: `ruff check src/services/whatsapp_service.py src/db/models/whatsapp_conversation.py src/api/routers/whatsapp.py tests/unit/test_whatsapp_service.py tests/integration/test_whatsapp_service_integration.py` → 0 errors.

Run migration against a clean `alembic_dev` DB: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0.

**完成判定**：`ruff check ...` exit 0；`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` exit 0

---

## 6. 验收

- [ ] `ruff check src/services/whatsapp_service.py src/db/models/whatsapp_conversation.py src/api/routers/whatsapp.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_whatsapp_service.py -v` → 6 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_whatsapp_service_integration.py -v` → 4 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0 (against `alembic_dev`)
- [ ] `mypy src/services/whatsapp_service.py src/db/models/whatsapp_conversation.py` → 0 errors (if mypy is configured in project)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#525` `WhatsAppApiClient` interface changes after this step is started, breaking `send_message` call signature | 中 | 中 | Pin to a stable interface stub in `tests/unit/conftest.py`; update service call only when #525 is stable; do not block on #525 for unit test structure |
| `whatsapp_conversations` migration conflicts with existing table naming (if another concurrent PR creates it first) | 低 | 高 | `alembic stamp head` to mark DB up-to-date without running migration; add uniqueness constraint on `(tenant_id, message_id)` to prevent duplicates across parallel migrations |
| `message_metadata` JSONB column causes perf issues on large contact history queries | 低 | 中 | Add pagination to `get_conversation_history` (already in scope); add `LIMIT/OFFSET` to SQL query; add composite index on `(tenant_id, contact_id, created_at)` as next-step optimization |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/whatsapp_service.py \
       src/db/models/whatsapp_conversation.py \
       src/db/models/__init__.py \
       src/api/routers/whatsapp.py \
       src/api/routers/__init__.py \
       alembic/versions/<id>_create_whatsapp_conversations.py \
       tests/unit/test_whatsapp_service.py \
       tests/integration/test_whatsapp_service_integration.py \
       alembic/env.py
git commit -m "feat(whatsapp): add WhatsAppService with send_message, link_ticket, get_conversation_history

- WhatsAppConversation ORM model (tenant-scoped, JSONB metadata)
- alembic migration for whatsapp_conversations table
- FastAPI router: POST /whatsapp/send, POST /whatsapp/{id}/link-ticket, GET /whatsapp/history/{contact_id}
- Unit tests (mock WhatsAppApiClient) + integration tests (real DB round-trip)
Closes #526"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(whatsapp): add WhatsAppService class" --body "Closes #526

## Summary
- `WhatsAppService` in `src/services/whatsapp_service.py` with `send_message`, `link_ticket`, `get_conversation_history`
- `WhatsAppConversation` ORM model with `tenant_id` scoping and JSONB `message_metadata`
- Alembic migration for `whatsapp_conversations` table
- FastAPI router exposing 3 endpoints
- 6 unit tests (mock HTTP wrapper) + 4 integration tests (DB round-trip)

## Test plan
- [ ] \`ruff check ...\` → 0 errors
- [ ] \`pytest tests/unit/test_whatsapp_service.py -v\` → 6 passed
- [ ] \`pytest tests/integration/test_whatsapp_service_integration.py -v\` → 4 passed
- [ ] \`alembic upgrade head && alembic downgrade -1 && alembic upgrade head\` → exit 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. Update changelog in this board document
# Add a row to the §Changelog table above with today's date, change "created -> implemented", and your handle
```

---

## 9. 参考

- 同类参考实现：`TBD - 待验证：src/services/customer_service.py — 现有 service 层模式（#525 产出后可对照 WhatsAppApiClient 用法）`
- 父 issue / 关联：#71 (parent), #525 (dependency — WhatsApp API wrapper)
- WhatsApp Business API docs: https://business.whatsapp.com/developers/developer-hub (confirm message status field names with actual API response schema in #525 integration test)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
