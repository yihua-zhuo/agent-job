# Implementation Plan — Issue #144

## Goal
Create `tests/unit/test_analytics_service.py` covering the dashboard CRUD, report dispatch, and aggregated analytics methods of `AnalyticsService`. No integration tests are needed — the existing integration suite already covers the full DB lifecycle; this file adds fast unit-level coverage for the report and dashboard operations using in-memory SQL mocks.

## Affected Files
- `tests/unit/conftest.py` — add `dashboard_handler` and `report_handler` SQL handlers, plus `make_analytics_handlers()` factory
- `tests/unit/test_analytics_service.py` — new file; all test classes and fixtures

## Implementation Steps

1. **Add SQL handlers to `tests/unit/conftest.py`**
   - `dashboard_handler(sql_text, params)` — stateless; matches `"from dashboards"` for SELECT, `"insert into dashboards"` for INSERT; returns `MockResult([MockRow({...})])` with fields matching `DashboardModel` (`id`, `tenant_id`, `name`, `description`, `widgets`, `owner_id`, `is_default`, `created_at`, `updated_at`). For `"where id"` queries, return a fixture row when `params.get("id")` matches (id=1 → `"Dashboard 1"`), or empty `MockResult([])` for unknown IDs.
   - `report_handler(sql_text, params)` — same pattern for `"from reports"` / `"insert into reports"`; returns `MockResult([MockRow({...})])` with `ReportModel` fields (`id`, `tenant_id`, `name`, `type`, `config`, `date_range`, `created_by`, `last_run_at`, `created_at`).
   - `make_analytics_handlers(state)` factory returning `[dashboard_handler, report_handler, opportunity_handler, make_count_handler(state)]` — composable list for use with `make_mock_session`.

2. **Create `tests/unit/test_analytics_service.py`**

   a. **Imports**: `AnalyticsService` from `services.analytics_service`, `NotFoundException` from `pkg.errors.app_exceptions`, `make_mock_session`, `MockResult`, `MockState` from `tests.unit.conftest`.

   b. **Mock model classes** (matching `DashboardModel` and `ReportModel` interfaces):
   - `MockDashboardModel`: `__init__` sets all fields as attributes, `to_dict()` returns flat dict. Used as the return value of `session.refresh` in `create_dashboard`.
   - `MockReportModel`: same pattern for `ReportModel`.

   c. **`mock_db_session` fixture** — uses `MockState` + `make_mock_session([dashboard_handler, report_handler, opportunity_handler, make_count_handler(state)])`. Patches `session.refresh` to set `dashboard.id = 1` / `report.id = 1` so subsequent lookups find the record.

   d. **`analytics_service(mock_db_session)` fixture** — returns `AnalyticsService(mock_db_session)`.

   e. **`TestGetSalesRevenueReport`** class:
   - `test_get_sales_revenue_report_returns_dict` — call `svc.get_sales_revenue_report("2024-01-01", "2024-01-31", tenant_id=1)`; assert result is a `dict` with keys `"labels"`, `"datasets"`, `"chart_type"`. Mock must handle the `func.date_trunc` aggregation query — the existing `opportunity_handler` covers `"from opportunities"` so it will return a row.

   f. **`TestGetSalesConversionReport`** class:
   - `test_get_sales_conversion_report_returns_dict` — call `svc.get_sales_conversion_report("2024-01-01", "2024-01-31", tenant_id=1)`; assert dict with `"labels"`, `"datasets"`, `"chart_type"`. Mock returns stage count rows via `opportunity_handler`.

   g. **`TestGetCustomerGrowthReport`** class:
   - `test_get_customer_growth_report_returns_dict` — call `svc.get_customer_growth_report("2024-01-01", "2024-01-31", tenant_id=1)`; assert dict. Mock needs `customer_handler` added to conftest.py if not already present — verify `make_customer_handler` exists and covers `"from customers"` queries.

   h. **`TestGetPipelineForecast`** class:
   - `test_get_pipeline_forecast_returns_dict` — call `svc.get_pipeline_forecast(pipeline_id=1, tenant_id=1)`; assert dict with `"pipeline_id"`, `"labels"`, `"datasets"`, `"chart_type"`. Uses `opportunity_handler` for stage aggregation.

   i. **`TestGetTeamPerformance`** class:
   - `test_get_team_performance_returns_dict` — call `svc.get_team_performance("2024-01-01", "2024-01-31", tenant_id=1)`; assert dict with `"labels"` (list of `"Owner N"` strings), `"datasets"`. Uses `opportunity_handler` for owner grouping.

   j. **`TestDashboardCrud`** class:
   - `test_create_dashboard_success` — mock `session.refresh` to set `dashboard.id = 1`; call `svc.create_dashboard(name="Sales", owner_id=1, tenant_id=1)`; assert returned object's `name == "Sales"` and `widgets == []`.
   - `test_get_dashboard_found` — `dashboard_handler` returns a fixture row for id=1; call `svc.get_dashboard(1, tenant_id=1)`; assert name from fixture.
   - `test_get_dashboard_not_found` — add a `_empty_dashboard_handler` that returns `MockResult([])` for all queries; build a session with it + `make_count_handler`; assert `pytest.raises(NotFoundException)`.
   - `test_list_dashboards_pagination` — `dashboard_handler` returns a list of 3 `MockRow` fixture objects; call `svc.list_dashboards(tenant_id=1)`; assert returned list has 3 items.

   k. **`TestReportDispatch`** class (optional but recommended to cover `run_report`):
   - `test_run_report_dispatches_to_sales_revenue` — create a report via `create_report`, then call `run_report` with `date_range`; verify it returns a dict matching `get_sales_revenue_report` shape. Requires `report_handler` to return the created report row on the second `get_report` call.

3. **Run `pytest tests/unit/test_analytics_service.py --collect-only`** — confirm >= 8 items, 0 errors. Fix any import or fixture errors.

4. **Run `pytest tests/unit/test_analytics_service.py -v`** — all tests must pass. Iterate on mock handlers until green.

5. **Run `grep -E 'def test_get_sales_|def test_get_customer_|def test_get_pipeline_|def test_get_team_|def test_create_dashboard_|def test_list_dashboards'` on the new file** — confirm all 8 names are present.

6. **Run `pytest tests/unit/ -q`** — entire unit suite must still be green.

## Test Plan
- Unit tests in `tests/unit/`: `tests/unit/test_analytics_service.py` — new file covering all 8 dashboard/report operations and 5 aggregated report methods via mocked SQLAlchemy session
- Integration tests in `tests/integration/`: no changes (existing `test_analytics_integration.py` covers the full DB lifecycle)

## Acceptance Criteria
- `pytest tests/unit/test_analytics_service.py --collect-only` reports >= 8 items, 0 collection errors
- `pytest tests/unit/test_analytics_service.py -v` — all tests pass
- `grep -E 'def test_get_sales_|def test_get_customer_|def test_get_pipeline_|def test_get_team_|def test_create_dashboard_|def test_list_dashboards' tests/unit/test_analytics_service.py` confirms all 8 test names are present
- `pytest tests/unit/ -q` — unit suite remains green (no regressions)
