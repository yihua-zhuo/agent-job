# 0506-implement-copilotservice · Implement CopilotService with context building and tool registry

| 元数据 | 值 |
|---|---|
| Issue | #506 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD — 待补充：哪些下游板块依赖 CopilotService |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM needs an AI copilot layer that can access real-time customer and sales context to assist users. Currently there is no service that aggregates customer/opportunity/activity data into a format consumable by an AI agent. Issue #505 provides the context-building primitives; this issue wires them into a `CopilotService` that serves as the runtime interface for the copilot.

### 1.2 做完后

- **用户视角**：无用户-visible changes — this is a pure backend service layer.
- **开发者视角**：`CopilotService` is importable from `services.copilot_service`. It exposes `build_system_prompt(tenant_id, customer_id)`, `persist_message(...)`, and `get_tool_registry()` — ready to be wired into an API router or background agent loop.

### 1.3 不做什么（剔除）

- [ ] No API router for copilot endpoints — that belongs in a later issue.
- [ ] No email/task tool implementations — email and task tools are explicitly deferred.
- [ ] No database table for conversation messages — `persist_message` is stubbed/interface-only until the message schema is defined.
- [ ] No LLM integration or actual prompt rendering.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v` → all passed
- `ruff check src/services/copilot_service.py` → 0 errors
- `CopilotService` constructor accepts `session: AsyncSession` with no default; all methods accept `tenant_id: int`
- `NotFoundException` raised when `customer_id` or `opportunity_id` does not resolve for the given `tenant_id`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - `src/services/copilot_service.py` — 新建 `CopilotService` class
  - `tests/unit/test_copilot_service.py` — 新建 unit test
- 要建：
  - `src/services/copilot_service.py` — service class following the service pattern
  - `tests/unit/test_copilot_service.py` — mock-based unit tests
  - No migration needed — no new tables required at this stage

### 2.3 缺什么

- [ ] `CopilotService` class with constructor `__init__(self, session: AsyncSession)` — no default
- [ ] `build_system_prompt(self, tenant_id: int, customer_id: int) -> str` method that aggregates context
- [ ] `persist_message(self, tenant_id: int, role: str, content: str) -> None` stub method
- [ ] `get_tool_registry(self) -> dict[str, callable]` method returning tool descriptors
- [ ] `NotFoundException` raised when context entity is missing for the tenant
- [ ] Unit tests with `mock_db_session` fixture using `tests/unit/conftest.py` helpers

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/copilot_service.py` | `CopilotService` with prompt building, message persistence stub, and tool registry |
| `tests/unit/test_copilot_service.py` | Unit tests covering service methods with mocked DB session |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/copilot_service.py` | 新建文件；遵循 service pattern |
| `tests/unit/test_copilot_service.py` | 新建文件；mock-based tests |

### 3.3 新增能力

- **Service class**：`CopilotService(session: AsyncSession)` — constructor takes session, no default
- **Service method**：`build_system_prompt(tenant_id: int, customer_id: int) -> str` — aggregates customer/opportunity/activity context; raises `NotFoundException` on missing entity
- **Service method**：`persist_message(tenant_id: int, role: str, content: str) -> None` — stub/interface for future message persistence
- **Service method**：`get_tool_registry() -> dict[str, callable]` — returns tool descriptors for `get_customer`, `get_opportunities`, `get_recent_activities`, `get_churn_risk`; email/task tools return deferred marker
- **Tool registry entries**: `get_customer`, `get_opportunities`, `get_recent_activities`, `get_churn_risk` (active); `send_email`, `create_task` (deferred stub)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Stub persistence over real DB write now**：The conversation message table schema is not yet defined (#505 does not yet cover it). We implement `persist_message` as a no-op stub so the service structure is complete and testable without a schema dependency. When the message table lands, the stub is replaced.
- **Tool registry as plain dict**：Rather than a dedicated class, the registry is returned as `dict[str, callable]` — simple, testable, and compatible with the downstream agent loop without introducing a new abstraction layer.

### 4.2 版本约束

TBD — 无新增外部依赖。

### 4.3 兼容性约束

- `CopilotService.__init__(self, session: AsyncSession)` — no default value, matching the service pattern in CLAUDE.md
- All public methods accept `tenant_id: int` as first parameter and include it in every SQL WHERE clause
- Service returns ORM/dataclass objects or primitives; does **not** call `.to_dict()`
- Service raises `AppException` subclasses; does **not** return `ApiResponse.error()`
- No column named `metadata` on any ORM model in scope (would conflict with `Base.metadata`)

### 4.4 已知坑

1. **SQLAlchemy `Base.metadata` column name collision** — If any future model in this service's scope uses a column named `metadata`, it will shadow `Base.metadata` and crash at class definition → Use `event_metadata`, `payload`, `attrs`, or `meta` instead.
2. **Alembic autogen drops `timezone=True` on `DateTime` columns** — Not currently applicable (no migrations in this issue), but if a future migration is added, verify `DateTime(timezone=True)` is emitted explicitly; autogen will emit plain `DateTime` and it must be corrected manually.
3. **Async session via `Depends(get_db)`** — Do not use `async with get_db() as session:` in routers that call `CopilotService`. Always inject via `session: AsyncSession = Depends(get_db)`.
4. **PYTHONPATH=src for all imports** — Write `from services.copilot_service import CopilotService`, not `from src.services.copilot_service import CopilotService`.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/services/copilot_service.py` skeleton

