# [Analytics] · Add unit tests for AnalyticsService reports + dashboards

| 元数据 | 值 |
|---|---|
| Issue | #144 |
| 分类 | 20-test |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`AnalyticsService` currently has no unit test coverage. The service exposes report and dashboard operations that are central to the CRM's analytics layer. Without tests, any regression in those methods goes undetected until integration or production — making the module risky to evolve. Adding unit tests is a prerequisite for any future work on analytics (dashboards, exports, permissions).

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层测试覆盖提升。
- **开发者视角**：有了 `tests/unit/test_analytics_service.py`，覆盖 `get_sales_revenue_report`、`get_sales_conversion_report`、`get_customer_growth_report`、`get_pipeline_forecast`、`get_team_performance`、`create_dashboard`、`get_dashboard`、`list_dashboards` 等方法。CI gate prevents regressions in these methods.

### 1.3 不做什么（剔除）

- [ ] 不实现任何新的 service 方法 or API endpoint — only test coverage
- [ ] 不编写 integration tests for analytics (belong in `tests/integration/`)
- [ ] 不 mock at the HTTP/router layer — focus on service unit tests only

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_analytics_service.py --collect-only` → `>= 8 items, 0 errors`]
- [指标 2：`PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v` → `8 passed`]
- [指标 3：`ruff check tests/unit/test_analytics_service.py` → `0 errors`]
- [指标 4：`grep -E "def test_get_sales_|def test_get_customer_|def test_get_pipeline_|def test_get_team_|def test_create_dashboard_|def test_list_dashboards" tests/unit/test_analytics_service.py` → all 8 names present]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/analytics_service.py` — AnalyticsService class with `get_sales_revenue_report`, `get_sales_conversion_report`, `get_customer_growth_report`, `get_pipeline_forecast`, `get_team_performance`, `create_dashboard`, `get_dashboard`, `list_dashboards` methods. Constructor takes `session: AsyncSession` with no default.

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/test_analytics_service.py` — 新建，覆盖 AnalyticsService 所有公开方法
- 要建：
  - `tests/unit/test_analytics_service.py` — unit test module (8 test cases as per issue)

### 2.3 缺什么

- [ ] `tests/unit/test_analytics_service.py` — 文件不存在，AnalyticsService is not covered by any unit test
- [ ] `analytics_service` fixture in the test file — returns `AnalyticsService(mock_db_session)`
- [ ] Mock DB session handler for analytics SQL queries — must handle count + fetch patterns
- [ ] `test_get_sales_revenue_report_returns_dict` — validates dict return from revenue report
- [ ] `test_get_sales_conversion_report_returns_dict` — validates dict return from conversion report
- [ ] `test_get_customer_growth_report_returns_dict` — validates dict return from growth report
- [ ] `test_get_pipeline_forecast_returns_dict` — validates dict return from forecast
- [ ] `test_get_team_performance_returns_dict` — validates dict return from team performance
- [ ] `test_create_dashboard_success` — validates dashboard creation path
- [ ] `test_get_dashboard_found` + `test_get_dashboard_not_found` — found/not-found branches
- [ ] `test_list_dashboards_pagination` — validates pagination logic on list

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_analytics_service.py` | Unit tests for AnalyticsService reports and dashboard operations (8 test cases) |

### 3.2 修改文件

（无修改 — 新建单元测试文件即可）

### 3.3 新增能力

- **Test cases**：8 `async def test_*` functions covering all AnalyticsService report + dashboard methods
- **Fixture**：`analytics_service(session)` returning a `AnalyticsService` instance
- **Mock strategy**：uses `make_mock_session` from `tests/unit/conftest.py` with `MockState` + per-query handlers following the established domain-handler pattern

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `pytest-asyncio` async test functions over sync mocks**：AnalyticsService methods are async; tests must use `pytest.mark.asyncio` and `async def test_*` to match the service's interface. This is consistent with all existing unit tests in `tests/unit/`.
- **选 per-method mock handlers over a generic catch-all**：Each handler (`make_*_handler(state)`) provides deterministic mock responses keyed by method name and parameters. This matches the established pattern in `tests/unit/conftest.py` and avoids brittle global patching.
- **选 `MockRow` / `MockResult` from conftest.py over plain dict mocking**：SQLAlchemy async returns `Row` / `Result` objects; using `MockRow` simulates the exact shape the service sees, catching e.g. attribute-access mismatches before they reach integration.

### 4.2 版本约束

（无新依赖引入）

### 4.3 兼容性约束

- Multi-tenant：mock handlers must pass `tenant_id` through to WHERE clauses (even if the mock returns a fixed value) so the test mirrors real service behaviour
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；测试断言直接比较返回的对象或其属性（不调用 `.to_dict()`）
- Service 错误抛 `AppException` 子类；`test_get_dashboard_not_found` uses `pytest.raises(NotFoundException)` to assert the correct exception is raised
- Import 路径：`from services.analytics_service import AnalyticsService` — NOT `from src.services.analytics_service`

