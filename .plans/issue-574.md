# Implementation Plan — Issue #574

## Goal
Add two REST endpoints (`GET /api/v1/customers/{id}/churn-risk` and `POST /api/v1/customers/churn-predict-batch`) that expose the existing `ChurnPredictionService` to HTTP clients. The single-customer endpoint returns the latest stored prediction or computes a new one if none exists; the batch endpoint accepts a list of customer IDs and returns predictions for each. Both endpoints follow the project's standard service/router/envelope pattern.

## Source Contract
Dev-plan target: `docs/dev-plan/60-analytics/0574-add-churn-risk-api-endpoints.md`
Template depth: `deep`
Reading order followed:
1. `docs/dev-plan/README.md` — global constraints §2, cross-cutting §3, auto-discovery via `iter_routers()`
2. `docs/dev-plan/_template-deep.md` — deep-template structure (frozen interfaces, known pitfalls, rollback)
3. `docs/dev-plan/60-analytics/0574-add-churn-risk-api-endpoints.md` — target board

## Affected Files
- `src/api/routers/churn_risk.py` — **new file**: `churn_risk_router` with two endpoints
- `src/main.py` — no manual edit needed; `iter_routers()` in `src/api/__init__.py` auto-discovers any module-level `*_router` variable in `src/api/routers/`
- `tests/unit/test_churn_risk_router.py` — **new file**: 4 unit tests (normal + error for each endpoint)

## Implementation Steps

### Step 1: Verify service interface and serialization path
Before writing any code, confirm how `ChurnPredictionService` returns prediction objects and whether they support `.to_dict()`. The service lives at `src/services/churn_prediction_service.py` and exposes:
- `calculate_score(customer_id, tenant_id) -> ChurnPrediction` — computes a fresh prediction (returns a dataclass with fields `customer_id`, `score`, `tier`, `top_3_risk_factors`, `recommended_actions`)
- `get_churn_prediction(customer_id, tenant_id) -> ChurnPrediction` — returns a `ChurnPrediction` dataclass, or raises `NotFoundException`
- `predict_churn(customer_ids, tenant_id) -> list[ChurnPrediction]` — batch computation

Since both methods return a `ChurnPrediction` dataclass that has a `.to_dict()` method, serialize via `prediction.to_dict()` directly.

### Step 2: Create `src/api/routers/churn_risk.py`

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from internal.middleware.fastapi_auth import AuthContext, require_auth
from db.connection import get_db
from services.churn_prediction_service import ChurnPredictionService

router = APIRouter(prefix="/api/v1/customers", tags=["churn-risk"])


class BatchPredictRequest(BaseModel):
    customer_ids: list[int] = Field(..., min_length=1, max_length=500)


@router.get("/{customer_id}/churn-risk")
async def get_churn_risk(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    prediction = await svc.get_or_compute_prediction(customer_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": prediction.to_dict()}


@router.post("/churn-predict-batch")
async def predict_churn_batch(
    body: BatchPredictRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    found, skipped = await svc.predict_churn(body.customer_ids, tenant_id=ctx.tenant_id)
    return {
        "success": True,
        "data": {
            "predictions": [p.to_dict() for p in found],
            "skipped_customer_ids": skipped,
        },
    }
```

Notes:
- Router variable must be named `churn_risk_router` (not `router`) for auto-discovery by `iter_routers()` per `src/api/__init__.py` line 22–40.
- `BatchPredictRequest` enforces `min_length=1` (rejects empty list with 422) and `max_length=500` (guards against oversized batches per dev-plan §7 risk table).
- The GET endpoint delegates the "return latest or compute" logic to `get_or_compute_prediction`, keeping the router a thin serialization layer per CLAUDE.md §Router Pattern.
- The batch endpoint returns `(found, skipped)` from `predict_churn` so the client can see which customer IDs were excluded (e.g., not found), making partial failures visible.
- Serialize via `.to_dict()` per CLAUDE.md §Service Pattern.

### Step 3: Write unit tests in `tests/unit/test_churn_risk_router.py`

Follow the pattern in `tests/unit/test_enrichment_router.py`:
- Monkeypatch `api.routers.churn_risk.ChurnPredictionService` to return `AsyncMock` instances.
- Override `require_auth` and `get_db` dependencies on a minimal `FastAPI()` app that includes only `churn_risk_router`.
- Register `AppException` and `ValidationError` exception handlers on the test app.
- Use `TestClient(app, raise_server_exceptions=False)`.

Test classes and cases:

**`TestGetChurnRisk`:**
- `test_returns_existing_prediction` — mock `get_churn_prediction` to return a prediction; assert 200, `success: True`, `data` contains expected fields.
- `test_computes_when_not_found` — mock `get_churn_prediction` to raise; mock `calculate_score` to return a prediction; assert 200 and the computed result is returned.
- `test_not_found_returns_404` — mock `get_or_compute_prediction` to raise `NotFoundException`; assert 404 in response.

**`TestPredictBatch`:**
- `test_returns_predictions` — mock `predict_churn` to return a list; POST with `{"customer_ids": [1, 2]}`; assert 200 and `data.predictions` has the expected length.
- `test_empty_list_rejected` — POST with `{"customer_ids": []}`; assert 422 (Pydantic `min_length=1`).
- `test_oversized_batch_rejected` — POST with 501 IDs; assert 422 (`max_length=500`).

## Test Plan
- Unit tests in `tests/unit/`: **new file** `test_churn_risk_router.py` with 7 test cases across 2 test classes covering both endpoints (normal, fallback, error paths).
- Integration tests in `tests/integration/`: **none** — the dev-plan §1.3 explicitly excludes end-to-end integration; the service-layer integration is covered by #573. This is a pure router-layer change that needs only unit tests per dev-plan §5 Step 3.
- Dev-plan verification (§6):
  - `ruff check src/api/routers/churn_risk.py` → 0 errors
  - `ruff check src/main.py` → 0 errors (no changes expected, but verify)
  - `PYTHONPATH=src pytest tests/unit/test_churn_risk_router.py -v` → 7 passed
  - `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → not applicable for this issue (no new migrations; #573 owns the churn_predictions table)

## Acceptance Criteria
- `GET /api/v1/customers/{customer_id}/churn-risk` returns 200 with `{"success": true, "data": {<prediction fields>}}` when a prediction exists
- `GET /api/v1/customers/{customer_id}/churn-risk` returns 200 with a freshly computed prediction when none is stored
- `GET /api/v1/customers/{customer_id}/churn-risk` returns 404 when the customer does not exist (service raises `NotFoundException`)
- `POST /api/v1/customers/churn-predict-batch` returns 200 with `{"success": true, "data": {"predictions": [...]}}` for valid input
- `POST /api/v1/customers/churn-predict-batch` returns 422 for empty `customer_ids` or lists exceeding 500 items
- `ruff check src/api/routers/churn_risk.py` passes with 0 errors
- `PYTHONPATH=src pytest tests/unit/test_churn_risk_router.py -v` shows 7 passed
- Router is auto-registered via `iter_routers()` — confirmed by app startup with no manual `main.py` edits
