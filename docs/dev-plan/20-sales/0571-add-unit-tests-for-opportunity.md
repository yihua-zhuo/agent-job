# 20-sales · Add unit tests for Opportunity service

| 元数据 | 值 |
|---|---|
| Issue | #571 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [#570](https://github.com/owner/repo/issues/570) |
| 启用后赋能 | [#552](https://github.com/owner/repo/issues/552) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The Opportunity service (`src/services/opportunity_service.py`) currently has no unit test coverage. As part of the [#552](https://github.com/owner/repo/issues/552) test-enablement drive, every service must be covered by unit tests that use the per-test mock pattern described in CLAUDE.md. Without these tests, refactoring or adding new methods to the service carries unacceptable regression risk.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层测试改动
- **开发者视角**：任何 PR touching OpportunityService is automatically validated by `pytest tests/unit/test_opportunity.py`. When a new method is added, the test scaffold is already in place to extend.

### 1.3 不做什么（剔除）

- [ ] Integration tests (real PostgreSQL) — handled by a separate [#570](https://github.com/owner/repo/issues/570) board
- [ ] Router-level tests — out of scope; router tests live in `tests/unit/test_opportunity_routes.py` (not yet created)
- [ ] Test fixtures for `SalesService` or any cross-service dependency beyond `OpportunityService`

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_opportunity.py -v` → ≥ 10 passed
- `ruff check src/services/opportunity_service.py tests/unit/test_opportunity.py` → 0 errors
- `ruff check src/services/opportunity_service.py tests/unit/conftest.py` → 0 errors (if conftest is modified)

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/opportunity_service.py` L? — OpportunityService with methods: `list`, `create`, `update`, `delete`, error-raising on not found / validation

TBD - 待验证：`src/db/models/opportunity.py` L? — Opportunity ORM model; primary key `id`, tenant index, stage enum column

TBD - 待验证：`tests/unit/conftest.py` — existing `MockState`, `make_mock_session`, `MockRow`, `MockResult`; may or may not have `make_opportunity_handler`

### 2.2 涉及文件清单

- 要改：
  - [`tests/unit/conftest.py`](../../tests/unit/conftest.py) — add `make_opportunity_handler(state)` if not yet present
- 要建：
  - `tests/unit/test_opportunity.py` — full unit test suite for OpportunityService

### 2.3 缺什么

- [ ] `make_opportunity_handler(state)` in `tests/unit/conftest.py` — currently no handler for the opportunity table, so `make_mock_session` cannot simulate SELECT/INSERT/UPDATE/DELETE
- [ ] `tests/unit/test_opportunity.py` — zero coverage; no test for `list` (with stage filter + pagination), `create`, `update`, `delete`, `not_found`, `validation_error`
- [ ] Guidance on what constitutes "validation error" in OpportunityService (e.g. empty name, invalid stage value)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_opportunity.py` | Unit tests for all OpportunityService public methods with per-test mock pattern |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/conftest.py`](../../tests/unit/conftest.py) | Add `make_opportunity_handler(state)` factory if not already present; may also need `make_count_handler(state)` for paginated list total count |

### 3.3 新增能力

- **Test fixture**：`make_opportunity_handler(state) -> SQLMockHandler` — simulates opportunity table CRUD; must be stateful (IDs auto-increment)
- **Test suite**：`tests/unit/test_opportunity.py` with the following test functions:
  - `test_list_opportunities_returns_empty`
  - `test_list_opportunities_with_stage_filter`
  - `test_list_opportunities_pagination`
  - `test_create_opportunity_success`
  - `test_create_opportunity_validation_error`
  - `test_update_opportunity_success`
  - `test_update_opportunity_not_found`
  - `test_update_opportunity_validation_error`
  - `test_delete_opportunity_success`
  - `test_delete_opportunity_not_found`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Per-test mock session over shared autouse fixture**：CLAUDE.md §Unit Test SQL Mocks explicitly requires each test file to define its own `mock_db_session` fixture using only the handlers it needs. This prevents cross-test pollution and makes each test independently auditable.
- **Stateful `MockState` for opportunity IDs**：Opportunity records need stable, incrementing primary keys so that `update` and `delete` can target the correct row. Use `state.opportunities` dict; next_id increments on each `INSERT`.

### 4.2 版本约束

N/A — no new dependencies introduced.

### 4.3 兼容性约束

- `OpportunityService.__init__(self, session: AsyncSession)` — no default; must be constructed with a real or mock session in each test
- Service raises `AppException` subclasses; tests must use `pytest.raises()` for error cases
- Service returns ORM objects; tests assert against model attributes, not `.to_dict()` output
- Every SQL mock handler must receive and forward `tenant_id` in all queries (multi-tenancy enforcement)
- Mock session must implement `async_session.execute()` returning `MockResult` wrapping `MockRow` objects

### 4.4 已知坑

1. **Handler missing → `AttributeError: 'NoneType' has no attribute 'execute'`** → Before writing tests, verify `make_opportunity_handler` exists in conftest.py; if not, add it first. All other tests in the file will fail with a cryptic message if the handler is missing.
2. **MockResult.scalar_one_or_none() called on a result set that returned multiple rows** → For `list`, the mock must return a list of `MockRow` objects, not a single row. Wrap in `MagicMock()` with `scalars.return_value = MagicMock(all=MagicMock()))`.
3. **Pagination: total count query** → `list_opportunities` likely does two queries: one for items and one for `COUNT(*)`. The mock session must handle both. If using a separate `count_handler`, ensure the test sets it up — otherwise the count query returns nothing and the service may raise.

---

## 5. 实现步骤（按顺序）

### Step 1: Verify or create `make_opportunity_handler` in `tests/unit/conftest.py`

Read `tests/unit/conftest.py` to confirm `make_opportunity_handler` already exists. If not present, add it following the same pattern as `make_customer_handler(state)`:

```python
def make_opportunity_handler(state: MockState) -> dict:
    """Returns a SQL mock handler dict for the opportunity table."""
    def handle(method, statement, params=None):
        table = state.opportunities
        if method == "SELECT":
            tenant_id = params.get("tenant_id") if params else None
            filtered = [r for r in table.values() if r.get("tenant_id") == tenant_id]
            stage = params.get("stage") if params else None
            if stage is not None:
                filtered = [r for r in filtered if r.get("stage") == stage]
            offset = params.get("offset", 0) if params else 0
            limit = params.get("limit", 20) if params else 20
            return MagicMock(all=MagicMock(return_value=filtered[offset:offset+limit]))
        elif method == "INSERT":
            id_ = state.next_id("opportunity")
            row = {"id": id_, "tenant_id": params.get("tenant_id"), "name": params.get("name"), "stage": params.get("stage")}
            table[id_] = row
            return MagicMock(lastrowid=id_)
        elif method == "UPDATE":
            id_ = params.get("id")
            if id_ in table:
                table[id_].update({k: v for k, v in params.items() if k != "id"})
            return MagicMock(rowcount=1)
        elif method == "DELETE":
            id_ = params.get("id")
            removed = table.pop(id_, None)
            return MagicMock(rowcount=1 if removed else 0)
    return {"opportunity": handle}
```

If `count_handler` is needed for pagination total, ensure it is also present or note the need in the test file.

**完成判定**：`ruff check tests/unit/conftest.py` → 0 errors

---

### Step 2: Create `tests/unit/test_opportunity.py` scaffold

Create the file with:
- Import block: `pytest`, `AsyncSession`, `MagicMock`, `MockState`, `make_mock_session`, `make_opportunity_handler`, `make_count_handler` (if needed), `OpportunityService`, exception classes
- Module-level docstring: "Unit tests for OpportunityService. Per-test mock pattern — no global autouse."
- `@pytest.fixture` `mock_db_session` that creates a `MockState()`, adds `make_opportunity_handler(state)`, and calls `make_mock_session([...])`
- `@pytest.fixture` `opportunity_service(mock_db_session)` that returns `OpportunityService(mock_db_session)`

**完成判定**：`ruff check tests/unit/test_opportunity.py` → 0 errors (before adding test bodies)

---

### Step 3: Add `test_list_opportunities_returns_empty`

```python
async def test_list_opportunities_returns_empty(self, opportunity_service, mock_db_session):
    items, total = await opportunity_service.list_opportunities(tenant_id=1, page=1, page_size=20)
    assert items == []
    assert total == 0
```

Use `MagicMock` to ensure the mock `execute` returns a result with `.scalars().all()` returning `[]`.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity.py::TestOpportunityService::test_list_opportunities_returns_empty -v` → 1 passed

---

### Step 4: Add `test_list_opportunities_with_stage_filter`

Pre-populate `state.opportunities` with 2 rows (stage="prospecting" and stage="closed_won"). Call `list_opportunities(tenant_id=1, stage="prospecting", page=1, page_size=20)`. Assert only the matching row is returned.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity.py::TestOpportunityService::test_list_opportunities_with_stage_filter -v` → 1 passed

---

### Step 5: Add `test_list_opportunities_pagination`

Add 5 opportunity rows. Call `list_opportunities(tenant_id=1, page=1, page_size=2)`. Assert `len(items) == 2` and `total == 5`. Call with `page=3` and assert empty list (beyond pages).

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity.py::TestOpportunityService::test_list_opportunities_pagination -v` → 1 passed

---

### Step 6: Add `test_create_opportunity_success`

Call `opportunity_service.create_opportunity(tenant_id=1, name="Acme Deal", stage="prospecting")`. Assert the returned object has `name="Acme Deal"` and a positive `id`.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity.py::TestOpportunityService::test_create_opportunity_success -v` → 1 passed

---

### Step 7: Add `test_create_opportunity_validation_error`

Arrange: mock `execute` to raise `IntegrityError` on INSERT (e.g. unique constraint). Assert `pytest.raises(ValidationException)` wraps the call.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity.py::TestOpportunityService::test_create_opportunity_validation_error -v` → 1 passed

---

### Step 8: Add update + delete + not found tests

Add the following test methods:
- `test_update_opportunity_success` — pre-populate a row, call `update_opportunity(id=id, tenant_id=1, name="Renamed Deal")`, assert new name
- `test_update_opportunity_not_found` — call `update_opportunity(id=9999, ...)`; assert `pytest.raises(NotFoundException)`
- `test_update_opportunity_validation_error` — mock raises `IntegrityError`; assert `pytest.raises(ValidationException)`
- `test_delete_opportunity_success` — pre-populate row, call `delete_opportunity(id, tenant_id=1)`, assert no exception
- `test_delete_opportunity_not_found` — call `delete_opportunity(9999, tenant_id=1)`; assert `pytest.raises(NotFoundException)`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity.py -v` → ≥ 10 passed

---

## 6. 验收

- [ ] `ruff check tests/unit/conftest.py tests/unit/test_opportunity.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity.py -v` → ≥ 10 passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → no regression in other test files (existing tests still pass)
- [ ] `ruff check src/services/opportunity_service.py` → 0 errors (service itself is clean)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `make_opportunity_handler` is missing from conftest.py and tests fail silently (empty pass) | 低 | 中 | Add the handler in conftest.py before running; all tests re-run |
| MockResult setup mismatch (e.g. wrong attribute chain for scalars) causes `AttributeError` in all tests | 低 | 高 | Debug the mock chain: `execute().scalars().all()` must return list; add a helper in conftest.py to construct valid mock results |
| Handler added to conftest.py conflicts with existing test files that also use `make_mock_session` | 中 | 低 | Each test file defines its own fixture with only its needed handlers; no global state is shared |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/conftest.py tests/unit/test_opportunity.py
git commit -m "test(opportunity): add unit tests for OpportunityService"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#571): add unit tests for OpportunityService" --body "Closes #571"

# 2. post-PR verification (run in CI before merge)
PYTHONPATH=src pytest tests/unit/test_opportunity.py -v
ruff check tests/unit/conftest.py tests/unit/test_opportunity.py
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../tests/unit/test_customer_service.py) — `make_customer_handler` pattern + all CRUD test methods
- 父 issue / 关联：#552 (parent), #570 (dependency — integration tests for Opportunity)
- CLAUDE.md §Unit Test SQL Mocks — `MockState`, `make_mock_session`, `make_<entity>_handler` pattern

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
