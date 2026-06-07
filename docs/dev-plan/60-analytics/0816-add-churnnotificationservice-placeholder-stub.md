# ChurnNotificationService · Stub for churn alert dispatch

| 元数据 | 值 |
|---|---|
| Issue | #816 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.25 工作日 |
| 依赖 | #815（板块文件路径待验证） |
| 启用后赋能 | #817, #47 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The churn detection pipeline (epic #575) needs a notification dispatch point so that when a customer's churn score crosses a threshold, the system has a well-defined seam to send alerts. Before wiring real Slack/Email transport (deferred to #47), the batch job (#817) needs a typed service it can call without coupling to transport specifics or inlining a `print()`/`logger.info` call. Without this stub, #817 either has to inline a log statement (hard to swap later without a refactor PR) or blocks on #47 (which adds weeks of unrelated scope around template management, retry, and channel selection).

### 1.2 做完后

- **用户视角**：No user-visible change — this is a pure backend seam. The `[STUB]` WARNING line written to the application log is the only runtime artifact.
- **开发者视角**：`ChurnNotificationService` is importable from `services.churn_notification_service` and exposes an `async send_churn_alert(customer_id, tenant_id, old_score, new_score)` method. The batch job (#817) can `Depends(get_db)`-inject it and `await svc.send_churn_alert(...)` at the threshold-crossing branch. The real Slack/Email wiring in #47 replaces only the method body — no call-site edits, no constructor change.

### 1.3 不做什么（剔除）

- [ ] Real Slack/Email/SMS/Webhook transport wiring (owned by #47)
- [ ] Notification template management, i18n, or per-tenant copy
- [ ] Retry, exponential backoff, or dead-letter handling
- [ ] User notification preferences / opt-out / quiet hours
- [ ] Persistence of sent notifications (no `notifications` audit table, no delivery-status tracking)

### 1.4 关键 KPI

- `ruff check src/services/churn_notification_service.py` → 0 errors
- `ruff check tests/unit/test_churn_notification_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_churn_notification_service.py -v` → 3 passed
- `PYTHONPATH=src pytest tests/unit/ -v` → all previously-passing tests still pass, plus the 3 new ones
- `PYTHONPATH=src python -c "from services.churn_notification_service import ChurnNotificationService"` → exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - （无 — this board creates a new module; no existing files are modified）
- 要建：
  - `src/services/churn_notification_service.py` — `ChurnNotificationService` class with `send_churn_alert` stub method
  - `tests/unit/test_churn_notification_service.py` — unit tests verifying constructor signature, async-ness, and `[STUB]` log emission

### 2.3 缺什么

- [ ] No `ChurnNotificationService` exists — churn score threshold breaches have nowhere to dispatch to
- [ ] Batch job (#817) has no typed service seam; would be forced to inline a `logger.warning(...)` call as a workaround, making the #47 swap a cross-file refactor instead of a single-body edit
- [ ] #47 (real Slack/Email wiring) has no stable interface to implement against until this stub pins the method signature
- [ ] No unit test pattern established in this repo for "logs a warning and returns None" service stubs (this board sets the precedent)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/churn_notification_service.py` | `ChurnNotificationService(session: AsyncSession)` stub — logs `[STUB]` WARNING and returns `None` |
| `tests/unit/test_churn_notification_service.py` | Unit tests for the stub: constructor stores session, method is a coroutine, call emits the expected `[STUB]` log line |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| （无） | No existing file is modified by this board |

### 3.3 新增能力

- **Service class**：`ChurnNotificationService` in `src/services/churn_notification_service.py` with `__init__(self, session: AsyncSession) -> None` storing `self.session = session`
- **Service method**：`async send_churn_alert(self, customer_id: int, tenant_id: int, old_score: float, new_score: float) -> None` — emits a single WARNING-level `[STUB] churn alert: customer={customer_id} tenant={tenant_id} old={old_score} new={new_score}` log line via `logging.getLogger(__name__)` and returns
- **Unit test fixture**：`mock_db_session` returning an `AsyncMock` (no real SQL is issued by the stub body, so no `make_*_handler` from `tests/unit/conftest.py` is needed)
- **Unit test coverage**：3 tests — (a) constructor stores `session`, (b) `send_churn_alert` is `asyncio.iscoroutinefunction(...)`, (c) `caplog` captures the `[STUB]` log line at WARNING level on logger `services.churn_notification_service`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Stub returns `None` rather than raising `NotImplementedError`**：The batch job calls this on the happy path of a threshold breach. An exception would force every call site to wrap in `try/except` and decide whether "not implemented" is fatal — it isn't. `None` signals "success-without-side-effect"; #47 can later widen the return type to `bool` (delivered?) or a sent-message-id without breaking the call-site contract.
- **Method is `async def` even though the stub body never `await`s**：Real Slack/Email/SMTP calls in #47 will be `await`ed I/O. Making the stub `async` now means #47 changes only the method body — no call-site edits, no `def` → `async def` propagation downstream.
- **`session: AsyncSession` is stored on `self` but unused in the stub body**：Mandatory by CLAUDE.md §Service Pattern. The `self.session = session` assignment is non-negotiable so that when #47 replaces the body with a real implementation that issues SQL (e.g. looking up customer email), no constructor change is needed.
- **Logger is `logging.getLogger(__name__)`, not a hardcoded `"churn"` name**：Resolves to `services.churn_notification_service` under `PYTHONPATH=src`. This lets tests target the exact logger in `caplog` and lets prod log routing / log-level config pick it up by dotted path.

### 4.2 版本约束

（无 — no new pip dependencies are introduced. `logging` and `sqlalchemy.ext.asyncio.AsyncSession` are already on the import path.）

### 4.3 兼容性约束

- Service `__init__` must type `session: AsyncSession` with **no default** — `session: AsyncSession | None = None` is forbidden (CLAUDE.md §Service Pattern)
- Module must be importable as `from services.churn_notification_service import ChurnNotificationService` (project uses `PYTHONPATH=src`; `from src.services...` is forbidden per CLAUDE.md)
- `send_churn_alert` signature is the public contract: `customer_id: int`, `tenant_id: int`, `old_score: float`, `new_score: float`, in that order, returning `None`. #47 must preserve this signature even when widening the implementation.
- `tenant_id` is included in the log line for traceability even though the stub issues no SQL — the real #47 implementation will use it for `WHERE tenant_id = :tenant_id` filters
- No new exceptions are raised by the stub; #47 may introduce domain-specific exceptions and must document them when it lands

### 4.4 已知坑

1. **Async signature drift if written as `def` instead of `async def`** → The batch job will `await svc.send_churn_alert(...)`; calling a sync function with `await` raises `TypeError: object dict can't be used in 'await' expression` at runtime, not at import time. Keep `async def` from day one — do not "simplify" it because the body has no `await`.
2. **`session=None` default would be a silent landmine** → Adding `session: AsyncSession | None = None` "to make the stub easier to test" violates CLAUDE.md and forces a constructor rewrite when #47 lands a real implementation. Type it strictly and pass a real `AsyncMock`/`AsyncSession` in tests.
3. **Logger-name mismatch in `caplog` under `PYTHONPATH=src`** → `__name__` resolves to `services.churn_notification_service`, not `src.services.churn_notification_service`. Tests must use `caplog.set_level(logging.WARNING, logger="services.churn_notification_service")` (exact dotted path) — a substring match like `logger="churn_notification_service"` will fail to capture.
4. **Float formatting in the log line** → Use `%s` placeholders passed to `logger.warning(...)`, not f-strings. f-strings eagerly format `old_score`/`new_score` even when the WARNING level is filtered out, wasting CPU on hot paths; `%s`-style lazy formatting defers it until the handler decides to emit.
5. **Alembic autogen tendency** → Not applicable to this board (no migration is created). If a future board adds a `notifications` audit table, watch for `sa.JSON()` being emitted where `sa.JSONB()` is intended and for `timezone=True` being dropped from `DateTime` columns (see CLAUDE.md §Alembic Migrations).

---

## 5. 实现步骤（按顺序）

### Step 1: Create the service stub file

Create `src/services/churn_notification_service.py` with the `ChurnNotificationService` class. The constructor stores `self.session`; `send_churn_alert` is `async def` and logs a single `[STUB]` WARNING line via `logging.getLogger(__name__)`, then returns `None`.

操作：
- a) Create file `src/services/churn_notification_service.py` at the repo root
- b) Add module docstring (one line) and `import logging` + `from sqlalchemy.ext.asyncio import AsyncSession`
- c) Add module-level `logger = logging.getLogger(__name__)`
- d) Add `class ChurnNotificationService:` with `def __init__(self, session: AsyncSession) -> None:` that does `self.session = session`
- e) Add `async def send_churn_alert(self, customer_id: int, tenant_id: int, old_score: float, new_score: float) -> None:` that calls `logger.warning("[STUB] churn alert: customer=%s tenant=%s old=%s new=%s", customer_id, tenant_id, old_score, new_score)` and returns implicitly

