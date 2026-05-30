# Webhook Service · Write unit tests for WebhookService and WebhookDeliveryService

| 元数据 | 值 |
|---|---|
| Issue | #722 |
| 分类 | 40-testing |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无（可独立进行；不依赖 #723 集成测试） |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

WebhookService and WebhookDeliveryService are currently covered by zero unit tests. The services handle critical async delivery logic and tenant-scoped webhook registration, yet there is no regression guard for those code paths. Without unit tests, any refactor or extension to these services carries undetected breakage risk.

### 1.2 做完后

- **用户视角**: 无用户可见变化 — 纯底层测试改进。
- **开发者视角**: `tests/unit/test_webhook_service.py` exists and runs as part of the CI suite. Any future change to WebhookService or WebhookDeliveryService will immediately surface regressions via `pytest tests/unit/test_webhook_service.py -v`.

### 1.3 不做什么（剔除）

- [ ] Do NOT mock httpx — that belongs to integration tests (`tests/integration/`).
- [ ] Do NOT write migration or schema tests here — those are covered in integration tests.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → `8 passed`
- `ruff check src/services/webhook_service.py tests/unit/test_webhook_service.py` → `0 errors` (after any required service changes are made)
- All 8 named test cases present: `test_register_webhook_success`, `test_register_webhook_invalid_url_raises_validation`, `test_list_webhooks_returns_only_active_matching_tenant`, `test_delete_webhook_success`, `test_delete_webhook_not_found_raises_not_found`, `test_deliver_queries_matching_webhooks`, `test_deliver_inserts_success_record`, `test_deliver_inserts_failure_record`

---

## 2. 当前现状（起点）

### 2.1 现有实现

`src/services/webhook_service.py` L? — WebhookService/WebhookDeliveryService class definition（#719 完成后确认；实施前需先验证文件存在）

Pattern reference (customer service, confirmed existing):

[`tests/unit/test_customer_service.py`](../../tests/unit/test_customer_service.py) L{1}-L{50}

```{python}
# Mock session pattern from test_customer_service.py
from tests.unit.conftest import make_mock_session, make_customer_handler, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_customer_handler(state)])

@pytest.fixture
def customer_service(mock_db_session):
    return CustomerService(mock_db_session)

async def test_get_customer_success(customer_service):
    result = await customer_service.get_customer(1, tenant_id=1)
    assert result.name == "Acme Corp"
```

### 2.2 涉及文件清单

- 要改：
  - `TBD - 待验证：` `src/services/webhook_service.py` — WebhookService and WebhookDeliveryService must exist and be importable; if not yet shipped by #721, this doc will be updated after #721 merges
