# Implementation Plan — Issue #226

## Goal
Add a `count_by_status` method to `CustomerService` that returns a dictionary of `CustomerStatus → int` counts per tenant, enabling dashboard widgets to display lead/active/inactive breakdowns. The existing method implementation uses SQL aggregation; the remaining work is a defensive guard and matching unit tests.

## Affected Files
- `src/services/customer_service.py` — add `tenant_id <= 0` early-return guard to `count_by_status`
- `tests/unit/test_customer_service.py` — add two tests: `test_count_by_status_basic` and `test_count_by_status_zero_tenant`; the existing `TestCountByStatus` class already covers tenant isolation and result-shape cases

## Implementation Steps
1. In `src/services/customer_service.py`, add an early-return guard at the start of `count_by_status`: if `tenant_id <= 0`, return `{}` before executing any SQL.
2. In `tests/unit/test_customer_service.py`, add `test_count_by_status_basic` inside the existing `TestCountByStatus` class: create three mock rows for tenant 1 covering `CustomerStatus.LEAD`, `CustomerStatus.ACTIVE`, and `CustomerStatus.INACTIVE`; assert each count matches.
3. Add `test_count_by_status_zero_tenant` asserting `count_by_status(0)` returns `{}` directly without calling `session.execute`.

## Test Plan
- Unit tests in `tests/unit/test_customer_service.py`: extend `TestCountByStatus` with the two new cases above; existing tests (`test_count_by_status_empty`, `test_count_by_status_returns_counts`, `test_count_by_status_tenant_isolation`, `test_count_by_status_single_status`, `test_count_by_status_invalid_db_status_raises_validation`) cover the remaining paths.
- Integration tests in `tests/integration/`: no integration tests required for this method — aggregation is exercised end-to-end via router-level API tests if they exist.

## Acceptance Criteria
- `grep -n 'def count_by_status' src/services/customer_service.py` shows the method body including the `tenant_id <= 0` guard returning `{}`
- `python -m pytest tests/unit/test_customer_service.py -v -k count_by_status` runs all 5 tests in `TestCountByStatus` and all pass
- `python -m pytest tests/unit/test_customer_service.py -q` shows the full suite green
