# Implementation Plan — Issue #670

## Goal

Create a `ChurnPrediction` SQLAlchemy ORM model to store per-customer churn predictions (score, tier, contributing factors, and prediction timestamp), and add an Alembic migration so the table exists in the database. The model follows the established multi-tenant pattern with `tenant_id` filtering on every query.

## Affected Files

- `src/db/models/churn_prediction.py` — new file; `ChurnPredictionModel` ORM class with `customer_id`, `tenant_id`, `score`, `tier`, `factors` JSON, `predicted_at`, plus `to_dict()`
- `alembic/versions/<new_rev>.py` — new migration creating `churn_predictions` table, with `upgrade()` and `downgrade()` functions
- `alembic/env.py` — no changes needed; `import db.models` auto-discovers all models in `src/db/models/`

## Implementation Steps

1. **Create `src/db/models/churn_prediction.py`** following the `CustomerModel` / `TicketModel` pattern:
   - Inherit `Base` from `db.base`
   - `__tablename__ = "churn_predictions"`
   - Columns: `id` (PK, autoincrement), `tenant_id` (indexed), `customer_id` (indexed), `score` (Float), `tier` (String, nullable), `factors` (JSON, default=list), `predicted_at` (DateTime, server_default=func.now()), `created_at` / `updated_at` (DateTime with server_default/onupdate)
   - Composite index on `(tenant_id, customer_id)`
   - `to_dict()` returning all fields as dict (dates as ISO strings)

2. **Generate the Alembic migration** using the procedure in `CLAUDE.md`:
   - Spin up the dev DB via `docker compose -f configs/docker-compose.test.yml up -d test-db`
   - Create `alembic_dev` database
   - Run `alembic upgrade head`
   - Run `alembic revision --autogenerate -m "add_churn_predictions"`
   - Review the generated `alembic/versions/<id>_add_churn_predictions.py`, adjusting `score` column type to `Float` (Alembic may emit `Numeric`; correct if needed) and ensuring composite index is present
   - Verify: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` passes cleanly
   - Run a second `alembic revision --autogenerate -m "drift_check"` to confirm an empty diff; delete it if both up/down are `pass`

3. **Verify the model is queryable** by running unit tests (no DB needed) and ensuring the file imports without error (`PYTHONPATH=src python -c "from db.models.churn_prediction import ChurnPredictionModel; print(ChurnPredictionModel.__tablename__)"`).

## Test Plan

- Unit tests in `tests/unit/`: create `tests/unit/test_churn_prediction_model.py` — uses `MockState` + `make_mock_session` with a new `make_churn_prediction_handler(state)` in `tests/unit/domain_handlers/` following the pattern of existing domain handlers (e.g., `tests/unit/domain_handlers/customers.py`). Test: model instantiation, `to_dict()` output shape, and that `tenant_id` is included in the state. No real DB required.
- Integration tests in `tests/integration/`: create `tests/unit/test_churn_prediction_integration.py` (marked `@pytest.mark.integration`) — uses `db_schema`, `tenant_id`, `async_session` fixtures. Test: `ChurnPredictionModel` can be inserted and queried back within a transaction.

## Acceptance Criteria

- `ruff check src/db/models/churn_prediction.py` passes with no errors
- `mypy src/db/models/churn_prediction.py` passes
- `alembic upgrade head` succeeds on a clean `alembic_dev` database with no errors
- `alembic downgrade -1` succeeds and drops the table
- `alembic upgrade head` succeeds again (re-run is clean)
- Second autogenerate (`alembic revision --autogenerate -m "drift_check"`) produces an empty diff (only `pass` in both upgrade/downgrade)
- Unit test `pytest tests/unit/test_churn_prediction_model.py -v` passes
- Integration test `pytest tests/integration/test_churn_prediction_integration.py -v` passes
