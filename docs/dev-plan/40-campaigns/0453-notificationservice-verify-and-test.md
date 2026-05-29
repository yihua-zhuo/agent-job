# Notifications · Verify and test NotificationService

| 元数据 | 值 |
|---|---|
| Issue | #453 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [0452 — add notification ORM model & migration](0452-add-notification-orm-model-and-migration.md) |
| 启用后赋能 | [0461 — add workflow ORM model & migration](0461-add-workflow-orm-model-and-migration.md), [0464 — build automation rules engine](0464-build-workflowservice-with-crud-execute-methods.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

NotificationService is the central touch-point for all in-app, email, SMS, and push notification delivery in the CRM. Before wiring up downstream consumers (workflows, automation rules, campaign triggers), every one of its 9 public methods must be confirmed present, correctly implemented, and covered by tests. Without this verification, downstream development will build on an unverified foundation and edge-case bugs (tenant leakage, incorrect return types, missing error handling) will surface only in production.

### 1.2 做完后

- **用户视角**：No user-visible change — this is a pure verification and test-coverage task.
- **开发者视角**：After this board, `NotificationService` in `src/services/notification_service.py` will have confirmed implementations of all 9 methods, a typed router in `src/api/routers/notification_router.py`, passing unit tests in `tests/unit/test_notification_service.py`, and passing integration tests in `tests/integration/test_notification_integration.py`. Developers can confidently call `send_notification`, `subscribe_channel`, `get_unread_count`, etc. in automation and campaign services without guessing at the API surface.

### 1.3 不做什么（剔除）

- [ ] Do not add new NotificationService methods beyond the 9 listed below
- [ ] Do not change the existing API surface (method signatures, route paths) — only verify and add tests
- [ ] Do not implement actual email/SMS/push delivery infrastructure (that belongs to a separate notification-transport issue)

### 1.4 关键 KPI

- [KPI 1: `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → ≥ 8 passed]
- [KPI 2: `PYTHONPATH=src pytest tests/integration/test_notification_integration.py -v` → ≥ 6 passed]
- [KPI 3: `ruff check src/services/notification_service.py src/api/routers/notification_router.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：在 `src/services/` 目录下搜索 `class NotificationService` — 需确认文件路径和行号

TBD - 待验证：在 `src/api/routers/` 目录下搜索 `notification` 路由文件 — 需确认 router 文件路径

TBD - 待验证：ORM model `Notification` 应已在 `src/db/models/` 下，由 #452 创建

TBD - 待验证：9 个方法的具体签名（需读取 `notification_service.py` 确认参数名和返回类型）

### 2.2 涉及文件清单

- 要改：
  - TBD（验证后列出实际需要修改的文件）
- 要建：
  - `src/db/models/notification.py` — Notification ORM model (from #452)
  - `alembic/versions/<id>_add_notification_table.py` — migration for notifications table (from #452)
  - `tests/unit/test_notification_service.py` — unit tests for all 9 methods (create if missing)
  - `tests/integration/test_notification_integration.py` — integration tests against real Postgres (create if missing)

### 2.3 缺什么

- [ ] Confirmation that `NotificationService` class exists in `src/services/` with all 9 methods
- [ ] Unit test file `tests/unit/test_notification_service.py` — verify present, add missing test cases
- [ ] Integration test file `tests/integration/test_notification_integration.py` — verify present, add missing test cases
- [ ] Verification that `subscribe_channel` / `unsubscribe_channel` include `tenant_id` in their SQL filters
- [ ] Verification that all service methods raise `AppException` subclasses on errors (not return dict error)
- [ ] Verification that router endpoints use `session: AsyncSession = Depends(get_db)` (not `async with get_db()`)
- [ ] Verification that `notification_router.py` is included in `src/main.py` app
- [ ] Notification channels enum (EMAIL, SMS, PUSH, IN_APP) defined and imported in the service

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_notification_service.py` | Unit tests for all 9 NotificationService methods using mock DB |
| `tests/integration/test_notification_integration.py` | Integration tests against real PostgreSQL for all 9 methods |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD（验证后列出实际修改的文件） | Verify and document; no functional changes expected unless gaps found |

### 3.3 新增能力

- **Service method**：`send_notification(session, tenant_id, user_id, channel, content) -> NotificationModel`
- **Service method**：`get_notification(session, tenant_id, notification_id) -> NotificationModel`
- **Service method**：`list_notifications(session, tenant_id, user_id, page, page_size) -> tuple[list, int]`
- **Service method**：`mark_as_read(session, tenant_id, notification_id) -> NotificationModel`
- **Service method**：`mark_all_as_read(session, tenant_id, user_id) -> int` (returns count)
- **Service method**：`get_unread_count(session, tenant_id, user_id) -> int`
- **Service method**：`delete_notification(session, tenant_id, notification_id) -> None`
- **Service method**：`subscribe_channel(session, tenant_id, user_id, channel) -> SubscriptionModel`
- **Service method**：`unsubscribe_channel(session, tenant_id, user_id, channel) -> None`
- **API router**：notification endpoints in `src/api/routers/notification_router.py`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Verify-only, no refactor** — choose to not change the service implementation unless a clear bug is found. The goal is test coverage, not redesign. Changing implementation in a verify-and-test issue risks scope creep.
- **Mock DB for unit tests, real Postgres for integration tests** — consistent with the rest of the CRM test suite (see `tests/unit/conftest.py` for mock patterns).

### 4.2 版本约束

<!-- 无新增依赖 -->

### 4.3 兼容性约束

- Multi-tenant enforcement: every SQL query in all 9 methods must include `WHERE tenant_id = :tenant_id`. Pay special attention to `subscribe_channel` and `unsubscribe_channel` — verify they filter by `tenant_id`.
- Service methods return ORM/model objects — do NOT call `.to_dict()` inside the service class.
- Service methods raise `AppException` subclasses (`NotFoundException`, `ValidationException`, etc.) — do NOT return `ApiResponse.error()`.
- Router uses `session: AsyncSession = Depends(get_db)` — do NOT use `async with get_db() as session:`.
- Import paths follow PYTHONPATH=src convention: `from db.models...`, `from services...`, `from api.routers...` — never `from src.db.models...`.

### 4.4 已知坑

1. **SQLAlchemy `metadata` column name conflict** → Avoid：If a `Notification` ORM model defines a column named `metadata`, it collides with `Base.metadata` (the `MetaData` object) and crashes at class definition. Use `event_metadata`, `payload`, or `attrs` instead. This is verified as part of the ORM model check from #452.
2. **Alembic autogenerate writes `sa.JSON()` instead of `sa.JSONB()`** → Workaround：If the notification table uses a JSON column for payload/metadata, manually edit the generated migration to use `JSONB` instead of `JSON`. Check `alembic/versions/<id>_add_notification_table.py` from #452.
3. **Alembic autogenerate drops `timezone=True` on DateTime columns** → Workaround：If the migration uses naive `DateTime()` instead of `DateTime(timezone=True)`, manually correct the column type in the generated migration.
4. **Mock session handler for `subscribe_channel` / `unsubscribe_channel` may not exist** → Workaround：If `tests/unit/conftest.py` does not have a `make_subscription_handler` factory, create one similar to `make_customer_handler` using `MockState` before writing unit tests for those methods.
5. **Integration tests require the `notifications` table to exist** → Prerequisite：Run `alembic upgrade head` in the test database before running integration tests. The `db_schema` fixture in `tests/integration/conftest.py` handles this automatically; do not manually create tables in integration tests.

---

## 5. 实现步骤（按顺序）

### Step 1: Verify NotificationService class and read method signatures

Inspect `src/services/notification_service.py` — confirm all 9 methods exist and note their exact signatures.

操作：
- a) `Grep` for `class NotificationService` in `src/services/` — record file path
- b) Read the file — confirm these 9 methods are present: `send_notification`, `get_notification`, `list_notifications`, `mark_as_read`, `mark_all_as_read`, `get_unread_count`, `delete_notification`, `subscribe_channel`, `unsubscribe_channel`
- c) Record each method's parameters, return type annotations, and whether `tenant_id` appears in all SQL queries
- d) Check that the service constructor takes `session: AsyncSession` with no default value

完成判定：File `src/services/notification_service.py` confirmed present with all 9 methods documented.

### Step 2: Verify notification router and channels enum

Inspect `src/api/routers/` for the notification router file and check that notification channels enum (EMAIL, SMS, PUSH, IN_APP) is defined.

操作：
- a) `Grep` for `notification` router file in `src/api/routers/`
- b) Read the router file — confirm endpoints for all 9 service methods exist
- c) Verify each endpoint uses `session: AsyncSession = Depends(get_db)` (not `async with`)
- d) Verify channels enum is imported and used in route handlers

完成判定：Router file confirmed present with notification endpoints using correct FastAPI patterns.

### Step 3: Verify ORM model from #452

Confirm `src/db/models/notification.py` (or similar) exists with the correct `Notification` model.

操作：
- a) `Grep` for `class Notification` in `src/db/models/`
- b) Verify `tenant_id` column exists and is indexed
- c) Verify `metadata`-adjacent column uses a name other than `metadata` (e.g., `event_metadata`, `payload`, `attrs`)

完成判定：`src/db/models/notification.py` confirmed with `Notification` ORM model present.

### Step 4: Check or create unit test file

Verify `tests/unit/test_notification_service.py` exists. If present, check coverage. If absent, create it using the mock pattern from `tests/unit/conftest.py`.

操作：
- a) List files in `tests/unit/` matching `test_notification*`
- b) If file exists: review each of the 9 methods — assert each has at least one test case
- c) If file does not exist: create it with a `mock_db_session` fixture and test methods for each of the 9 service methods
- d) Use `make_mock_session` from `tests/unit/conftest.py` with appropriate handlers; add a `make_subscription_handler` if it does not exist

示例代码（如有）：

```python
# tests/unit/test_notification_service.py (excerpt)
import pytest
from unittest.mock import AsyncMock

from tests.unit.conftest import make_mock_session, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([/* notification handler */], state)

@pytest.fixture
def notification_service(mock_db_session):
    from services.notification_service import NotificationService
    return NotificationService(mock_db_session)

class TestNotificationService:
    async def test_send_notification(self, notification_service, mock_db_session):
        # arrange
        state = MockState()
        notification_id = state.notifications.insert({
            "tenant_id": 1, "user_id": 10,
            "channel": "EMAIL", "content": "test",
            "is_read": False
        })
        # act
        result = await notification_service.send_notification(
            session=mock_db_session,
            tenant_id=1,
            user_id=10,
            channel="EMAIL",
            content="test"
        )
        # assert
        assert result.id == notification_id
        assert result.is_read is False
```

完成判定：`tests/unit/test_notification_service.py` exists and covers all 9 methods. `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → ≥ 8 passed.

### Step 5: Check or create integration test file

Verify `tests/integration/test_notification_integration.py` exists. If present, check coverage. If absent, create it using the `db_schema`, `tenant_id`, and `async_session` fixtures from `tests/integration/conftest.py`.

操作：
- a) List files in `tests/integration/` matching `test_notification*`
- b) If file exists: review — assert each of the 9 methods has at least one integration test
- c) If file does not exist: create it with `@pytest.mark.integration` tests using real DB

示例代码（如有）：

```python
# tests/integration/test_notification_integration.py (excerpt)
import pytest
from pytest.mark.integration import db_schema, tenant_id, async_session

@pytest.mark.integration
class TestNotificationServiceIntegration:
    async def test_list_notifications_pagination(
        self, db_schema, tenant_id, async_session
    ):
        from services.notification_service import NotificationService
        svc = NotificationService(async_session)
        # seed data
        for i in range(5):
            await svc.send_notification(
                session=async_session,
                tenant_id=tenant_id,
                user_id=100,
                channel="IN_APP",
                content=f"Notification {i}"
            )
        # act
        items, total = await svc.list_notifications(
            session=async_session,
            tenant_id=tenant_id,
            user_id=100,
            page=1,
            page_size=3
        )
        # assert
        assert len(items) == 3
        assert total == 5

    async def test_get_unread_count(
        self, db_schema, tenant_id, async_session
    ):
        from services.notification_service import NotificationService
        svc = NotificationService(async_session)
        count = await svc.get_unread_count(
            session=async_session,
            tenant_id=tenant_id,
            user_id=100
        )
        assert isinstance(count, int)
        assert count >= 0
```

完成判定：`tests/integration/test_notification_integration.py` exists and covers all 9 methods. `PYTHONPATH=src pytest tests/integration/test_notification_integration.py -v` → ≥ 6 passed.

### Step 6: Run unit tests

操作：
- a) `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v`
- b) If any test fails due to a missing handler in `conftest.py`, add the handler before retrying
- c) If any test fails due to an implementation bug (not a test bug), document in issue notes and decide with team whether to fix in this board or defer