示例代码：

```python
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ChurnNotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def send_churn_alert(
        self,
        customer_id: int,
        tenant_id: int,
        old_score: float,
        new_score: float,
    ) -> None:
        logger.warning(
            "[STUB] churn alert: customer=%s tenant=%s old=%s new=%s",
            customer_id,
            tenant_id,
            old_score,
            new_score,
        )
```

**完成判定**：`ruff check src/services/churn_notification_service.py` → exit 0, 0 errors; `PYTHONPATH=src python -c "from services.churn_notification_service import ChurnNotificationService; import inspect; assert not inspect.iscoroutinefunction is not None"` → exit 0

### Step 2: Create the unit test file

Create `tests/unit/test_churn_notification_service.py` with three tests. Because the stub body never touches `self.session`, the mock session can be a plain `AsyncMock` — no `make_*_handler` from `tests/unit/conftest.py` is needed.

操作：
- a) Create file `tests/unit/test_churn_notification_service.py`
- b) Add a `mock_db_session` fixture that returns `AsyncMock()` (no spec required; the stub never calls methods on it)
- c) Add a `churn_notification_service` fixture that instantiates `ChurnNotificationService(mock_db_session)`
- d) Test 1 — constructor stores session: instantiate `ChurnNotificationService(mock_db_session)`, assert `svc.session is mock_db_session`
- e) Test 2 — method is a coroutine: `assert inspect.iscoroutinefunction(ChurnNotificationService.send_churn_alert)`
- f) Test 3 — `[STUB]` log emission: use `caplog.set_level(logging.WARNING, logger="services.churn_notification_service")`, `await svc.send_churn_alert(1, 2, 0.3, 0.8)`, assert exactly one record at WARNING with message `"[STUB] churn alert: customer=1 tenant=2 old=0.3 new=0.8"`

