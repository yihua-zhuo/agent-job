Now I have everything I need. Here's the implementation plan:

# Implementation Plan — Issue #597

## Goal

Add `Recommendation` and `RiskSignal` ORM models for storing AI-generated sales recommendations and risk signals per opportunity. These models enable the system to persist recommendations (next action, confidence, reasoning) and risk assessments (level, factors) on opportunities, replacing the current stateless `SalesRecommendationService`.

## Affected Files

- `src/db/models/recommendation.py` — new file: `RecommendationModel` and `RiskSignalModel` ORM classes
- `alembic/versions/<revision>_add_recommendations_table.py` — new file: migration to create `recommendations` and `risk_signals` tables
- `tests/integration/test_recommendation_integration.py` — new file: integration tests for create/retrieve flow
- `src/db/models/__init__.py` — no changes needed; auto-discovery via `pkgutil.iter_modules` picks up new model file automatically
- `alembic/env.py` — no changes needed; already does `import db.models` which auto-discovers all model modules

## Implementation Steps

1. **Create `src/db/models/recommendation.py`** with two SQLAlchemy models:
   - `RecommendationModel` (`__tablename__ = "recommendations"`) with fields: `id` (pk), `tenant_id` (indexed), `opportunity_id` (FK to `opportunities.id`, indexed), `next_action` (SQLAlchemy `Enum` with `values_callable` storing `"call" | "email" | "meeting" | "demo" | "proposal"`), `confidence` (`Float`, 0.0–1.0), `reasons` (`JSON`), `similar_deals` (`JSON`), `created_at`, `updated_at`. Include `to_dict()` method.
   - `RiskSignalModel` (`__tablename__ = "risk_signals"`) with fields: `id` (pk), `tenant_id` (indexed), `opportunity_id` (FK to `opportunities.id`, indexed), `risk_level` (SQLAlchemy `Enum` storing `"low" | "medium" | "high"`), `risk_factors` (`JSON`), `created_at`, `updated_at`. Include `to_dict()` method.
   - Use `Mapped[...]` typed columns, `server_default=func.now()` for timestamps, `onupdate=func.now()` for `updated_at`. Store enum values as lowercase strings via `values_callable=lambda x: x` or explicit `enum_values=["call", ...]`.

2. **Generate the Alembic migration**:
   - Run `docker compose -f configs/docker-compose.test.yml up -d test-db` and set up a disposable `alembic_dev` database (drop + create).
   - Run `alembic upgrade head` to bring it to current head.
   - Run `alembic revision --autogenerate -m "add_recommendations_and_risk_signals_tables"`.
   - Review the generated migration: add composite index on `(tenant_id, opportunity_id)` on both tables, ensure `opportunity_id` FK uses `ondelete="CASCADE"`, verify JSON columns are created correctly.
   - Run `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` to verify reversibility.
   - Run a second `alembic revision --autogenerate -m "drift_check"` to confirm no residual drift; delete if both `upgrade()`/`downgrade()` are `pass`.

3. **Verify auto-discovery** — confirm `db.models.__init__.py`'s `pkgutil.iter_modules` finds the new `recommendation.py` file automatically. The `import db.models` in `alembic/env.py` already covers this; no import needed in `env.py`.

4. **Create `tests/integration/test_recommendation_integration.py`**:
   - Import `RecommendationModel` from `db.models`, `SalesService` from `services.sales_service`, `CustomerService`, `UserService` from appropriate modules.
   - Helper `_seed_opportunity(async_session, tenant_id, customer_id)` that calls `SalesService.create_opportunity`.
   - `TestRecommendationCreateAndGet` class with:
     - `test_create_and_get_recommendation` — seeds customer + user, creates opportunity, inserts `RecommendationModel` row directly via `async_session`, fetches it back, asserts all fields (next_action, confidence, reasons JSON, similar_deals JSON).
     - `test_create_and_get_risk_signal` — same pattern for `RiskSignalModel`.
     - `test_recommendation_tenant_isolation` — creates recommendations for two different tenant_ids on the same opportunity_id, verifies each tenant only sees its own row.
   - Use `@pytest.mark.integration` on the class and `@pytest.mark.asyncio` on each method.

## Test Plan

- Unit tests in `tests/unit/`: No new unit test files needed — the mock infrastructure in `tests/unit/conftest.py` does not cover ORM model instantiation, and the issue does not require unit-level model tests.
- Integration tests in `tests/integration/`: `tests/integration/test_recommendation_integration.py` — covers creating and retrieving a `Recommendation` and a `RiskSignal`, plus tenant isolation.

## Acceptance Criteria

- Running `ruff check src/db/models/recommendation.py` passes with no errors.
- `alembic current` shows the new revision applied; `alembic history` lists the new migration.
- `pytest tests/integration/test_recommendation_integration.py -v` passes, including the tenant isolation test.
- `RecommendationModel` and `RiskSignalModel` are importable from `db.models`.
- `to_dict()` on both models returns JSON-serializable output including the JSON columns.

## Risks / Open Questions

- **JSON column type**: No existing model in `src/db/models/` uses a `JSON` column, so the exact SQLAlchemy type (`JSON` vs `JSONB`) has not been established in this codebase. Use `JSON` (PostgreSQL `json`) for broad compatibility; swap to `JSONB` for better indexing performance in a follow-up if needed.
- **Enum on FK deletion**: Both models should use `ondelete="CASCADE"` on `opportunity_id` so that deleting an opportunity removes its recommendations and risk signals. This should be verified in the migration review step.
- **One-to-one vs one-to-many per opportunity**: The current design assumes one recommendation and one risk signal per opportunity. If multiple recommendations per opportunity are needed in the future, add a `UNIQUE` constraint on `(opportunity_id, tenant_id)` for the recommendations table or handle versioning differently.