完成判定：`pytest tests/unit/test_notification_service.py -v` → all tests passed (≥ 8 passed).

### Step 7: Run integration tests

操作：
- a) Confirm docker compose test database is running: `docker compose -f configs/docker-compose.test.yml ps`
- b) Run `PYTHONPATH=src pytest tests/integration/test_notification_integration.py -v`
- c) If tests fail due to missing migration, run `alembic upgrade head` against the test DB first

完成判定：`pytest tests/integration/test_notification_integration.py -v` → all tests passed (≥ 6 passed).

### Step 8: Lint and final review

操作：
- a) `ruff check src/services/notification_service.py src/api/routers/notification_router.py`
- b) `ruff format --check src/services/notification_service.py src/api/routers/notification_router.py`
- c) Verify no `from src.db.models` import paths exist (must be `from db.models`)
- d) Verify no `async with get_db()` usage in the router

完成判定：`ruff check` and `ruff format --check` both exit 0 for all modified files.

---

## 6. 验收

- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → ≥ 8 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_notification_integration.py -v` → ≥ 6 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0 (verify migration from #452 applies cleanly)
- [ ] `ruff check src/services/notification_service.py src/api/routers/notification_router.py` → 0 errors
- [ ] `ruff format --check src/services/notification_service.py src/api/routers/notification_router.py` → 0 errors
- [ ] All 9 NotificationService methods verified present with correct signatures including `tenant_id` in every SQL filter

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Unit test file `tests/unit/test_notification_service.py` does not exist and must be created from scratch | 中 | 中 | Create the file using the mock pattern from `tests/unit/conftest.py`; use `MockState` for stateful ID generation; create `make_subscription_handler` if not present |
| Integration tests fail due to missing migration from #452 not being applied to test DB | 低 | 中 | Run `alembic upgrade head` against test DB before running integration suite; this is a prerequisite step in Step 7 |
| `subscribe_channel` / `unsubscribe_channel` do not filter by `tenant_id` (multi-tenant leak) | 低 | 高 | Document the bug and open a separate issue; do NOT attempt to fix in this verify-and-test board — scope is verification only |
| Notification router not included in `src/main.py` | 低 | 中 | Document which router is missing; add the `include_router` call to `main.py` as a small fix in this board |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_notification_service.py tests/integration/test_notification_integration.py
git commit -m "test(notifications): verify all 9 NotificationService methods with unit and integration tests"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#453): verify and add tests for NotificationService" --body "Closes #453"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — service pattern (raises `AppException`, returns ORM objects)
- 同类参考实现：[`tests/unit/test_customer_service.py`](../../tests/unit/test_customer_service.py) — unit test pattern (mock DB, stateful fixture)
- 同类参考实现：[`tests/integration/conftest.py`](../../tests/integration/conftest.py) — integration test fixtures (`db_schema`, `tenant_id`, `async_session`)
- 父 issue / 关联：#451 (parent), #452 (dependency — notification ORM model and migration)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
