`ReportModel` has no `updated_at` column — the dev-plan Step 5 code that assigns it will need to be adjusted. That's a real finding to include.

# Implementation Plan — Issue #631

## Goal
Add five CRUD methods (`list_reports`, `get_report`, `create_report`, `update_report`, `delete_report`) to the existing `ReportService` class in `src/services/report_service.py`, enabling the service layer to manage `ReportModel` rows with full multi-tenant isolation. This unblocks the API router built in issue #632 and all downstream analytics consumers.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0631-implement-reportservice-with-crud-and-basic-storage.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0631-implement-reportservice-with-crud-and-basic-storage.md`

## Affected Files
- `src/services/report_service.py` — add five CRUD async methods; update imports (`ReportModel`, `NotFoundException`, `ForbiddenException`, `func`, `update`, `delete`)
- `tests/unit/test_report_service.py` — new file; unit tests for all five CRUD methods + tenant isolation + not-found cases

## Implementation Steps

1. **Update imports in `src/services/report_service.py`**
   - Add `from datetime import UTC, datetime` (remove duplicate `from datetime import UTC, datetime` that already exists at line 9 — consolidate to one import line)
   - Change `from sqlalchemy import and_, select` → `from sqlalchemy import and_, delete, func, select, update`
   - Add `from db.models.analytics import ReportModel`
   - Add `ForbiddenException, NotFoundException` to the existing `pkg.errors.app_exceptions` import

2. **Add `list_reports` method to `ReportService`**
   - Insert after the existing `schedule_report` method (around line 178)
   - Uses `func.count()` for total + `SELECT ... LIMIT/OFFSET ORDER BY created_at DESC`
   - Returns `tuple[list[ReportModel], int]`

3. **Add `get_report` method to `ReportService`**
   - `SELECT ... WHERE id=? AND tenant_id=?` via `and_()`; raises `NotFoundException` if `scalar_one_or_none()` returns `None`

4. **Add `create_report` method to `ReportService`**
   - Constructs `ReportModel` from `data` dict (name, type, config, date_range, created_by); sets `tenant_id`, `last_run_at=None`, `created_at=datetime.now(UTC)`
   - Calls `session.add()` + `session.flush()`; returns the ORM object

5. **Add `update_report` method to `ReportService`**
   - Fetches by `(id, tenant_id)`; raises `NotFoundException` if missing   - Merges `data` dict into existing row via `setattr()` for fields `name`, `type`, `config`, `date_range`, `last_run_at`
   - **Note**: `ReportModel` has no `updated_at` column — the dev-plan Step 5 code that assigns `report.updated_at = datetime.now(UTC)` must be removed; call `session.flush()` + `session.refresh()` without touching `updated_at`

6. **Add `delete_report` method to `ReportService`**
   - Confirms existence via `SELECT id WHERE (id, tenant_id)`; raises `NotFoundException` if missing
   - Executes `delete(ReportModel).where(and_(...))`; calls `session.flush()`

7. **Create `tests/unit/domain_handlers/reports.py`** (new file)
   - Follow the pattern of `tests/unit/domain_handlers/customers.py` with `ORDER = 10`
   - Handler for `SELECT reports WHERE tenant_id=?` (single and paginated), `INSERT INTO reports`, `UPDATE reports`, `DELETE FROM reports`
   - Use `MockRow` / `MockResult` from `conftest.py`

8. **Create `tests/unit/test_report_service.py`** (new file)
   - Follow the pattern of `tests/unit/test_customer_service.py` — inline `mock_db_session` fixture using `MagicMock` + `AsyncMock` (no `make_mock_session` dependency needed)
   - `mock_db_session` wires `session.execute` to return appropriate `MockResult` objects for each test case
   - Test classes: `TestListReports`, `TestGetReport`, `TestCreateReport`, `TestUpdateReport`, `TestDeleteReport`
   - Covers: happy path, not-found (missing id), tenant-isolation (wrong tenant → `NotFoundException`), empty list, pagination offset

9. **Run verification commands**
   - `ruff check src/services/report_service.py` →0 errors
   - `PYTHONPATH=src python -c "from services.report_service import ReportService; import inspect; methods=['list_reports','get_report','create_report','update_report','delete_report']; [assert m in dir(ReportService) for m in methods]; print('all five present')"` → exit 0
   - `PYTHONPATH=src pytest tests/unit/test_report_service.py -v` → all cases passed

## Test Plan
- Unit tests in `tests/unit/`: `tests/unit/test_report_service.py` (new) — covers all five CRUD methods with happy path, not-found, and tenant-isolation cases; `tests/unit/domain_handlers/reports.py` (new) — SQL mock handler for `reports` table- Integration tests in `tests/integration/`: none required per the dev-plan (table already exists via `ReportModel`; no migration needed)
- Dev-plan verification:
  - `ruff check src/services/report_service.py` →0 errors
  - `PYTHONPATH=src pytest tests/unit/test_report_service.py -v` → all passed
  - `PYTHONPATH=src python -c "from services.report_service import ReportService; assert hasattr(ReportService, 'list_reports'); assert hasattr(ReportService, 'get_report'); assert hasattr(ReportService, 'create_report'); assert hasattr(ReportService, 'update_report'); assert hasattr(ReportService, 'delete_report'); print('ok')"` → exit 0

## Acceptance Criteria
- `ruff check src/services/report_service.py` exits0 with no errors
- `ReportService` has all five methods: `list_reports`, `get_report`, `create_report`, `update_report`, `delete_report`
- `get_report`, `update_report`, `delete_report` each raise `NotFoundException` when the report is absent or belongs to another tenant
- `list_reports` returns `tuple[list[ReportModel], int]` with correct total count and respects pagination (`LIMIT/OFFSET`)
- All five methods include `tenant_id` in every SQL `WHERE` clause
- `PYTHONPATH=src pytest tests/unit/test_report_service.py -v` passes all cases
- `ReportModel` fields assigned in `update_report` match only the columns that actually exist on the model (no `updated_at` — remove the dev-plan's erroneous assignment)

## Risks / Open Questions
- **`ReportModel` has no `updated_at` column**: The dev-plan Step 5 code sets `report.updated_at = datetime.now(UTC)` but `ReportModel` only has `created_at`. This assignment must be removed. The `flush()` + `refresh()` calls still correctly persist changes without it.
- **`make_mock_session` uses lowercase SQL text matching**: The `reports` SQL handler in `tests/unit/domain_handlers/reports.py` must match on `"select from reports"`, `"insert into reports"`, `"update reports"`, `"delete from reports"` (lowercase, as per `_execute_side_effect` in `conftest.py`).