- 要建：
  - `tests/unit/test_webhook_service.py` — unit test file (8 test cases)
  - `src/db/models/webhook.py` — Webhook model (由 #719 创建；确认文件存在后再引用)

### 2.3 缺什么

- [ ] No `tests/unit/test_webhook_service.py` exists — zero unit test coverage for WebhookService and WebhookDeliveryService
- [ ] No mock session handlers for `webhook` / `webhook_delivery` tables in `tests/unit/conftest.py`
- [ ] `WebhookService.register_webhook` not covered by any test
- [ ] `WebhookService.list_webhooks` not covered by any test
- [ ] `WebhookService.delete_webhook` not covered by any test
- [ ] `WebhookDeliveryService.deliver` not covered by any test

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_webhook_service.py` | Unit tests for WebhookService (register/list/delete) and WebhookDeliveryService (deliver) — 8 test cases |
| `tests/unit/domain_handlers/webhook.py` | 领域专属 handler 文件，包含 `make_webhook_handler` / `make_webhook_delivery_handler`（不修改共享 conftest.py） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/domain_handlers/webhook.py` — 新建领域专属 handler 文件，包含 `make_webhook_handler` / `make_webhook_delivery_handler`（不修改共享 conftest.py） |
| `TBD - 待验证：` `src/services/webhook_service.py` — no code change; source for test to import against (must exist first) |

### 3.3 新增能力

- **Unit test**：`tests/unit/test_webhook_service.py` — 8 test cases covering registration, listing, deletion, and delivery recording
- **Service method coverage**: `WebhookService.register_webhook`, `WebhookService.list_webhooks`, `WebhookService.delete_webhook`, `WebhookDeliveryService.deliver`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Mock SQLAlchemy session only, not httpx**: Unit tests run fast (<5s) and must not depend on network. httpx mocking belongs in `tests/integration/test_webhook_delivery_service_integration.py` (covered by #721).
- **Handler-based mock (same pattern as test_customer_service.py)**: Reuse `make_mock_session` + per-table handler factories. This avoids global autouse patching and keeps each test isolated.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pytest` | `>=8.0` | async test support via `pytest-asyncio` |

### 4.3 兼容性约束

- Each test defines its own `mock_db_session` fixture — no global autouse patching.
- Session is `AsyncSession` with no default — use `make_mock_session(...)` directly.
- Handlers must return `MockRow` / `MockResult` objects matching SQLAlchemy row interface.
- `make_count_handler(state)` must be included in the mock session for paginated list calls.
- Do NOT import from `src.db.models` using `from src.db.models...` — use `from db.models...` (PYTHONPATH=src).
- Tenant isolation: every query result returned from handlers must be scoped to the `tenant_id` passed in the call.

### 4.4 已知坑

1. **MockRow attribute access** → 规避：ensure `MockRow` exposes dict-like `.key` access matching SQLAlchemy Row behavior (e.g. `row.webhook_id` not `row["webhook_id"]`); verify against `test_customer_service.py` before writing handlers.
2. **Async test functions require `@pytest.mark.asyncio`** → 规避：all 8 test functions must be decorated with `@pytest.mark.asyncio`.
3. **No httpx mocking in unit tests** → 规避：`WebhookDeliveryService.deliver` sends HTTP POST; in unit tests, mock only the DB session. The HTTP layer is exercised in integration tests (#721). If the service is structured so that httpx is called directly in the service (not injected), the unit test will call the service and exercise only the DB write path — this is the intended behavior.

---

## 5. 实现步骤（按顺序）

### Step 1: Verify source files and existing test patterns

Locate the service source and confirm the mock session pattern in the reference file.

操作：
- a) Confirm `src/services/webhook_service.py` exists (will be shipped by #721; if not yet, complete #721 first).
- b) Confirm `tests/unit/test_customer_service.py` exists and review its mock session setup.
- c) Confirm or create domain handlers in `tests/unit/domain_handlers/webhook.py`（不要修改 `tests/unit/conftest.py`）：
   - `make_webhook_handler(state)` — handles SELECT/INSERT/UPDATE/DELETE for `webhooks` table
   - `make_webhook_delivery_handler(state)` — handles SELECT/INSERT for `webhook_deliveries` table
   - `make_count_handler(state)` — handles COUNT queries for pagination

**完成判定**：`ruff check src/services/webhook_service.py` exit 0 / `ruff check tests/unit/conftest.py` exit 0

---

### Step 2: Create tests/unit/test_webhook_service.py with mock session fixture

Create the test file and define the mock session fixture with all required handlers.

操作：
- a) Add imports: `make_mock_session`, `MockState`, `make_webhook_handler`, `make_webhook_delivery_handler`, `make_count_handler` from `tests.unit.conftest` (these are auto-discovered via `_load_domain_handler_modules()` in conftest — no need to edit conftest itself)
- b) Add `WebhookService` and `WebhookDeliveryService` imports from the service module
- c) Define `mock_db_session` fixture with all three handlers (webhook, webhook_delivery, count)
- d) Define `webhook_service` fixture: `WebhookService(mock_db_session)`
- e) Define `delivery_service` fixture: `WebhookDeliveryService(mock_db_session)`

> **注意**：`tests/unit/domain_handlers/webhook.py` 必须通过 `__all__` 导出 `make_webhook_handler`、`make_webhook_delivery_handler`、`get_handlers`，这样 conftest 的 `_load_domain_handler_modules()` 才能自动发现它们。

示例代码：

```python
from tests.unit.conftest import (
    make_mock_session,
    MockState,
    make_webhook_handler,
    make_webhook_delivery_handler,
    make_count_handler,
)
from services.webhook_service import WebhookService, WebhookDeliveryService

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([
        make_webhook_handler(state),
        make_webhook_delivery_handler(state),
        make_count_handler(state),
    ])

@pytest.fixture
def webhook_service(mock_db_session):
    return WebhookService(mock_db_session)

@pytest.fixture
def delivery_service(mock_db_session):
    return WebhookDeliveryService(mock_db_session)
```

**完成判定**：`ruff check tests/unit/test_webhook_service.py` exit 0

---

### Step 3: Write WebhookService.register_webhook test cases

Cover success and validation error paths.

操作：
- a) `test_register_webhook_success` — call `webhook_service.register_webhook(tenant_id=1, url="https://example.com/webhook", event_type="ticket.created")`, assert a `WebhookModel` is returned with correct fields
- b) `test_register_webhook_invalid_url_raises_validation` — call with an invalid URL string (e.g. `"not-a-url"`), assert `ValidationException` is raised

示例代码：

```python
@pytest.mark.asyncio
async def test_register_webhook_success(webhook_service, mock_db_session):
    state = mock_db_session._state  # access MockState to seed rows if needed
    state.webhooks.clear()

    result = await webhook_service.register_webhook(
        tenant_id=1,
        url="https://example.com/hook",
        events=["ticket.created"],
    )
    assert result.url == "https://example.com/hook"
    assert result.tenant_id == 1

@pytest.mark.asyncio
async def test_register_webhook_invalid_url_raises_validation(webhook_service):
    with pytest.raises(ValidationException):
        await webhook_service.register_webhook(
            tenant_id=1,
            url="not-a-valid-url",
            events=["ticket.created"],
        )
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_service.py::test_register_webhook_success tests/unit/test_webhook_service.py::test_register_webhook_invalid_url_raises_validation -v` → `2 passed`

---

### Step 4: Write WebhookService.list_webhooks and delete test cases

Cover listing (tenant isolation) and delete (success + not-found).

操作：
- a) `test_list_webhooks_returns_only_active_matching_tenant` — seed two webhooks for tenant_id=1 and one for tenant_id=2; call `list_webhooks(tenant_id=1)`; assert only tenant 1's webhooks are returned (count=2)
- b) `test_delete_webhook_success` — call `delete_webhook(webhook_id=X, tenant_id=1)`, assert it returns the deleted entity
- c) `test_delete_webhook_not_found_raises_not_found` — call with a non-existent webhook_id, assert `NotFoundException` is raised

示例代码：

```python
@pytest.mark.asyncio
async def test_list_webhooks_returns_only_active_matching_tenant(webhook_service, mock_db_session):
    state = mock_db_session._state
    state.webhooks.clear()
    state.webhooks.append(WebhookModel(id=10, tenant_id=1, url="https://a.com", is_active=True))
    state.webhooks.append(WebhookModel(id=11, tenant_id=1, url="https://b.com", is_active=True))
    state.webhooks.append(WebhookModel(id=20, tenant_id=2, url="https://c.com", is_active=True))

    items, total = await webhook_service.list_webhooks(tenant_id=1)
    assert total == 2
    assert all(w.tenant_id == 1 for w in items)

@pytest.mark.asyncio
async def test_delete_webhook_not_found_raises_not_found(webhook_service):
    with pytest.raises(NotFoundException):
        await webhook_service.delete_webhook(webhook_id=9999, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_service.py::test_list_webhooks_returns_only_active_matching_tenant tests/unit/test_webhook_service.py::test_delete_webhook_success tests/unit/test_webhook_service.py::test_delete_webhook_not_found_raises_not_found -v` → `3 passed`

---

### Step 5: Write WebhookDeliveryService.deliver test cases

Cover webhook query and delivery record insertion (success and failure paths).

操作：
- a) `test_deliver_queries_matching_webhooks` — seed a webhook for event `ticket.created`; call `deliver(event_type="ticket.created", payload={...})`; verify the handler received the correct SELECT with `tenant_id` filter and `event_type` filter
- b) `test_deliver_inserts_success_record` — call `deliver`, assert a `WebhookDeliveryModel` with `status="success"` was inserted into the mock state
- c) `test_deliver_inserts_failure_record` — call `deliver` with a scenario that triggers a failure path (e.g. webhook URL raises), assert a `WebhookDeliveryModel` with `status="failed"` was inserted

示例代码：

```python
@pytest.mark.asyncio
async def test_deliver_queries_matching_webhooks(delivery_service, mock_db_session):
    state = mock_db_session._state
    state.webhooks.clear()
    state.webhooks.append(WebhookModel(
        id=5, tenant_id=1, url="https://hook.example.com",
        events=["ticket.created"], is_active=True,
    ))

    await delivery_service.deliver(
        event_type="ticket.created",
        payload={"ticket_id": 42},
        tenant_id=1,
    )
    # Verify the handler was invoked with matching criteria
    calls = state.webhook_handler_calls
    assert any(call.kwargs.get("event_type") == "ticket.created" for call in calls)

@pytest.mark.asyncio
async def test_deliver_inserts_failure_record(delivery_service, mock_db_session):
    state = mock_db_session._state
    state.webhooks.clear()
    state.webhooks.append(WebhookModel(
        id=5, tenant_id=1, url="http://unreachable.invalid",
        events=["ticket.created"], is_active=True,
    ))

    await delivery_service.deliver(
        event_type="ticket.created",
        payload={"ticket_id": 42},
        tenant_id=1,
    )
    # Delivery attempt should be recorded regardless of HTTP outcome
    assert any(
        d.status in ("success", "failed")
        for d in state.webhook_deliveries
    )
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_service.py::test_deliver_queries_matching_webhooks tests/unit/test_webhook_service.py::test_deliver_inserts_success_record tests/unit/test_webhook_service.py::test_deliver_inserts_failure_record -v` → `3 passed`

---

### Step 6: Run full test file and lint

Verify all 8 test cases pass and lint is clean.

操作：
- a) `PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v`
- b) `ruff check tests/unit/test_webhook_service.py src/services/webhook_service.py`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → `8 passed` / `ruff check tests/unit/test_webhook_service.py src/services/webhook_service.py` → `0 errors`

---

## 6. 验收

- `ruff check src/services/webhook_service.py tests/unit/test_webhook_service.py` → `0 errors`
- `PYTHONPATH=src pytest tests/unit/test_webhook_service.py -v` → `8 passed`
- All 8 named test functions present: `test_register_webhook_success`, `test_register_webhook_invalid_url_raises_validation`, `test_list_webhooks_returns_only_active_matching_tenant`, `test_delete_webhook_success`, `test_delete_webhook_not_found_raises_not_found`, `test_deliver_queries_matching_webhooks`, `test_deliver_inserts_success_record`, `test_deliver_inserts_failure_record`
- `ruff check tests/unit/conftest.py` (if modified) → `0 errors`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| WebhookService source not yet shipped by #721 | 中 | 高 | Block on #721 merging first; update §2.1 ref once #721 is merged; re-run Step 1 verification before proceeding |
| Mock handlers in conftest.py insufficient for WebhookService method signatures | 低 | 中 | Add method-specific assertions in handlers; extend `MockRow` to handle new attribute names as they surface |
| 8 tests pass but integration tests in #721 fail due to missing DB model | 低 | 中 | Add `make_webhook_handler` / `make_webhook_delivery_handler` with full INSERT/UPDATE/DELETE coverage; this does not block the unit test PR |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_webhook_service.py
git add tests/unit/domain_handlers/webhook.py  # new domain handlers (do NOT modify shared conftest.py)
git add src/services/webhook_service.py  # if any service changes were required
git commit -m "test(webhook): add unit tests for WebhookService and WebhookDeliveryService"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#722): unit tests for WebhookService and WebhookDeliveryService" --body "Closes #722"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../tests/unit/test_customer_service.py)
- Mock session helpers：[`tests/unit/conftest.py`](../../tests/unit/conftest.py)
- Integration test counterpart：[`tests/integration/test_webhook_delivery_service_integration.py`](../../tests/integration/test_webhook_delivery_service_integration.py) (covered by #721)
- 父 issue：#496
- 前置依赖：#721

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
