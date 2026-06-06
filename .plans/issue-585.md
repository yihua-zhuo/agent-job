Now I have all the context I need. The `AIAgentClient` class does not exist yet — it's the dependency that #584 must deliver. The plan must account for the fact that this interface is TBD per the dev-plan.

Key facts I've gathered:
- `ScoreService` exists at `src/services/score_service.py` with `calculate_score` returning a tuple `(score, tier, top_factors, recommendations)`
- The customer router at `src/api/routers/customers.py` L553-595 already calls `ScoreService` and serializes the result dict
- `tests/unit/test_score_service.py` uses `MockState`, `MockRow`, `MockResult` from conftest
- `from src.models.score` is used in `test_score_schemas.py` (note: `from src.` prefix exists in that one file, inconsistent with CLAUDE.md)
- No `AIAgentClient` class exists yet — the dev-plan marks `#584` as TBD
- `conftest.py` already provides `AsyncMock` import
- `agent_service.py` has `AgentService` class but no `AIAgentClient` — the dev-plan §5 Step 1 requires reading #584's output first

---

# Implementation Plan — Issue #585

## Goal
Extend `ScoreService` to optionally call the AI Agent Framework for deeper factor analysis (competitor mentions, decision-maker probability) and to enrich the score response with `similar_leads` and AI-generated recommendations. The public API contract remains unchanged — the AI path is opt-in via an `include_ai` parameter and degrades gracefully when the agent is unavailable, so non-AI callers see the same response shape as before.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0585-integrate-ai-agent-framework-for-enhanced-scoring-factors.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/60-analytics/0585-integrate-ai-agent-framework-for-enhanced-scoring-factors.md`

## Affected Files
- `src/services/score_service.py` — add `ai_annotate_score()` async method; add `include_ai: bool` parameter to `calculate_score`; inject `similar_leads` and AI-enriched `recommendations` into the result tuple when AI succeeds
- `src/models/score.py` — extend `ScoreResponse` with optional `similar_leads: list[dict] | None` field; ensure `to_dict()` includes the new key
- `src/api/routers/customers.py` — add `include_ai: bool = True` query parameter to `POST /{customer_id}/score` and `GET /{customer_id}/score` endpoints; serialize `similar_leads` from result tuple into the response envelope
- `tests/unit/test_score_service.py` — add AI-branch and AI-fallback test cases; use `unittest.mock.patch` to mock the AI agent client; keep existing tests passing

## Implementation Steps

1. **Read #584 output to confirm the AI agent client interface.** The dev-plan §5 Step 1 requires reading `docs/dev-plan/50-automation/` for the #584 board (file is marked TBD — verify it exists at merge time). Extract: the AI client class name, the method to call (expected to be `analyze_factors(entity_id, tenant_id, current_score)`), and the response payload shape (`similar_leads`, `recommendations`).

2. **Extend `ScoreResponse` in `src/models/score.py`** to include `similar_leads: list[dict[str, Any]] | None = None` and update `to_dict()` to include the new key when set. This is backward-compatible — existing consumers that ignore unknown keys are unaffected, and the field is `None` when AI is disabled or unavailable.

3. **Add `ai_annotate_score` method to `ScoreService` in `src/services/score_service.py` L43-46.** The method signature: `async def ai_annotate_score(self, customer_id: int, tenant_id: int, current_score: int) -> dict`. It calls the AI client (imported as `from services.ai_agent_client import AIAgentClient`, the class delivered by #584), wraps the call in `try/except Exception` returning `{}` on any failure (timeout, non-200, malformed payload), and returns a dict with `similar_leads` and `recommendations` keys. Cap `similar_leads` at 10 items to prevent response bloat.

4. **Add `include_ai: bool = True` parameter to `calculate_score` in `src/services/score_service.py` L47.** After computing the static `(score, tier, top_factors, recommendations)` tuple, if `include_ai` is `True`, call `await self.ai_annotate_score(customer_id, tenant_id, score)`. Merge results: return `(score, tier, top_factors, recommendations, similar_leads)` as a 5-tuple. When AI fails or is disabled, `similar_leads` is `[]`. Update `get_score` to match the new signature and forward `include_ai`.

5. **Update the customer router in `src/api/routers/customers.py` L553-595.** Add `include_ai: bool = True` as a query parameter to both `POST /{customer_id}/score` and `GET /{customer_id}/score`. Pass it to the service calls. Extract `similar_leads` from the result tuple (now 5-element) and include it in the response data dict only when it is non-empty — this preserves the response shape for non-AI callers as required by §1.3 of the dev-plan.

6. **Add unit tests in `tests/unit/test_score_service.py`.** Add two new test cases:
   - `test_calculate_score_ai_branch` — patch `services.score_service.AIAgentClient` with an `AsyncMock` whose `analyze_factors()` returns `{"similar_leads": [{"id": 42, "score": 0.9}], "recommendations": ["Expand to segment B"]}`; assert the 5th element of the result tuple is `[{"id": 42, "score": 0.9}]` and the call was made with the expected kwargs.
   - `test_calculate_score_ai_fallback` — patch `AIAgentClient` so `analyze_factors()` raises `Exception("agent down")`; assert the result tuple's `similar_leads` is `[]` and the static score/tier are still computed correctly.
   - `test_calculate_score_include_ai_false_skips_agent` — assert that with `include_ai=False`, the AI client is never instantiated.

7. **Run lint and full test suite.** `ruff check src/services/score_service.py src/models/score.py src/api/routers/customers.py tests/unit/test_score_service.py` → 0 errors. `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → all existing + ≥ 3 new tests pass. `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → no regressions.

## Test Plan
- Unit tests in `tests/unit/test_score_service.py`: add ≥ 3 test cases covering the AI happy path (mocked `AsyncMock.analyze_factors` returns valid data → `similar_leads` populated), AI fallback (agent raises → `similar_leads` is `[]`, static score still computed), and `include_ai=False` opt-out (agent is never called). All existing tests must continue to pass — the tuple return shape grows from 4 to 5 elements, so the router and existing assertions on result indices `[0]`–`[3]` must be checked for breakage.
- Integration tests in `tests/integration/`: none required by the dev-plan §6 (this board is data-layer and service-layer only; no new DB schema is introduced unless #584 requires it).
- Dev-plan verification:
  - §6 acceptance item: `ruff check src/services/score_service.py tests/unit/test_score_service.py` → 0 errors — run `ruff check` on both files.
  - §6 acceptance item: `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → all passed including ≥ 2 new AI-branch tests — run the test suite.
  - §6 acceptance item: `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → no regressions — run the full unit suite.
  - §6 acceptance item: API contract preserved for calls without AI annotation — verified by `test_calculate_score_include_ai_false_skips_agent` and by the existing `test_calculate_score_tier` / `test_get_score_delegates` tests continuing to pass.

## Acceptance Criteria
- `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` passes all existing tests plus ≥ 3 new AI-related test cases.
- `ruff check src/services/score_service.py src/models/score.py src/api/routers/customers.py tests/unit/test_score_service.py` exits 0.
- `calculate_score` returns a 5-element tuple `(score, tier, top_factors, recommendations, similar_leads)` when `include_ai=True`; `similar_leads` is `[]` when the agent is unreachable or returns malformed data (graceful degradation, no exception propagates).
- The `POST /{customer_id}/score` and `GET /{customer_id}/score` responses include `similar_leads` only when the AI path produced non-empty results — the response shape for non-AI callers is unchanged.
- `include_ai=False` on the router endpoints causes the AI client to never be instantiated (verified by mock assertion).

## Risks / Open Questions
- The `AIAgentClient` class and its `analyze_factors` method signature are TBD per the dev-plan §5 Step 1. This board is blocked until #584 merges. If the actual interface differs from the assumed `analyze_factors(entity_id, tenant_id, current_score) -> dict`, the import path and method call in `ai_annotate_score` will need adjustment.
- The current return shape of `calculate_score` is a 4-tuple; changing to a 5-tuple is a breaking change to any external caller indexing into the result. The dev-plan §1.3 requires the API contract to be preserved — the router-level response shape stays the same because it accesses `result[0]`–`result[3]` by index, but if the router is updated to also access `result[4]`, that change must be coordinated. A safer alternative is to switch to a `ScoreResponse` Pydantic object as the return type, but that is a larger refactor outside this board's scope.
