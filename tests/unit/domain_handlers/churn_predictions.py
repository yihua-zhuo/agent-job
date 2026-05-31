"""Churn prediction SQL handlers for unit tests."""

from __future__ import annotations

import json as _json

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def make_churn_prediction_handler(state: MockState):
    """Handle all churn_prediction-related SQL (INSERT, UPDATE, DELETE, SELECT)."""

    def handler(sql_text, params):
        if "insert into churn_predictions" in sql_text:
            cid = getattr(state, "churn_predictions_next_id", 1)
            setattr(state, "churn_predictions_next_id", cid + 1)
            record = {
                "id": cid,
                "tenant_id": params.get("tenant_id", 0),
                "customer_id": params.get("customer_id", 0),
                "score": params.get("score", 0.0),
                "tier": params.get("tier"),
                "factors": _json.dumps(params.get("factors", [])),
                "predicted_at": params.get("predicted_at"),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            if not hasattr(state, "churn_predictions"):
                state.churn_predictions = {}
            state.churn_predictions[cid] = record
            return MockResult([MockRow(record.copy())])

        if "select" in sql_text and "from churn_predictions" in sql_text:
            tenant_id = params.get("tenant_id", 0)
            rows = []
            for rec in getattr(state, "churn_predictions", {}).values():
                if rec.get("tenant_id") == tenant_id:
                    rows.append(MockRow(rec.copy()))
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_churn_prediction_handler(state)]


__all__ = ["get_handlers", "make_churn_prediction_handler"]
