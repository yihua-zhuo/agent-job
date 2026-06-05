Now I have everything I need. Here's the implementation plan:

# Implementation Plan — Issue #582

## Goal
Add five nullable lead-score columns (`score`, `tier`, `score_factors`, `top_factors`, `recommendations`) to `CustomerModel` and create `ScoreRequest`/`ScoreResponse` Pydantic schemas. An alembic migration will apply the schema change to the database.

## Affected Files
- `src/db/models/customer.py` — add five ORM columns and update `to_dict()`
- `src/models/score.py` — new file with `ScoreRequest` and `ScoreResponse` Pydantic schemas
- `alembic/versions/<new_revision>.py` — new migration adding columns to the `customers` table
- `tests/unit/domain_handlers/customers.py` — add score fields to every mock record in the customer SQL handler

## Implementation Steps
1. **Add ORM columns to `CustomerModel`** (`src/db/models/customer.py`):
   - Import `Integer` and `JSON` alongside existing imports
   - Add `score: Mapped[int | None] = mapped_column(Integer, nullable=True)` after `recycle_history`
   - Add `tier: Mapped[str | None] = mapped_column(String(50), nullable=True)` after `score`
   - Add `score_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)` after `tier`
   - Add `top_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)` after `score_factors`
   - Add `recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)` after `top_factors`
   - Update `to_dict()` to include all five new fields with appropriate None defaults (`self.score`, `self.tier`, `self.score_factors or {}`, `self.top_factors or []`, `self.recommendations or []`)

2. **Create `src/models/score.py`** with two Pydantic schemas:
   - `ScoreRequest(BaseModel)`: fields matching what the scoring engine needs as input (e.g. `customer_id`, `tenant_id`, optional raw attributes). Fields and types should match the existing `SmartCategorizationService.score_lead()` input shape.
   - `ScoreResponse(BaseModel)`: fields `score: int | None`, `tier: str | None`, `score_factors: dict | None`, `top_factors: list | None`, `recommendations: list | None`, plus a `to_dict()` method. Both schemas should follow the same `Annotated[..., Field(...)]` pattern used in `CustomerCreateDTO`.

3. **Generate the alembic migration**:
   - Spin up the clean `alembic_dev` database as documented in `CLAUDE.md`
   - Run `alembic upgrade head` to bring it to current state
   - Run `alembic revision --autogenerate -m "add_lead_score_columns"` — alembic will diff `Base.metadata` (which now includes the five new `CustomerModel` columns) against the live schema and produce the upgrade/downgrade SQL
   - Review the generated file: ensure `op.add_column('customers', sa.Column('score', sa.Integer(), nullable=True))` and the same pattern for `tier` (String(50)), `score_factors` (postgresql.JSON), `top_factors` (postgresql.JSON), `recommendations` (postgresql.JSON) appear in `upgrade()`. Fill in `downgrade()` to drop the five columns.
   - Run `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` to verify round-trip
   - Run a second `alembic revision --autogenerate -m "drift_check"` to confirm an empty diff; delete that file if both up/down are `pass`

4. **Update mock SQL handler** (`tests/unit/domain_handlers/customers.py`):
   - Add `"score": None`, `"tier": None`, `"score_factors": None`, `"top_factors": None`, `"recommendations": None` to every mock record dict in `make_customer_handler` (INSERT record, UPDATE fallback fixtures, `from customers where id` fixtures, and the hardcoded `select from customers` rows) so that any test touching score fields via the mock session won't raise `KeyError`.

5. **Add unit test** (`tests/unit/test_customer_model.py` or a new `tests/unit/test_score_schemas.py`):
   - Import `ScoreRequest` and `ScoreResponse` from `src.models.score`
   - Test `ScoreResponse` round-trip: construct with all fields set, call `to_dict()`, confirm keys and values match; construct with all `None`, confirm `to_dict()` returns all `None`
   - Test `ScoreResponse` serialization of `score_factors` dict, `top_factors` list, and `recommendations` list
   - Test `ScoreRequest` validation: required fields raise `ValidationError` when omitted; valid input accepted

6. **Run the full test suite and lint**:
   - `ruff check src/ && ruff format --check src/`
   - `pytest tests/unit/ -v` — all tests must pass
   - `mypy src/` — no new errors

## Test Plan
- Unit tests in `tests/unit/`: Add `tests/unit/test_score_schemas.py` covering `ScoreRequest` and `ScoreResponse` construction, field validation, and `to_dict()` serialization. Update `tests/unit/domain_handlers/customers.py` to include score fields in every mock record so existing tests continue to pass once columns are added to the ORM.
- Integration tests in `tests/integration/`: Add `tests/integration/test_score_integration.py` (or extend an existing customer integration test) that creates a customer with score fields set, queries it back, and asserts the values round-trip correctly through the real database.

## Acceptance Criteria
- `CustomerModel` has five new nullable columns (`score`, `tier`, `score_factors`, `top_factors`, `recommendations`) matching the ORM definition in `src/db/models/customer.py`
- `ScoreRequest` and `ScoreResponse` Pydantic schemas exist in `src/models/score.py` with all required fields
- `alembic upgrade head` applies the new migration against a live PostgreSQL database without errors; `alembic downgrade -1` reverts cleanly
- All unit tests pass (`pytest tests/unit/ -v`)
- `ruff check src/` reports no errors; `mypy src/` reports no new errors
