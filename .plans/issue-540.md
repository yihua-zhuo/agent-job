Now I have everything needed to write the plan. Let me synthesize the file structure, method signatures, and test patterns.

# Implementation Plan — Issue #540

## Goal
Wire the five existing aggregated-report methods on `AnalyticsService` to FastAPI GET endpoints under `/api/v1/analytics/`, returning structured JSON per metric. No new models, migrations, or changes to the service itself.

## Affected Files
- `src/api/routers/analytics.py` — **new** — six GET endpoints (one per metric) + one GET endpoint for `get_chart_data`
- `tests/unit/test_analytics_router.py` — **new** — unit tests for all six endpoints
- `tests/integration/test_analytics_integration.py` — **add** — router-level integration test cases for the six endpoints

## Implementation Steps

1. **Create `src/api/routers/analytics.py`**
   - Import `APIRouter`, `Depends`, `Query` from FastAPI; `AsyncSession` from SQLAlchemy; `AnalyticsService`; `AuthContext` / `require_auth`; `get_db`
   - Create `analytics_router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])`
   - Add six GET endpoints matching the method names below, each calling the corresponding service method and returning `{"success": True, "data": <result>, "message": "查询成功"}`:
     - `GET /revenue?start_date=&end_date=&group_by=day` → `svc.get_sales_revenue_report(...)` (pattern `"^(day|week|month)$"`)
     - `GET /sales-conversion?start_date=&end_date=` → `svc.get_sales_conversion_report(...)`
     - `GET /customer-growth?start_date=&end_date=` → `svc.get_customer_growth_report(...)`
     - `GET /pipeline-forecast?pipeline_id=` → `svc.get_pipeline_forecast(...)` (pipeline_id optional, defaults to `None`)
     - `GET /team-performance?start_date=&end_date=` → `svc.get_team_performance(...)`
     - `GET /chart-data?chart_type=&data=&labels=` → `svc.get_chart_data(...)` (sync utility, `Query` for data/labels as comma-separated strings or JSON arrays)
   - All endpoints inject `ctx: AuthContext = Depends(require_auth)` and `session: AsyncSession = Depends(get_db)`, pass `tenant_id=ctx.tenant_id or 0` to every service call, and use `Query(...)` (required) for start_date / end_date; optional params use `Query(None)`

2. **No changes to `src/main.py`** — `api/__init__.py` uses `pkgutil.iter_modules` to auto-discover all `APIRouter` instances in `api/routers/`. Dropping `analytics.py` there is sufficient for registration.

3. **Create `tests/unit/test_analytics_router.py`**
   - Follow the exact pattern from `tests/unit/test_sales_router.py`: monkeypatch `api.routers.analytics.AnalyticsService` to return a `MagicMock`, override `require_auth` with `_make_auth_ctx()`, override `get_db` with `MagicMock()`, register the `AppException` exception handler, use `TestClient`
   - Define module-level fixtures `REVENUE_DATA`, `CONVERSION_DATA`, `GROWTH_DATA`, `FORECAST_DATA`, `TEAM_DATA`, `CHART_DATA` as exact dict shapes returned by the service methods
   - Add one test class per endpoint (`TestGetSalesRevenue`, `TestGetSalesConversion`, `TestGetCustomerGrowth`, `TestGetPipelineForecast`, `TestGetTeamPerformance`, `TestGetChartData`) with at minimum: `test_success` (asserts 200 + `body["success"] is True` + correct `chart_type` in data), `test_missing_dates_rejected` (asserts 422 for required query params), and for `/revenue` also `test_with_group_by` and `test_invalid_group_by_rejected` (asserts 422)

4. **Add integration tests to `tests/integration/test_analytics_integration.py`**
   - Add a `@pytest.mark.integration` class `TestAnalyticsRouterIntegration` with async test methods seeded via `_seed_customer` (from conftest) and `_seed_opportunity` helpers
   - For each of the five DB-backed endpoints, test: happy path (`async_session`-scoped real service call returns a dict with expected keys `labels`, `datasets`, `chart_type`) and 404-equivalent error path (e.g., requesting with a non-existent tenant_id returns empty/zero data, not an exception — these methods return dicts on all inputs)
   - Use the existing `db_schema`, `tenant_id`, `async_session` fixtures from `tests/integration/conftest.py`

## Test Plan
- Unit tests in `tests/unit/`: `test_analytics_router.py` — six endpoint test classes exercising all status codes, required-param validation, and response shape via mocked service
- Integration tests in `tests/integration/`: `test_analytics_integration.py` — add `TestAnalyticsRouterIntegration` class exercising the five DB-backed endpoints against a real PostgreSQL fixture with seeded customers and opportunities

## Acceptance Criteria
- `GET /api/v1/analytics/revenue?start_date=2025-01-01&end_date=2025-01-31&group_by=day` returns `200` with `{"success": true, "data": {"labels": [...], "datasets": [...], "chart_type": "line"}}`
- `GET /api/v1/analytics/sales-conversion?start_date=…&end_date=…` returns `200` with `chart_type: "funnel"`
- `GET /api/v1/analytics/customer-growth?start_date=…&end_date=…` returns `200` with `chart_type: "bar"`
- `GET /api/v1/analytics/pipeline-forecast` (no params required) returns `200` with `chart_type: "bar"`
- `GET /api/v1/analytics/team-performance?start_date=…&end_date=…` returns `200` with two datasets
- `GET /api/v1/analytics/chart-data?chart_type=line&data=1,2,3&labels=a,b,c` returns `200` with the formatted dict
- All six endpoints return `401` without a valid Bearer token
- All endpoints with required `Query(...)` params return `422` when those params are absent
- All endpoints are tenant-isolated: passing `tenant_id` from the auth context into the service call
