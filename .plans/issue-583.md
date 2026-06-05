Key findings:
- `CustomerModel` has no `company_size`, `engagement_level`, `budget`, `industry`, or `last_activity_days` fields. It has `score`, `tier`, `score_factors`, `top_factors`, `recommendations` columns (persisted by issue #582's migration).
- `src/models/score.py` already exists with `ScoreRequest` and `ScoreResponse` Pydantic models (the issue says "touch src/models/score.py").
- `src/services/score_service.py` does NOT exist — must be created.
- `src/pkg/errors/app_exceptions.py` has `NotFoundException(resource: str)`.
- `tests/unit/conftest.py` has `MockState`, `MockRow`, `MockResult`, and `make_mock_session`.
- Board 582 is referenced as a dependency but the file doesn't exist on this branch.

Here is the implementation plan:

# Implementation Plan — Issue #583

## Goal
Implement `ScoreService` with a deterministic, non-AI static rule engine that computes a 0–100 health score for a customer, classifies it into a tier (A/B/C/D), surfaces the top contributing factors, and returns actionable recommendations — without calling any AI agent or persisting score history.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0583-implement-scoreservice-with-static-non-ai-scoring-logic.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0583-implement-scoreservice-with-static-non-ai-scoring-logic.md`

## Affected Files
- `src/services/score_service.py` — **new file**: `ScoreService` class with `__init__(self, session: AsyncSession)`, `calculate_score(customer_id, tenant_id) -> tuple[int, str, list[str], list[str]]`, and `get_score(customer_id, tenant_id) -> tuple[int, str, list[str], list[str]]`. Static rule engine reads from `CustomerModel` persisted score columns.
- `src/models/score.py` — **modify**: add `ScoreTier` enum (A/B/C/D) to the existing file alongside the existing `ScoreRequest` / `ScoreResponse` schemas.
- `src/models/__init__.py` — **modify**: re-export `ScoreTier` (and `ScoreResponse` if not already exported).
- `tests/unit/test_score_service.py` — **new file**: unit tests covering tier A, tier D, mid-tier, not-found, get_score delegation, zero-contribution filter, and recommendation mapping.

## Implementation Steps
1. **Add `ScoreTier` enum to `src/models/score.py`**: Append a `ScoreTier(StrEnum)` with values `"A"`, `"B"`, `"C"`, `"D"` to the existing `score.py` file. The existing `ScoreResponse` schema is unchanged. Update `src/models/__init__.py` to export `ScoreTier`.

2. **Create `src/services/score_service.py`**: Define module-level constants — `FIELD_WEIGHTS` (dict mapping field name → weight summing to 100), `TIER_BOUNDARIES` (list of `(threshold, ScoreTier)` tuples ordered highest-first: `[(80, ScoreTier.A), (60, ScoreTier.B), (40, ScoreTier.C)]`), and `FIELD_RECOMMENDATIONS` (dict mapping field name → recommendation string). Implement `ScoreService` with `__init__(self, session: AsyncSession)` storing `self.session`. `calculate_score` queries `CustomerModel` filtered by `id == customer_id` AND `tenant_id == tenant_id`; raises `NotFoundException("Customer")` if absent. Then reads the persisted `score_factors` JSON column from the customer row (populated by issue #582's pipeline), sums each factor's contribution, clamps to 0–100, maps to tier via `TIER_BOUNDARIES`, extracts the top 2–3 non-zero factor names as `top_factors`, and generates `recommendations` by looking up each top factor in `FIELD_RECOMMENDATIONS`. Returns `(score, tier.value, top_factors, recommendations)`.

3. **Implement `get_score`**: Simple delegation to `calculate_score` (no caching at this stage — that is handled by the #585 auto-recalculation board). Both methods share the same signature and return type.

4. **Handle missing/None score_factors**: If `customer.score_factors` is `None` or empty, default to a neutral score of 50 / tier C with empty factor lists, so the endpoint returns a valid result rather than raising. This is the static engine's graceful-degradation path when no upstream scoring run has populated the factors yet.

5. **Write `tests/unit/test_score_service.py`**: Define a `mock_db_session` fixture using `MockState` + a custom execute handler that returns `MockRow` objects representing customers with different `score_factors` payloads. Write the seven test cases listed in the dev-plan §5 Step 3 (tier A, tier D, mid-tier, not-found, get_score delegation, zero-contribution exclusion, recommendation mapping).

6. **Run full verification**: `ruff check src/services/score_service.py src/models/score.py` → 0 errors; `ruff format --check src/services/score_service.py src/models/score.py` → pass; `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → ≥ 7 passed.

## Test Plan
- **Unit tests in `tests/unit/`**: Create `tests/unit/test_score_service.py` with a `mock_db_session` fixture that returns a `MockResult` with a `MockRow` for a pre-seeded customer. Cover:
  - `test_calculate_score_tier_a` — customer with `score_factors` summing high → tier A, score ≥ 80
  - `test_calculate_score_tier_d` — all factors near zero → tier D, score < 40
  - `test_calculate_score_tier_b_or_c` — mid-range factors → score in 40–79
  - `test_calculate_score_not_found` — `MockResult` returns empty → raises `NotFoundException`
  - `test_calculate_score_none_factors` — `score_factors` is `None` → returns neutral 50/C, empty lists
  - `test_get_score_delegates` — `get_score` returns identical tuple to `calculate_score`
  - `test_top_factors_excludes_zero` — factors scoring 0 do not appear in `top_factors`
  - `test_recommendations_match_top_factors` — each non-zero top factor maps to a `FIELD_RECOMMENDATIONS` entry
- **Integration tests in `tests/integration/`**: No integration tests required for this board (the dev-plan §1.4 marks integration as "如 integration test is created" — conditional). The service operates entirely on the existing `customers` table and uses the `AsyncSession` injection pattern; a future board can add real-DB coverage.
- **Dev-plan verification**: From the target board §6:
  - `ruff check src/services/score_service.py src/models/score.py` → 0 errors
  - `ruff format --check src/services/score_service.py src/models/score.py` → pass
  - `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → ≥ 7 passed (dev-plan says ≥ 5; we write 8 for full coverage)
  - `PYTHONPATH=src mypy src/services/score_service.py` → 0 errors (if mypy is configured)
  - Alembic verification is N/A (no new migration in this board)

## Acceptance Criteria
- `ScoreService.__init__` accepts `session: AsyncSession` with no default value, and never allows `session=None`.
- `calculate_score(customer_id, tenant_id)` returns `(score, tier, top_factors, recommendations)` where `score` is clamped 0–100, `tier` is one of `"A"`/`"B"`/`"C"`/`"D"`, `top_factors` has ≤ 3 entries, and `recommendations` aligns 1:1 with `top_factors`.
- `calculate_score` raises `NotFoundException("Customer")` when the customer is absent for the given tenant (i.e., the query returns no row).
- `get_score(customer_id, tenant_id)` returns the same value as `calculate_score` for the same inputs.
- All SQL queries in the service filter by `tenant_id`.
- `ruff check` and `ruff format --check` pass for both new and modified files.
- `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → ≥ 7 passed.
- No AI agent or LLM call is made anywhere in `score_service.py` (static rules only).
- No new ORM model or Alembic migration is created in this board (score persistence is handled by #582).