### 4.4 已知坑

1. **SQLAlchemy `Row` attribute access** → 规避：使用 `MockRow` from `tests/unit/conftest.py` which returns attributes via `__getattr__` mapping; avoids `KeyError` on column access
2. **Async test collector count** → 规避：`pytest --collect-only` can undercount if `pytest-asyncio` is not properly configured; ensure `pytest.ini` / `pyproject.toml` has `asyncio_mode = auto` (matching existing unit test config)
3. **Mock handler returning `None` for scalar_one_or_none** → 规避：handlers must return `None` explicitly for not-found cases; do not omit the return in the handler dict

---

## 5. 实现步骤（按顺序）

### Step 1: Create `tests/unit/test_analytics_service.py` scaffold with fixtures

Add `pytest.mark.asyncio` import, `AnalyticsService` import, and `make_mock_session` / `MockState` imports from `tests.unit.conftest`. Add the `mock_db_session` fixture and the `analytics_service` fixture. Place 8 `async def test_*` stubs so `pytest --collect-only` resolves to `>= 8 items`.

```python
import pytest
from tests.unit.conftest import make_mock_session, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([])

@pytest.fixture
def analytics_service(mock_db_session):
    from services.analytics_service import AnalyticsService
    return AnalyticsService(mock_db_session)

@pytest.mark.asyncio
async def test_get_sales_revenue_report_returns_dict(analytics_service):
    raise NotImplementedError("stub")

# ... 7 more stubs
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_service.py --collect-only` → `>= 8 items, 0 errors`

---

### Step 2: Add mock DB session handlers for report methods

Define handlers for `get_sales_revenue_report`, `get_sales_conversion_report`, `get_customer_growth_report`, `get_pipeline_forecast`, `get_team_performance` that return appropriate mock `Row` objects (or plain dicts if the service returns dicts). Update `make_mock_session([])` with these handlers. Fill in the four report test bodies with assertions matching the expected return shape.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v -k "report"` → `4 passed`

---

### Step 3: Add mock DB session handlers for dashboard methods

Define handlers for `create_dashboard`, `get_dashboard`, `list_dashboards`. For `get_dashboard` include both found (returns a row) and not-found (returns `None`) cases. Use `MockState` counters for dashboard IDs. Fill in `test_create_dashboard_success`, `test_get_dashboard_found`, `test_get_dashboard_not_found`, `test_list_dashboards_pagination`.

- `test_get_dashboard_not_found` uses `from pkg.errors.app_exceptions import NotFoundException` and `pytest.raises(NotFoundException)`
- `test_list_dashboards_pagination` asserts `len(items) <= page_size` and `total >= 0`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v -k "dashboard"` → `4 passed`

---

### Step 4: Run full test suite and linter

Run the complete test file and confirm all 8 pass. Then run ruff to ensure no linting errors.

```bash
PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v
ruff check tests/unit/test_analytics_service.py
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v` → `8 passed` AND `ruff check tests/unit/test_analytics_service.py` → `0 errors`

---

## 6. 验收

- [ ] `ruff check tests/unit/test_analytics_service.py` → `0 errors`
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_service.py --collect-only` → `>= 8 items, 0 errors`
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v` → `8 passed`
- [ ] `grep -E "def test_get_sales_|def test_get_customer_|def test_get_pipeline_|def test_get_team_|def test_create_dashboard_|def test_list_dashboards" tests/unit/test_analytics_service.py` → 8 function names present
- [ ] `PYTHONPATH=src pytest tests/unit/ -q` → `N passed` (suite still green after adding new file)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| AnalyticsService method signatures change after this test is written | 低 | 中 | Tests fail at collection time; update test signatures to match new method args |
| Mock handlers don't precisely match actual SQLAlchemy row shape → false negatives | 低 | 中 | Add `MockRow` debug logging; compare against real integration test behaviour |
| New dependencies needed (e.g. pytest-asyncio config missing) | 低 | 低 | Add `asyncio_mode = auto` to `pytest.ini`; already done in sibling unit tests |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_analytics_service.py
git commit -m "test(analytics): add unit tests for AnalyticsService reports + dashboards"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(analytics): add unit tests for AnalyticsService reports + dashboards" --body "Closes #144"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — same unit test pattern: `MockState`, `make_mock_session`, `MockRow`, async test functions, `pytest.raises` for not-found cases
- 同类参考实现：[`tests/unit/test_opportunity_service.py`](../../tests/unit/test_opportunity_service.py) — pagination + list test pattern for `test_list_dashboards_pagination`
- 父 issue / 关联：TBD (no parent issue referenced in #144)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
