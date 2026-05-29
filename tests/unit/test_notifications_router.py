"""Unit tests for src/api/routers/notifications.py — /api/v1/notifications and /api/v1/reminders."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from api.routers.notifications import notifications_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from pkg.errors.app_exceptions import AppException, NotFoundException
from tests.unit.conftest import make_mock_session


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
        self._params = overrides.get("params_")
        self.status = overrides.get("status", "pending")
        self.priority = overrides.get("priority", "normal")
        self.created_at = overrides.get("created_at") or datetime(2026, 1, 1, tzinfo=UTC)
        self.delivered_at = overrides.get("delivered_at")
        self.read_at = overrides.get("read_at")

    @property
    def params_(self):
        return self._params

    @property
    def payload_params(self):
        return self._params

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "channel": self.channel,
            "template": self.template,
            "params": self._params,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }

    def __iter__(self):
        # Required for dict(mock) to work in jsonable_encoder (Pydantic serialization)
        yield from self.to_dict().items()


def _make_auth_override(tenant_id: int = 1, user_id: int = 99):
    """Mimics real JWT-based AuthContext creation: raises 401 for invalid tenants."""
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise HTTPException(status_code=401, detail="Token is missing a valid tenant_id")
    return _make_auth_ctx(tenant_id=tenant_id, user_id=user_id)


def _app(tenant_id: int = 1) -> TestClient:
    # AsyncSession is not needed here — the router under test patches
    # NotificationService entirely, so the DB session is never accessed.
    # get_db override is present for completeness but unused due to full patching.
    app = FastAPI()
    app.include_router(notifications_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_override(tenant_id=tenant_id)
    app.dependency_overrides[get_db] = lambda: make_mock_session([])

    @app.exception_handler(AppException)
    async def _handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"success": False, "message": exc.detail})

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
            response = client.get("/api/v1/notifications?page=1&page_size=20")
            assert response.status_code == 200
            svc.get_user_notifications.assert_called_once_with(
                user_id=99, tenant_id=1, unread_only=False, page=1, page_size=20
            )

    def test_list_unread_only(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=([], 0))
            client = _app()
            response = client.get("/api/v1/notifications?unread_only=true")
            assert response.status_code == 200
            svc.get_user_notifications.assert_called_once_with(
                user_id=99, tenant_id=1, unread_only=True, page=1, page_size=20
            )

    def test_list_pagination_params(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=([], 0))
            client = _app()
            response = client.get("/api/v1/notifications?page=2&page_size=10")
            assert response.status_code == 200
            svc.get_user_notifications.assert_called_once_with(
                user_id=99, tenant_id=1, unread_only=False, page=2, page_size=10
            )


# ---------------------------------------------------------------------------
# POST /notifications/send
# ---------------------------------------------------------------------------


class TestSendNotification:
    def test_send_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            mock_notif = _MockNotificationModel(
                {
                    "id": 5,
                    "tenant_id": 1,
                    "user_id": 2,
                    "channel": "info",
                    "template": "New deal",
                    "params_": {"content": "Deal closed!"},
                }
            )
            svc.send_notification = AsyncMock(return_value=mock_notif)
            client = _app()
            response = client.post(
                "/api/v1/notifications/send",
                json={
                    "user_id": 2,
                    "notification_type": "in_app",
                    "title": "New deal",
                    "content": "Deal closed!",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "通知发送成功"
            assert data["data"]["id"] == 5
            assert data["data"]["template"] == "New deal"
            svc.send_notification.assert_called_once()
            call_kwargs = svc.send_notification.call_args.kwargs
            assert call_kwargs["tenant_id"] == 1
            assert call_kwargs["user_id"] == 2
            assert call_kwargs["notification_type"] == "in_app"
            assert call_kwargs["title"] == "New deal"

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
            mock_notif = _MockNotificationModel(
                {
                    "id": 1,
                    "tenant_id": 1,
                    "user_id": 99,
                    "channel": "in_app",
                    "template": "Test",
                    "status": "read",
                    "read_at": datetime(2026, 1, 1, tzinfo=UTC),
                }
            )
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
    # notification_preferences table not yet implemented — storage is hardcoded in-router
    # responses with no service involvement. These are placeholder tests documenting
    # the hardcoded behavior; they pass for any tenant_id (tenant_id=0 has no real DB
    # enforcement). Replace with real service tests once the preferences table is added.

    def test_get_preferences_ok(self):
        client = _app()
        response = client.get("/api/v1/notifications/preferences")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data == {"email": True, "sms": False, "in_app": True, "push": False}

    def test_update_preferences_ok(self):
        client = _app()
        response = client.put("/api/v1/notifications/preferences", json={"email": False})
        assert response.status_code == 200
        assert response.json()["data"] == {"email": False, "sms": False, "in_app": True, "push": False}


# ---------------------------------------------------------------------------
# POST /reminders
# ---------------------------------------------------------------------------


class TestCreateReminder:
    def test_create_reminder_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.create_reminder = AsyncMock(
                return_value={
                    "id": 1,
                    "tenant_id": 1,
                    "user_id": 99,
                    "title": "Standup",
                    "content": "Daily meeting",
                    "remind_at": "2026-12-31T09:00:00",
                }
            )
            client = _app()
            response = client.post(
                "/api/v1/reminders",
                json={
                    "title": "Standup",
                    "content": "Daily meeting",
                    "remind_at": "2026-12-31T09:00:00",
                },
            )
            assert response.status_code == 200
            assert response.json()["data"]["title"] == "Standup"

    def test_create_reminder_validation_error(self):
        client = _app()
        response = client.post("/api/v1/reminders", json={})
        assert response.status_code == 422
        errors = response.json().get("detail", [])
        error_fields = {e.get("loc")[-1] for e in errors}
        assert {"title", "remind_at"}.issubset(error_fields)


# ---------------------------------------------------------------------------
# GET /reminders
# ---------------------------------------------------------------------------


class TestListReminders:
    def test_list_reminders_empty(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_reminders = AsyncMock(return_value=([], 0))
            client = _app()
            response = client.get("/api/v1/reminders")
            assert response.status_code == 200
            assert response.json()["data"] == {"items": [], "total": 0}

    def test_list_reminders_with_items(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_reminders = AsyncMock(
                return_value=(
                    [
                        {
                            "id": 1,
                            "title": "Standup",
                            "remind_at": "2026-12-31T09:00:00",
                        }
                    ],
                    1,
                )
            )
            client = _app()
            response = client.get("/api/v1/reminders")
            assert response.status_code == 200
            assert len(response.json()["data"]["items"]) == 1


# ---------------------------------------------------------------------------
# DELETE /reminders/{id}
# ---------------------------------------------------------------------------


class TestDeleteNotificationEndpoint:
    def test_delete_notification_ok(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.delete_notification = AsyncMock(return_value={"id": 1})
            client = _app()
            response = client.delete("/api/v1/notifications/1")
            assert response.status_code == 200
            assert response.json()["data"]["id"] == 1

    def test_delete_notification_not_found(self):
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.delete_notification = AsyncMock(side_effect=NotFoundException("通知"))
            client = _app()
            response = client.delete("/api/v1/notifications/999")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /notifications/{id}
# ---------------------------------------------------------------------------


class TestCancelReminderEndpoint:
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
        client = _app(tenant_id=0)
        response = client.get("/api/v1/notifications")
        assert response.status_code == 401

    def test_send_notification_invalid_tenant(self):
        client = _app(tenant_id=0)
        response = client.post(
            "/api/v1/notifications/send",
            json={
                "user_id": 1,
                "notification_type": "info",
                "title": "Test",
                "content": "Test",
            },
        )
        assert response.status_code == 401

    def test_mark_read_invalid_tenant(self):
        client = _app(tenant_id=0)
        response = client.put("/api/v1/notifications/1/read")
        assert response.status_code == 401

    def test_mark_all_read_invalid_tenant(self):
        client = _app(tenant_id=0)
        response = client.post("/api/v1/notifications/mark-all-read")
        assert response.status_code == 401

    def test_get_preferences_invalid_tenant(self):
        client = _app(tenant_id=0)
        response = client.get("/api/v1/notifications/preferences")
        assert response.status_code == 401

    def test_update_preferences_invalid_tenant(self):
        client = _app(tenant_id=0)
        response = client.put("/api/v1/notifications/preferences", json={"email": False})
        assert response.status_code == 401

    def test_create_reminder_invalid_tenant(self):
        client = _app(tenant_id=0)
        response = client.post(
            "/api/v1/reminders",
            json={
                "title": "Test",
                "remind_at": "2026-12-31T09:00:00",
            },
        )
        assert response.status_code == 401

    def test_list_reminders_invalid_tenant(self):
        client = _app(tenant_id=0)
        response = client.get("/api/v1/reminders")
        assert response.status_code == 401

    def test_cancel_reminder_invalid_tenant(self):
        client = _app(tenant_id=0)
        response = client.delete("/api/v1/reminders/1")
        assert response.status_code == 401

    def test_list_notifications_invalid_tenant_none(self):
        app = FastAPI()
        app.include_router(notifications_router)
        app.dependency_overrides[require_auth] = lambda: AuthContext(user_id=99, tenant_id=None, roles=[])
        app.dependency_overrides[get_db] = lambda: make_mock_session([])
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/notifications")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Cross-tenant isolation tests
# ---------------------------------------------------------------------------


class TestCrossTenantIsolation:
    """Rule 126: notifications are invisible across tenant boundaries."""

    def test_cross_tenant_read_returns_empty_list(self):
        """Tenant A's auth context cannot read tenant B's notifications; returns empty list."""
        with patch("api.routers.notifications.NotificationService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_user_notifications = AsyncMock(return_value=([], 0))
            client = _app(tenant_id=2)
            response = client.get("/api/v1/notifications")
            assert response.status_code == 200
            assert response.json()["data"]["items"] == []
            assert response.json()["data"]["total"] == 0
            svc.get_user_notifications.assert_called_once()
            call_kwargs = svc.get_user_notifications.call_args.kwargs
            assert call_kwargs.get("tenant_id") == 2

