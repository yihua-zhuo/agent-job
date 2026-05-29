"""Unit tests for src/api/routers/notifications.py — /api/v1/notifications and /api/v1/reminders."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from api.routers.notifications import notifications_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException, NotFoundException


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


class _MockNotificationModel:
    """Minimal mock that behaves like NotificationModel for Pydantic serialization.

    jsonable_encoder calls dict(obj) for non-BaseModel, non-Enum objects.
    Implementing __iter__ to yield (key, value) pairs makes dict(mock) work.
    """

    def __init__(self, overrides: dict):
        self.id = overrides.get("id", 1)
        self.tenant_id = overrides.get("tenant_id", 1)
        self.user_id = overrides.get("user_id", 99)
        self.channel = overrides.get("channel", "in_app")
        self.template = overrides.get("template", "Test")
        self._params_raw = overrides.get("params_", None)
        self.status = overrides.get("status", "pending")
        self.priority = overrides.get("priority", "normal")
        self.created_at = overrides.get("created_at") or datetime(2026, 1, 1, tzinfo=UTC)
        self.delivered_at = overrides.get("delivered_at")
        self.read_at = overrides.get("read_at")

    @property
    def params_(self):
        return self._params_raw

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "channel": self.channel,
            "template": self.template,
            "params": self._params_raw,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }

    def __iter__(self):
        # Required for dict(mock) to work in jsonable_encoder (Pydantic serialization)
        yield from self.to_dict().items()


def _app():
    app = FastAPI()
    app.include_router(notifications_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(AppException)
    async def _handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"success": False, "message": exc.detail})

    return TestClient(app, raise_server_exceptions=False)


def _app_invalid_tenant(tenant_id: int = 0):
    app = FastAPI()
    app.include_router(notifications_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx(tenant_id=tenant_id)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------

class TestListNotifications:
    def test_list_notifications_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=([], 0))
            client = _app()
            response = client.get("/api/v1/notifications")
            assert response.status_code == 200

    def test_list_unread_only(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=([], 0))
            client = _app()
            response = client.get("/api/v1/notifications?unread_only=true")
            assert response.status_code == 200

    def test_list_pagination_params(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=([], 0))
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
            mock_notif = _MockNotificationModel({
                "id": 5, "tenant_id": 1, "user_id": 2,
                "channel": "info", "template": "New deal",
                "params_": {"content": "Deal closed!"},
            })
            svc.send_notification = AsyncMock(return_value=mock_notif)
            client = _app()
            response = client.post("/api/v1/notifications/send", json={
                "user_id": 2, "notification_type": "info",
                "title": "New deal", "content": "Deal closed!",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["id"] == 5
            assert data["data"]["template"] == "New deal"

    def test_send_validation_error(self):
        client = _app()
        response = client.post("/api/v1/notifications/send", json={})
        assert response.status_code == 422
        errors = response.json().get("detail", [])
        error_fields = {e.get("loc")[-1] for e in errors}
        assert error_fields == {"user_id", "notification_type", "title", "content"}


# ---------------------------------------------------------------------------
# PUT /notifications/{id}/read
# ---------------------------------------------------------------------------

class TestMarkRead:
    def test_mark_read_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            mock_notif = _MockNotificationModel({
                "id": 1, "tenant_id": 1, "user_id": 99,
                "channel": "in_app", "template": "Test",
                "status": "read",
                "read_at": datetime(2026, 1, 1, tzinfo=UTC),
            })
            svc.mark_as_read = AsyncMock(return_value=mock_notif)
            client = _app()
            response = client.put("/api/v1/notifications/1/read")
            assert response.status_code == 200

    def test_mark_read_not_found(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.mark_as_read = AsyncMock(side_effect=NotFoundException("通知"))
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
            svc.mark_all_as_read = AsyncMock(return_value={"marked_count": 7})
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
            svc.create_reminder = AsyncMock(return_value={
                "id": 1, "tenant_id": 1, "user_id": 99, "title": "Standup",
                "content": "Daily meeting", "remind_at": "2026-12-31T09:00:00",
            })
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
            assert response.json()["data"] == []

    def test_list_reminders_with_items(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_reminders = AsyncMock(return_value=[{
                "id": 1, "title": "Standup", "remind_at": "2026-12-31T09:00:00",
            }])
            client = _app()
            response = client.get("/api/v1/reminders")
            assert response.status_code == 200
            assert len(response.json()["data"]) == 1


# ---------------------------------------------------------------------------
# DELETE /reminders/{id}
# ---------------------------------------------------------------------------

class TestCancelReminder:
    def test_cancel_reminder_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.cancel_reminder = AsyncMock(return_value={"id": 1})
            client = _app()
            response = client.delete("/api/v1/reminders/1")
            assert response.status_code == 200
            assert response.json()["data"]["id"] == 1

    def test_cancel_reminder_not_found(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.cancel_reminder = AsyncMock(side_effect=NotFoundException("提醒"))
            client = _app()
            response = client.delete("/api/v1/reminders/999")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# Invalid tenant tests
# ---------------------------------------------------------------------------

class TestInvalidTenant:
    def test_list_notifications_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.get("/api/v1/notifications")
        assert response.status_code == 401

    def test_send_notification_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.post("/api/v1/notifications/send", json={
            "user_id": 1, "notification_type": "info",
            "title": "Test", "content": "Test",
        })
        assert response.status_code == 401

    def test_mark_read_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.put("/api/v1/notifications/1/read")
        assert response.status_code == 401

    def test_mark_all_read_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.post("/api/v1/notifications/mark-all-read")
        assert response.status_code == 401

    def test_get_preferences_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.get("/api/v1/notifications/preferences")
        assert response.status_code == 401

    def test_update_preferences_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.put("/api/v1/notifications/preferences", json={"email": False})
        assert response.status_code == 401

    def test_create_reminder_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.post("/api/v1/reminders", json={
            "title": "Test", "remind_at": "2026-12-31T09:00:00",
        })
        assert response.status_code == 401

    def test_list_reminders_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.get("/api/v1/reminders")
        assert response.status_code == 401

    def test_cancel_reminder_invalid_tenant(self):
        client = _app_invalid_tenant(tenant_id=0)
        response = client.delete("/api/v1/reminders/1")
        assert response.status_code == 401

    def test_list_notifications_invalid_tenant_none(self):
        app = FastAPI()
        app.include_router(notifications_router)
        app.dependency_overrides[require_auth] = lambda: AuthContext(user_id=99, tenant_id=None, roles=[])
        app.dependency_overrides[get_db] = lambda: MagicMock()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/notifications")
        assert response.status_code == 401
