"""Churn risk REST endpoints — single + batch.

Wraps ``ChurnPredictionService`` for HTTP clients. The single-customer
endpoint returns the latest stored prediction or computes a new one if
none exists; the batch endpoint accepts a list of customer IDs and
returns a prediction for each, skipping customers that cannot be found.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import NotFoundException
from services.churn_prediction_service import ChurnPredictionService

churn_risk_router = APIRouter(prefix="/api/v1/customers", tags=["churn-risk"])


class BatchPredictRequest(BaseModel):
    customer_ids: list[int] = Field(..., min_length=1, max_length=500)


@churn_risk_router.get("/{customer_id}/churn-risk")
async def get_churn_risk(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    try:
        prediction = await svc.get_churn_prediction(customer_id, tenant_id=ctx.tenant_id)
    except NotFoundException:
        prediction = await svc.calculate_score(customer_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": prediction.to_dict()}


@churn_risk_router.post("/churn-predict-batch")
async def predict_churn_batch(
    body: BatchPredictRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    predictions = await svc.predict_churn(body.customer_ids, tenant_id=ctx.tenant_id)
    return {
        "success": True,
        "data": {"predictions": [p.to_dict() for p in predictions]},
    }