示例代码：

```python
import asyncio
import inspect
import logging
from unittest.mock import AsyncMock

import pytest

from services.churn_notification_service import ChurnNotificationService


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def churn_notification_service(mock_db_session):
    return ChurnNotificationService(mock_db_session)


class TestChurnNotificationService:
    def test_constructor_stores_session(self, mock_db_session):
        svc = ChurnNotificationService(mock_db_session)
        assert svc.session is mock_db_session

    def test_send_churn_alert_is_coroutine(self):
        assert inspect.iscoroutinefunction(ChurnNotificationService.send_churn_alert)

    async def test_send_churn_alert_emits_stub_log(self, churn_notification_service, caplog):
        caplog.set_level(logging.WARNING, logger="services.churn_notification_service")
        await churn_notification_service.send_churn_alert(1, 2, 0.3, 0.8)
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING
        assert caplog.records[0].getMessage() == "[STUB] churn alert: customer=1 tenant=2 old=0.3 new=0.8"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_notification_service.py -v` → `3 passed`

### Step 3: Lint the new test file and re-run the full unit suite

Confirm the test file passes ruff and that no previously-passing unit test regresses.

操作：
- a) `ruff check src/services/churn_notification_service.py tests/unit/test_churn_notification_service.py`
- b) `PYTHONPATH=src pytest tests/unit/ -v`

**完成判定**：`ruff` → 0 errors on both files; `pytest tests/unit/ -v` → all previously-passing tests still pass, plus the 3 new tests in `test_churn_notification_service.py`

---

## 6. 验收

- [ ] `ruff check src/services/churn_notification_service.py` → 0 errors
- [ ] `ruff check tests/unit/test_churn_notification_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_notification_service.py -v` → `3 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → all passed (no regressions in pre-existing unit tests)
- [ ] `PYTHONPATH=src python -c "from services.churn_notification_service import ChurnNotificationService"` → exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Batch job (#817) lands before this stub and inlines a `logger.warning(...)` call as a workaround | 低 | 中 | #817 ships the inline log first; this board's PR lands afterward and #817's follow-up commit swaps the inline call for `await ChurnNotificationService(session).send_churn_alert(...)`. No data loss, no schema impact, no rollback needed. |
| `send_churn_alert` signature differs from what #47 needs (e.g. real impl needs a `channel: str` or `template_id: int` param) | 低 | 中 | When #47 lands, add the new param with a default value (`channel: str = "stub"`) so existing call sites in #817 keep working. Do NOT remove or reorder existing positional params — `customer_id`, `tenant_id`, `old_score`, `new_score` are frozen. |
| Test logger-name assertion breaks under a different `PYTHONPATH` (e.g. `python -m pytest` from `src/`) | 中 | 低 | If the logger name resolves to `src.services.churn_notification_service` instead of `services.churn_notification_service`, switch the `caplog` fixture to `logger=__name__.replace("src.", "", 1)` or set `caplog` to `logger=None` (capture-all) and assert on the `name` attribute of the captured record. |
| `ruff` rule evolution flags `%s`-style logging in the stub body (some style guides prefer f-strings everywhere) | 低 | 低 | Add a per-file `# noqa: G004` (or the current equivalent rule) on the `logger.warning` line, citing that lazy `%s` formatting is intentional for log-level filtering performance. Do NOT convert to an f-string. |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/churn_notification_service.py tests/unit/test_churn_notification_service.py
git commit -m "feat(churn): add ChurnNotificationService placeholder stub (#816)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(churn): add ChurnNotificationService placeholder stub" --body "Closes #816"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