Create the file with the class skeleton matching the service pattern: constructor takes `session: AsyncSession` with no default, raise on missing context, stub all four methods.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from pkg.errors.app_exceptions import NotFoundException

class CopilotService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_system_prompt(self, tenant_id: int, customer_id: int) -> str:
        raise NotImplementedError

    async def persist_message(self, tenant_id: int, role: str, content: str) -> None:
        raise NotImplementedError

    def get_tool_registry(self) -> dict[str, callable]:
        raise NotImplementedError
```

**完成判定**：File `src/services/copilot_service.py` exists; `ruff check src/services/copilot_service.py` → 0 errors; `PYTHONPATH=src python -c "from services.copilot_service import CopilotService; print('import ok')"` → exit 0

### Step 2: Implement `build_system_prompt`

Query customer (by `tenant_id` + `customer_id`), related opportunities, and recent activities. Concatenate into a plain-text system prompt string. Raise `NotFoundException` when customer not found. Use existing service methods for opportunity and activity lookups (or raw queries if they don't exist yet — stub those sub-queries with `pass` if not yet available, documented in a `# TODO` comment).

```python
async def build_system_prompt(self, tenant_id: int, customer_id: int) -> str:
    customer = await self._get_customer(tenant_id, customer_id)
    opportunities = await self._get_opportunities(tenant_id, customer_id)
    activities = await self._get_recent_activities(tenant_id, customer_id)
    # Assemble prompt...
    return prompt
```

**完成判定**：`ruff check src/services/copilot_service.py` → 0 errors; unit test (Step 4) covers the method

### Step 3: Implement `get_tool_registry`

Return a `dict` with four active tool entries (`get_customer`, `get_opportunities`, `get_recent_activities`, `get_churn_risk`) and two deferred stubs (`send_email`, `create_task`). Each entry is `{"description": str, "handler": callable, "deferred": bool}`.

```python
def get_tool_registry(self) -> dict[str, dict]:
    return {
        "get_customer": {
            "description": "Retrieve customer record by ID",
            "handler": lambda tenant_id, customer_id: ...,
            "deferred": False,
        },
        # ... etc
        "send_email": {"description": "TBD — deferred", "handler": None, "deferred": True},
        "create_task": {"description": "TBD — deferred", "handler": None, "deferred": True},
    }
```

**完成判定**：`ruff check src/services/copilot_service.py` → 0 errors

### Step 4: Implement `persist_message` stub

Since the message table is not yet defined, implement as a no-op method. Include a docstring noting that the DB write will be added when the message schema lands.

```python
async def persist_message(self, tenant_id: int, role: str, content: str) -> None:
    """Persist conversation message. DB write deferred until message schema is defined."""
    pass
```

**完成判定**：`ruff check src/services/copilot_service.py` → 0 errors

### Step 5: Write `tests/unit/test_copilot_service.py`

Define a `mock_db_session` fixture using `tests/unit/conftest.py` helpers. Test: (a) `CopilotService` instantiates with `session: AsyncSession`; (b) `build_system_prompt` raises `NotFoundException` for unknown `customer_id`; (c) `get_tool_registry` returns a dict with exactly 6 keys, 4 non-deferred and 2 deferred.

```python
from tests.unit.conftest import make_mock_session, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([])

@pytest.fixture
def copilot_service(mock_db_session):
    return CopilotService(mock_db_session)

async def test_build_system_prompt_raises_not_found(copilot_service):
    with pytest.raises(NotFoundException):
        await copilot_service.build_system_prompt(tenant_id=1, customer_id=9999)

def test_tool_registry_returns_six_tools(copilot_service):
    registry = copilot_service.get_tool_registry()
    assert len(registry) == 6
    active = [k for k, v in registry.items() if not v["deferred"]]
    deferred = [k for k, v in registry.items() if v["deferred"]]
    assert set(active) == {"get_customer", "get_opportunities", "get_recent_activities", "get_churn_risk"}
    assert set(deferred) == {"send_email", "create_task"}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v` → all passed

---

## 6. 验收

- [ ] `ruff check src/services/copilot_service.py tests/unit/test_copilot_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v` → all passed
- [ ] `CopilotService.__init__` has signature `(self, session: AsyncSession)` with no default parameter
- [ ] `build_system_prompt` raises `NotFoundException` when customer not found for given `tenant_id`
- [ ] `get_tool_registry()` returns exactly 6 entries: 4 active + 2 deferred
- [ ] `persist_message` is a no-op stub (exit 0 on call, no side effects)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Issue #505 (context building primitives) is delayed, making `build_system_prompt` a pure stub | 中 | 中 | Keep the stub structure; once #505 lands, backfill the method. This does not block `get_tool_registry`. |
| Unit test `mock_db_session` fixture needs new SQL handler not yet in `conftest.py` | 低 | 低 | Add handler to `tests/unit/conftest.py` following existing patterns; update fixture in the same PR. |
| Column named `metadata` introduced in a future message model | 低 | 高 | Rename to `event_metadata` at migration authoring time; no runtime code change needed in this service. |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/copilot_service.py tests/unit/test_copilot_service.py
git commit -m "feat(copilot): implement CopilotService with context building and tool registry"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(copilot): implement CopilotService" --body "Closes #506"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 父 issue：#76
- 前置依赖：#505
- 同类参考实现：`src/services/customer_service.py` — service pattern (constructor + tenant_id, raises NotFoundException)
- 第三方文档：TBD — 无第三方 docs needed for this issue

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
