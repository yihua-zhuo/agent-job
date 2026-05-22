# Implementation Plan — Issue #572

## Goal

Create a new SQLAlchemy ORM model `ChurnPrediction` in `src/db/models/` and a corresponding Alembic migration that adds the `churn_predictions` table with fields for the churn score, tier classification, model factors, recommended actions, and metadata — then write one integration test that confirms the table is created and a row can be inserted and fetched from it.

## Affected Files

- `src/db/models/churn_prediction.py` — new ORM model with id, customer_id, tenant_id, score, tier enum, factors JSON, recommended_actions JSON, model_version, created_at
- `alembic/versions/<new_revision>_add_churn_predictions.py` — new migration extending head `c94d682d4b03`
- `tests/integration/test_churn_prediction_integration.py` — new integration test file

## Implementation Steps

1. **Create `src/db/models/churn_prediction.py`** following the pattern in `customer.py` and `opportunity.py`:
   - Import `Base` from `db.base`, `Mapped`, `mapped_column` from `sqlalchemy.orm`
   - Define a local `ChurnTier` Python enum (`high`, `medium`, `low`) and a SQLAlchemy `Enum` column mapping to it
   - Columns: `id` (Integer, PK, autoincrement), `tenant_id` (Integer, nullable=False, index), `customer_id` (Integer, nullable=False), `score` (Integer, nullable=False), `tier` (Enum, nullable=False), `factors` (JSON list — `Mapped[list[dict]]`, use `JSON` from `sqlalchemy.dialects.postgresql` with nullable=False), `recommended_actions` (JSON list), `model_version` (String(50)), `created_at` (DateTime with `server_default=func.now()`)
   - Add composite index on `(tenant_id, customer_id)`
   - Implement `to_dict()` mirroring other models

2. **Generate the Alembic migration** using the workflow in CLAUDE.md:
   - Spin up `test-db` via `docker compose -f configs/docker-compose.test.yml up -d`
   - Create a dedicated `alembic_dev` database: `DROP DATABASE IF EXISTS alembic_dev; CREATE DATABASE alembic_dev;`
   - Run `alembic upgrade head` on `alembic_dev`
   - Run `alembic revision --autogenerate -m "add_churn_predictions"` — since `alembic/env.py` already does `import db.models` (line 14), the new model is auto-discovered
   - Review the generated file: fix any mismatches (e.g. `sa.Integer` vs `sa.SmallInteger` for score, ensure JSON columns use `postgresql.JSON(astext_type=sa.Text())`), fill in `downgrade()` if left blank
   - Verify: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` on `alembic_dev`
   - Run a second empty autogen (`alembic revision --autogenerate -m "drift_check"`) and delete it if both up/down are `pass`
   - The new migration file (e.g. `abcdef123456_add_churn_predictions.py`) becomes the head revision

3. **Create `tests/integration/test_churn_prediction_integration.py`**:
   - Import `ChurnPredictionModel` from `db.models.churn_prediction`
   - Add a single `@pytest.mark.integration` test class `TestChurnPredictionIntegration`
   - One test: given `db_schema`, `tenant_id`, `async_session`, and a seeded customer (`_seed_customer`), insert a `ChurnPredictionModel` row, commit, then fetch it back and assert `score`, `tier`, `factors`, `recommended_actions`, and `model_version` are correct
   - Follow the same pattern as `test_ai_integration.py`

## Test Plan

- **Unit tests**: none required — this is a schema-only model with no business logic.
- **Integration tests**: `tests/integration/test_churn_prediction_integration.py` — one test that inserts a row into `churn_predictions` using the real DB (via `async_session` fixture) and verifies all fields including JSON columns round-trip correctly. Runs with `DATABASE_URL` (or `TEST_DATABASE_URL`) against a live PostgreSQL instance; schema is managed by Alembic migrations.

## Acceptance Criteria

- `ChurnPredictionModel` is importable from `db.models.churn_prediction`
- `alembic upgrade head` applies the new migration and creates the `churn_predictions` table with all required columns (id, tenant_id, customer_id, score, tier, factors, recommended_actions, model_version, created_at)
- The tier column is backed by a PostgreSQL enum with values `high`, `medium`, `low`
- The `factors` and `recommended_actions` columns store JSON lists and round-trip correctly
- `alembic downgrade -1` cleanly removes the table
- The integration test in `test_churn_prediction_integration.py` passes with `DATABASE_URL` set
- Ruff lint and mypy type-check pass on the new model file

## Risks / Open Questions

- **Enum in migration**: autogenerate sometimes emits the SQLAlchemy-side enum name rather than the PostgreSQL `CREATE TYPE` statement. If the generated migration lacks the `sa.Enum('high', 'medium', 'low', name='churntier')` backed by `op.create_enum_type` or a server-default, manually add the PostgreSQL enum type before the `create_table` call.
