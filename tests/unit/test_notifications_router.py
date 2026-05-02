"""Unit tests for src/api/routers/notifications.py — /api/v1/notifications and /api/v1/reminders."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from models.response import ResponseStatus
from api.routers.notifications import notifications_router
from internal.middleware.fastapi_auth import AuthContext, require_auth
from db.connection import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_service_response(status=ResponseStatus.SUCCESS, data=None):
    resp = MagicMock()
    resp.status = status
    resp.data = data
    return resp


def _app():
    app = FastAPI()
    app.include_router(notifications_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------

class TestListNotifications:
    def test_list_notifications_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=MagicMock(
                data=MagicMock(items=[], total=0, page=1, page_size=20, total_pages=1, has_next=False, has_prev=False)
            ))
            client = _app()
            response = client.get("/api/v1/notifications")
            assert response.status_code == 200

    def test_list_unread_only(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=MagicMock(
                data=MagicMock(items=[], total=0, page=1, page_size=20, total_pages=1, has_next=False, has_prev=False)
            ))
            client = _app()
            response = client.get("/api/v1/notifications?unread_only=true")
            assert response.status_code == 200

    def test_list_pagination_params(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=MagicMock(
                data=MagicMock(items=[], total=0, page=2, page_size=10, total_pages=1, has_next=False, has_prev=True)
            ))
            client = _app()
            response = client.get("/api/v1/notifications?page=2&page_size=10")
            assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /notifications/send
# ---------------------------------------------------------------------------

class TestSendNotification:
    def test_send_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.send_notification = AsyncMock(return_value=MagicMock(data={
                "id": 5, "tenant_id": 1, "user_id": 2, "type": "info",
                "title": "New deal", "content": "Deal closed!", "is_read": False,
                "related_type": "opportunity", "related_id": 10, "created_at": "2026-01-01T00:00:00",
            }))
            client = _app()
            response = client.post("/api/v1/notifications/send", json={
                "user_id": 2, "notification_type": "info",
                "title": "New deal", "content": "Deal closed!",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["id"] == 5
            assert data["data"]["title"] == "New deal"

    def test_send_validation_error(self):
        client = _app()
        # missing required fields
        response = client.post("/api/v1/notifications/send", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /notifications/{id}/read
# ---------------------------------------------------------------------------

class TestMarkRead:
    def test_mark_read_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.mark_as_read = AsyncMock(return_value=MagicMock(
                status=ResponseStatus.SUCCESS,
                data={"id": 1, "tenant_id": 1, "user_id": 99, "is_read": True},
            ))
            client = _app()
            response = client.put("/api/v1/notifications/1/read")
            assert response.status_code == 200

    def test_mark_read_not_found(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.mark_as_read = AsyncMock(return_value=MagicMock(status=ResponseStatus.NOT_FOUND))
            client = _app()
            response = client.put("/api/v1/notifications/999/read")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /notifications/mark-all-read
# ---------------------------------------------------------------------------

class TestMarkAllRead:
    def test_mark_all_read_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.mark_all_as_read = AsyncMock(return_value=MagicMock(
                data={"marked_count": 7}, status=ResponseStatus.SUCCESS
            ))
            client = _app()
            response = client.post("/api/v1/notifications/mark-all-read")
            assert response.status_code == 200
            assert response.json()["data"]["marked_count"] == 7


# ---------------------------------------------------------------------------
# GET /notifications/preferences
# ---------------------------------------------------------------------------

class TestPreferences:
    def test_get_preferences_ok(self):
        client = _app()
        response = client.get("/api/v1/notifications/preferences")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "email" in data

    def test_update_preferences_ok(self):
        client = _app()
        response = client.put("/api/v1/notifications/preferences", json={"email": False})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /reminders
# ---------------------------------------------------------------------------

class TestCreateReminder:
    def test_create_reminder_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.create_reminder = AsyncMock(return_value=MagicMock(data={
                "id": 1, "tenant_id": 1, "user_id": 99, "title": "Standup",
                "content": "Daily meeting", "remind_at": "2026-12-31T09:00:00",
                "related_type": None, "related_id": None, "is_completed": False,
                "created_at": "2026-01-01T00:00:00",
            }))
            client = _app()
            response = client.post("/api/v1/reminders", json={
                "title": "Standup",
                "content": "Daily meeting",
                "remind_at": "2026-12-31T09:00:00",
            })
            assert response.status_code == 200
            assert response.json()["data"]["title"] == "Standup"

    def test_create_reminder_validation_error(self):
        client = _app()
        response = client.post("/api/v1/reminders", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /reminders
# ---------------------------------------------------------------------------

class TestListReminders:
    def test_list_reminders_empty(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_reminders = AsyncMock(return_value=[])
            client = _app()
            response = client.get("/api/v1/reminders")
            assert response.status_code == 200
            assert response.json()["data"]["items"] == []

    def test_list_reminders_with_items(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_reminders = AsyncMock(return_value=[{
                "id": 1, "tenant_id": 1, "user_id": 99, "title": "Standup",
                "content": "Daily", "remind_at": "2026-12-31T09:00:00",
                "related_type": None, "related_id": None, "is_completed": False,
                "created_at": "2026-01-01T00:00:00",
            }])
            client = _app()
            response = client.get("/api/v1/reminders")
            assert response.status_code == 200
            assert len(response.json()["data"]["items"]) == 1


# ---------------------------------------------------------------------------
# DELETE /reminders/{id}
# ---------------------------------------------------------------------------

class TestCancelReminder:
    def test_cancel_reminder_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.cancel_reminder = AsyncMock(return_value=MagicMock(
                status=ResponseStatus.SUCCESS, data={"id": 1},
            ))
            client = _app()
            response = client.delete("/api/v1/reminders/1")
            assert response.status_code == 200
            assert response.json()["data"]["id"] == 1

    def test_cancel_reminder_not_found(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.cancel_reminder = AsyncMock(return_value=MagicMock(status=ResponseStatus.NOT_FOUND))
            client = _app()
            response = client.delete("/api/v1/reminders/999")
            assert response.status_code == 404
