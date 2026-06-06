I now have all the information needed. The dev-plan's test approach using `make_count_handler` will work for activity counts (via `make_activity_handler`), but for tickets and opportunities the mocks return hardcoded values. I need to account for this in the test plan. The test assertions should focus on structural correctness (score in 0-100, valid tier, 3 risk factors, list of actions) rather than precise numeric values.

# Implementation Plan — Issue #573

## Goal
Create a new `ChurnPredictionService` class in `src/services/churn_prediction_service.py` that computes a real-time 0-100 churn score from four customer dimensions (login_frequency, purchase_recency, support_ticket_count, engagement_score) using a weighted formula. The service returns a domain object (`ChurnPrediction` dataclass) with score, tier, top-3 risk factors, and recommended actions — no DB writes. This fills a gap left by the existing DB-backed `churn_prediction.py`, which will be complemented by this rule-based entry point. The API router and downstream features (#672, #673, #674) depend on this service being available.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0573-implement-churnpredictionservice-with-scoring-logic.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0573-implement-churnpredictionservice-with-scoring-logic.md`

## Affected Files
- `src/services/churn_prediction_service.py` — **new file**; defines `ChurnRiskFactor` and `ChurnPrediction` dataclasses + `ChurnPredictionService` class with `calculate_score` method
- `tests/unit/test_churn_prediction_service.py` — **new file**; unit tests with `MockState` + `make_customer_handler` + `make_count_handler`

## Implementation Steps

1. **Create `src/services/churn_prediction_service.py` with imports, dataclasses, and class skeleton.**
   - File: `src/services/churn_prediction_service.py`
   - Imports: `dataclass` from `dataclasses`, `UTC`/`datetime`/`timedelta` from `datetime`, `and_`/`func`/`select` from `sqlalchemy`, `AsyncSession` from `sqlalchemy.ext.asyncio`, `CustomerModel` from `db.models.customer`, `ActivityModel` from `db.models.activity`, `OpportunityModel` from `db.models.opportunity`, `TicketModel` from `db.models.ticket`, `NotFoundException` from `pkg.errors.app_exceptions`.
   - Define `@dataclass class ChurnRiskFactor` with fields `name: str`, `weight: float`, `score: float`, `description: str`.
   - Define `@dataclass class ChurnPrediction` with fields `customer_id: int`, `score: float`, `tier: str`, `top_3_risk_factors: list[ChurnRiskFactor]`, `recommended_actions: list[str]`.
   - Define `class ChurnPredictionService` with `WEIGHTS` class constant (4 dimensions × 0.25 each) and `__init__(self, session: AsyncSession)` that stores `self.session = session`. No default value for `session`.

2. **Implement `async _fetch_raw_metrics(self, customer_id: int, tenant_id: int) -> dict`.**
   - Query `CustomerModel` by `id` + `tenant_id`; if not found, `raise NotFoundException("Customer")`.
   - **login_frequency**: `SELECT count(ActivityModel.id) WHERE tenant_id=? AND customer_id=? AND created_at >= now - 30d`. Fallback to 0 if no activity.
   - **purchase_recency**: `SELECT max(OpportunityModel.created_at) WHERE tenant_id=? AND customer_id=? AND stage='won'`. Compute `days_since`; normalize tz-naive to UTC. Fallback to 90 days if no won opportunity.
   - **support_ticket_count**: `SELECT count(TicketModel.id) WHERE tenant_id=? AND customer_id=? AND status IN ('open','pending')`. Fallback to 0.
   - **engagement_score_raw**: Reuse login_count as proxy (activity count, to be normalized later).
   - Return `dict` with keys: `login_frequency`, `purchase_recency_days`, `support_ticket_count`, `engagement_score_raw`.

3. **Implement `_normalize_score`, `_compute_tier`, and `_build_top_3_factors` private methods.**
   - `_normalize_score(name, raw) -> float` maps each dimension's raw value to 0-100:
     - `login_frequency`: `min(raw / 10 * 100, 100)` — 10+ logins = full score.
     - `purchase_recency`: `max(0.0, 100.0 - raw)` — 0 days = full score, 90+ days = 0.
     - `support_ticket_count`: `min(raw / 5 * 100, 100)` — 5+ tickets = full score (this is "health score" — low ticket count = healthy).
     - `engagement_score`: `min(raw / 30 * 100, 100)` — 30+ activities = full score.
   - `_compute_tier(score) -> str`: `>= 70` → `"high"`, `>= 40` → `"medium"`, `< 40` → `"low"`.
   - `_build_top_3_factors(name_to_score) -> list[ChurnRiskFactor]`: sort dimensions by sub-score descending, return top 3 as `ChurnRiskFactor(name, weight, score, description)` objects.

4. **Implement `async calculate_score(self, customer_id: int, tenant_id: int) -> ChurnPrediction`.**
   - Call `_fetch_raw_metrics` to get raw values.
   - Normalize each dimension to 0-100 sub-score via `_normalize_score`.
   - Compute weighted total: `login_score * 0.25 + purchase_score * 0.25 + (100 - support_score) * 0.25 + engagement_score * 0.25`. (Support score is inverted: more tickets → higher churn contribution.)
   - Clamp to [0, 100] with `min(score, 100.0)`, round to 2 decimal places.
   - Determine `tier` via `_compute_tier`.
   - Build `top_3_risk_factors` via `_build_top_3_factors`.
   - Generate `recommended_actions: list[str]` based on raw metrics:
     - `support_ticket_count > 2` → `"优先处理客户工单，降低流失风险"`
     - `purchase_recency_days > 60` → `"客户长期无购买记录，触发重新激活营销"`
     - `login_frequency < 3` → `"客户登录频率低，建议发送个性化内容激活"`
     - If none triggered → `"客户状态健康，维持常规维护"`
   - Return `ChurnPrediction` dataclass (not dict, not `ApiResponse`).

5. **Create `tests/unit/test_churn_prediction_service.py` with unit tests.**
   - Imports: `pytest`, `ChurnPredictionService` + `ChurnPrediction` from `services.churn_prediction_service`, `NotFoundException` from `pkg.errors.app_exceptions`, `make_mock_session` + `MockState` + `make_customer_handler` + `make_count_handler` from `tests.unit.conftest`.
   - `mock_db_session` fixture: `state = MockState(); state.customers[1] = {"id": 1, "tenant_id": 1, "name": "Test"}; return make_mock_session([make_customer_handler(state), make_count_handler(state)])`.
   - **Test 1 — Happy path**: `customer_id=1, tenant_id=1` exists. Assert `isinstance(result, ChurnPrediction)`, `0.0 <= result.score <= 100.0`, `result.tier in ("high", "medium", "low")`, `len(result.top_3_risk_factors) == 3`, `isinstance(result.recommended_actions, list) and len(result.recommended_actions) >= 1`.
   - **Test 2 — Customer not found**: `customer_id=9999, tenant_id=1`. Assert `pytest.raises(NotFoundException)`.
   - **Test 3 — Returned object is dataclass, not dict**: Assert `result` is `ChurnPrediction` (not `dict`, not `ApiResponse`). Assert all fields are accessible as attributes.
   - **Test 4 — Tier boundary with seeded metrics**: Use a `mock_db_session` with specific `state.activities` entries to exercise different score ranges and verify `tier` computation logic (note: opportunity/ticket mock data comes from hardcoded handlers, so assertions should validate the tier mapping contract is wired correctly, not exact scores).

## Test Plan
- **Unit tests in `tests/unit/`**: `test_churn_prediction_service.py` — covers happy path (customer exists, all dimensions return data), error path (customer not found → `NotFoundException`), and structural validation (returns `ChurnPrediction` dataclass with correct fields, score in 0-100, valid tier, 3 risk factors, non-empty recommendations).
- **Integration tests in `tests/integration/`**: None — the dev-plan §1.3 explicitly excludes DB writes, and all DB reads are exercised through unit-test mocks. No integration test needed.
- **Dev-plan verification** (target-board §6):
  - `ruff check src/services/churn_prediction_service.py` → 0 errors (Step 1–4 completion gate)
  - `ruff format --check src/services/churn_prediction_service.py` → exit 0 (Step 4 completion gate)
  - `PYTHONPATH=src python -c "from services.churn_prediction_service import ChurnPredictionService, ChurnPrediction; print('ok')"` → `ok` (import sanity check)
  - `PYTHONPATH=src pytest tests/unit/test_churn_prediction_service.py -v` → `3+ passed` (Step 5 completion gate)

## Acceptance Criteria
- `src/services/churn_prediction_service.py` exists and defines `ChurnPredictionService`, `ChurnPrediction`, and `ChurnRiskFactor`.
- `ChurnPredictionService.__init__` accepts `session: AsyncSession` with no default value.
- `calculate_score(customer_id, tenant_id)` returns a `ChurnPrediction` dataclass (not dict, not `ApiResponse`).
- The returned object has `score` in `[0.0, 100.0]`, `tier` in `{"high", "medium", "low"}`, exactly 3 `ChurnRiskFactor` items in `top_3_risk_factors`, and a non-empty `list[str]` `recommended_actions`.
- Tier thresholds: `score >= 70` → `"high"`, `score >= 40` → `"medium"`, `score < 40` → `"low"`.
- `NotFoundException` is raised when the customer does not exist for the given `tenant_id`.
- All SQL queries filter by `tenant_id`.
- `ruff check src/services/churn_prediction_service.py` → 0 errors.
- `ruff format --check src/services/churn_prediction_service.py` → exit 0.
- `PYTHONPATH=src pytest tests/unit/test_churn_prediction_service.py -v` → all tests pass (≥ 3 passed).
- `PYTHONPATH=src python -c "from services.churn_prediction_service import ChurnPredictionService, ChurnPrediction; print('ok')"` → `ok`.
