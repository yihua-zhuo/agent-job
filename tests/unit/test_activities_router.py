"""Unit tests for src/api/routers/activities.py — /api/v1/activities endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from models.response import ResponseStatus
from api.routers.activities import (
    activities_router,
    _http_status,
    _activity_to_data,
)
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_service_response(status=ResponseStatus.SUCCESS, data=None, message="OK"):
    resp = MagicMock()
    resp.status = status
    resp.data = data
    resp.message = message
    return resp


# ---------------------------------------------------------------------------
# Mock activity object
# ---------------------------------------------------------------------------

class MockActivity:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)
        # Default attributes
        if not hasattr(self, 'id'):
            self.id = 1
        if not hasattr(self, 'tenant_id'):
            self.tenant_id = 1
        if not hasattr(self, 'customer_id'):
            self.customer_id = 1
        if not hasattr(self, 'opportunity_id'):
            self.opportunity_id = None
        if not hasattr(self, 'type'):
            self.type = "call"
        if not hasattr(self, 'content'):
            self.content = "Activity content"
        if not hasattr(self, 'created_by'):
            self.created_by = 99
        if not hasattr(self, 'created_at'):
            self.created_at = None
        if not hasattr(self, 'page_size'):
            self.page_size = 20
        if not hasattr(self, 'total'):
            self.total = 1

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'customer_id': self.customer_id,
            'opportunity_id': getattr(self, 'opportunity_id', None),
            'type': getattr(self, 'type', 'call'),
            'content': getattr(self, 'content', ''),
            'created_by': getattr(self, 'created_by', 99),
            'created_at': getattr(self, 'created_at', None),
        }


ACTIVITY_ROW = {
    "id": 1,
    "tenant_id": 1,
    "customer_id": 1,
    "opportunity_id": None,
    "type": "call",
    "content": "Discussed product features",
    "created_by": 99,
    "created_at": None,
}


# ---------------------------------------------------------------------------
# _http_status
# ---------------------------------------------------------------------------

class TestHttpStatus:
    def test_success_returns_200(self):
        assert _http_status(ResponseStatus.SUCCESS) == 200

    def test_not_found_returns_404(self):
        assert _http_status(ResponseStatus.NOT_FOUND) == 404

    def test_validation_error_returns_400(self):
        assert _http_status(ResponseStatus.VALIDATION_ERROR) == 400

    def test_unauthorized_returns_401(self):
        assert _http_status(ResponseStatus.UNAUTHORIZED) == 401

    def test_server_error_returns_500(self):
        assert _http_status(ResponseStatus.SERVER_ERROR) == 500

    def test_error_returns_400(self):
        assert _http_status(ResponseStatus.ERROR) == 400

    def test_unknown_status_returns_400(self):
        unknown = MagicMock()
        assert _http_status(unknown) == 400


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_service(monkeypatch):
    from internal.middleware.fastapi_auth import require_auth

    mock_service = MagicMock()
    monkeypatch.setattr(
        "api.routers.activities.ActivityService",
        lambda session: mock_service,
    )

    app = FastAPI()
    app.include_router(activities_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


# ---------------------------------------------------------------------------
# POST /api/v1/activities — create activity
# ---------------------------------------------------------------------------

class TestCreateActivityEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        mock_activity = MockActivity(ACTIVITY_ROW)
        svc.create_activity = AsyncMock(
            return_value=_make_service_response(data=mock_activity, message="活动创建成功")
        )
        resp = client.post(
            "/api/v1/activities",
            json={
                "customer_id": 1,
                "activity_type": "call",
                "content": "Discussed product features",
                "created_by": 99,
                "opportunity_id": None,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["content"] == "Discussed product features"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.create_activity = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR,
                message="客户不存在",
            )
        )
        resp = client.post(
            "/api/v1/activities",
            json={
                "customer_id": 9999,
                "activity_type": "call",
                "content": "Test",
                "created_by": 99,
            },
        )
        assert resp.status_code == 400

    def test_empty_content_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/activities",
            json={
                "customer_id": 1,
                "activity_type": "call",
                "content": "",
                "created_by": 99,
            },
        )
        assert resp.status_code == 422

    def test_empty_type_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/activities",
            json={
                "customer_id": 1,
                "activity_type": "",
                "content": "Some content",
                "created_by": 99,
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/activities/{activity_id} — get activity
# ---------------------------------------------------------------------------

class TestGetActivityEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_activity = MockActivity(ACTIVITY_ROW)
        svc.get_activity = AsyncMock(
            return_value=_make_service_response(data=mock_activity)
        )
        resp = client.get("/api/v1/activities/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_activity = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="活动不存在"
            )
        )
        resp = client.get("/api/v1/activities/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/activities/{activity_id} — update activity
# ---------------------------------------------------------------------------

class TestUpdateActivityEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        updated_row = {**ACTIVITY_ROW, "content": "Updated content"}
        mock_activity = MockActivity(updated_row)
        svc.update_activity = AsyncMock(
            return_value=_make_service_response(data=mock_activity, message="活动更新成功")
        )
        resp = client.put("/api/v1/activities/1", json={"content": "Updated content"})
        assert resp.status_code == 200
        assert resp.json()["data"]["content"] == "Updated content"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_activity = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="活动不存在"
            )
        )
        resp = client.put("/api/v1/activities/9999", json={"content": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/activities/{activity_id} — delete activity
# ---------------------------------------------------------------------------

class TestDeleteActivityEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.delete_activity = AsyncMock(
            return_value=_make_service_response(message="活动删除成功")
        )
        resp = client.delete("/api/v1/activities/1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.delete_activity = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="活动不存在"
            )
        )
        resp = client.delete("/api/v1/activities/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/activities — list activities
# ---------------------------------------------------------------------------

class TestListActivitiesEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_activity = MockActivity(ACTIVITY_ROW)
        mock_list = MagicMock()
        mock_list.items = [mock_activity]
        mock_list.total = 1
        mock_list.page = 1
        mock_list.page_size = 20
        svc.list_activities = AsyncMock(
            return_value=_make_service_response(data=mock_list)
        )
        resp = client.get("/api/v1/activities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.list_activities = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.get("/api/v1/activities")
        assert resp.status_code == 500

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/activities?page_size=101")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/activities/customer/{customer_id} — customer activities
# ---------------------------------------------------------------------------

class TestGetCustomerActivitiesEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_activity = MockActivity(ACTIVITY_ROW)
        svc.get_customer_activities = AsyncMock(
            return_value=_make_service_response(data=[mock_activity])
        )
        resp = client.get("/api/v1/activities/customer/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 1

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.get_customer_activities = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.get("/api/v1/activities/customer/1")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/activities/opportunity/{opp_id} — opportunity activities
# ---------------------------------------------------------------------------

class TestGetOpportunityActivitiesEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_activity = MockActivity(ACTIVITY_ROW)
        svc.get_opportunity_activities = AsyncMock(
            return_value=_make_service_response(data=[mock_activity])
        )
        resp = client.get("/api/v1/activities/opportunity/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 1

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.get_opportunity_activities = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.get("/api/v1/activities/opportunity/1")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/v1/activities/search — search activities
# ---------------------------------------------------------------------------

class TestSearchActivitiesEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_activity = MockActivity(ACTIVITY_ROW)
        svc.search_activities = AsyncMock(
            return_value=_make_service_response(data=[mock_activity])
        )
        resp = client.post(
            "/api/v1/activities/search",
            json={"keyword": "discussed"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]["items"]) == 1

    def test_empty_keyword_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/activities/search",
            json={"keyword": ""},
        )
        assert resp.status_code == 422

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.search_activities = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.post(
            "/api/v1/activities/search",
            json={"keyword": "test"},
        )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/activities/summary — activity summary
# ---------------------------------------------------------------------------

class TestActivitySummaryEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        summary_data = {
            "total": 5,
            "by_type": {"call": 3, "meeting": 2},
            "recent_activities": [],
        }
        svc.get_activity_summary = AsyncMock(
            return_value=_make_service_response(data=summary_data)
        )
        resp = client.get("/api/v1/activities/summary?customer_id=1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 5

    def test_missing_customer_id_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.get("/api/v1/activities/summary")
        assert resp.status_code in (422, 400)

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.get_activity_summary = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.get("/api/v1/activities/summary?customer_id=1")
        assert resp.status_code == 500