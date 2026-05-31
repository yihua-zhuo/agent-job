"""Unit tests for POST /notifications/smart endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from api.routers.notifications import notifications_router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.channel_delivery import ChannelDelivery
from pkg.errors.app_exceptions import AppException
from tests.unit.conftest import make_mock_session


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


class _MockSmartNotificationModel:
    """Minimal mock that behaves like SmartNotificationModel for Pydantic serialization.

    jsonable_encoder calls dict(obj) for non-BaseModel, non-Enum objects.
    Implementing __iter__ to yield (key, value) pairs makes dict(mock) work.
    """

    def __init__(self, overrides: dict | None = None):
        overrides = overrides or {}
        self.id = overrides.get("id", 1)
        self.tenant_id = overrides.get("tenant_id", 1)
        self.summarized_content = overrides.get("summarized_content", "Test content")
        self.priority = overrides.get("priority", 1)
        self.channel = overrides.get("channel", 0)
        self.timing = overrides.get("timing", 0)
        self.recipient_filter = overrides.get("recipient_filter", None)
        self.created_at = overrides.get("created_at") or datetime(2026, 1, 1, tzinfo=UTC)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "summarized_content": self.summarized_content,
            "priority": self.priority,
            "channel": self.channel,
            "timing": self.timing,
            "recipient_filter": self.recipient_filter,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __iter__(self):
        yield from self.to_dict().items()


async def _mock_get_db():
    yield make_mock_session([])


def _make_auth_override(tenant_id: int = 1, user_id: int = 99):
    """Mimics real JWT-based AuthContext creation: raises 401 for invalid tenants."""
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise HTTPException(status_code=401, detail="Token is missing a valid tenant_id")
    return _make_auth_ctx(tenant_id=tenant_id, user_id=user_id)


def _make_test_app(auth_override):
    """Build a FastAPI app with the notifications router and given auth override."""
    app = FastAPI()
    app.include_router(notifications_router)
    app.dependency_overrides[require_auth] = auth_override
    app.dependency_overrides[get_db] = _mock_get_db

    @app.exception_handler(AppException)
    async def _handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"success": False, "message": exc.detail})

    return app


def _app(tenant_id: int = 1) -> TestClient:
    app = _make_test_app(lambda: _make_auth_override(tenant_id=tenant_id))
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /notifications/smart — happy path
# ---------------------------------------------------------------------------


class TestCreateSmartNotification:
    def test_create_smart_notification_ok(self):
        """Valid payload returns 200 with notification and deliveries keys."""
        with (
            patch("api.routers.notifications.NotificationService") as svc_cls,
            patch("api.routers.notifications.NotificationRoutingService") as routing_cls,
        ):
            svc = svc_cls.return_value
            mock_record = _MockSmartNotificationModel({"id": 7, "tenant_id": 1})
            svc.create_smart_notification = AsyncMock(return_value=mock_record)

            routing_svc = routing_cls.return_value
            routing_svc.route = AsyncMock(
                return_value=[
                    ChannelDelivery(
                        channel="in_app",
                        target="99",
                        priority="normal",
                        status="routed",
                        tenant_id=1,
                    ),
                ]
            )

            client = _app()
            response = client.post(
                "/api/v1/notifications/smart",
                json={
                    "summarized_content": "Deal closed for $50k",
                    "priority": 1,
                    "channel": 0,
                    "timing": 0,
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert "notification" in body["data"]
            assert "deliveries" in body["data"]
            assert body["data"]["notification"]["id"] == 7
            assert len(body["data"]["deliveries"]) == 1
            assert body["message"] == "Smart notification created and routed"

            svc.create_smart_notification.assert_called_once()
            call_kwargs = svc.create_smart_notification.call_args.kwargs
            assert call_kwargs["summarized_content"] == "Deal closed for $50k"
            assert call_kwargs["priority"] == 1
            assert call_kwargs["channel"] == 0
            assert call_kwargs["timing"] == 0
            assert call_kwargs["tenant_id"] == 1
            assert call_kwargs["recipient_filter"] is None

            routing_svc.route.assert_called_once()
            route_call = routing_svc.route.call_args
            assert route_call.kwargs["tenant_id"] == 1
            assert route_call.args[0] is mock_record

    def test_create_smart_notification_with_recipient_filter(self):
        """Payload with recipient_filter is passed through to the service."""
        with (
            patch("api.routers.notifications.NotificationService") as svc_cls,
            patch("api.routers.notifications.NotificationRoutingService") as routing_cls,
        ):
            svc = svc_cls.return_value
            mock_record = _MockSmartNotificationModel()
            svc.create_smart_notification = AsyncMock(return_value=mock_record)
            routing_svc = routing_cls.return_value
            routing_svc.route = AsyncMock(return_value=[])

            client = _app()
            response = client.post(
                "/api/v1/notifications/smart",
                json={
                    "summarized_content": "Campaign update",
                    "priority": 2,
                    "channel": 3,
                    "timing": 1,
                    "recipient_filter": {"role": "sales", "region": "west"},
                },
            )
            assert response.status_code == 200
            call_kwargs = svc.create_smart_notification.call_args.kwargs
            assert call_kwargs["recipient_filter"] == {"role": "sales", "region": "west"}


# ---------------------------------------------------------------------------
# POST /notifications/smart — validation errors
# ---------------------------------------------------------------------------


class TestCreateSmartNotificationValidation:
    def test_missing_summarized_content(self):
        """Missing summarized_content returns 422."""
        client = _app()
        response = client.post("/api/v1/notifications/smart", json={"priority": 1, "channel": 0, "timing": 0})
        assert response.status_code == 422
        errors = response.json().get("detail", [])
        error_fields = {e.get("loc")[-1] for e in errors}
        assert "summarized_content" in error_fields

    def test_invalid_priority(self):
        """priority outside {0,1,2} returns 422."""
        client = _app()
        response = client.post(
            "/api/v1/notifications/smart",
            json={
                "summarized_content": "Test",
                "priority": 99,
                "channel": 0,
                "timing": 0,
            },
        )
        assert response.status_code == 422

    def test_invalid_channel(self):
        """channel outside {0,1,2,3} returns 422."""
        client = _app()
        response = client.post(
            "/api/v1/notifications/smart",
            json={
                "summarized_content": "Test",
                "priority": 1,
                "channel": 99,
                "timing": 0,
            },
        )
        assert response.status_code == 422

    def test_empty_summarized_content(self):
        """Empty summarized_content string returns 422."""
        client = _app()
        response = client.post(
            "/api/v1/notifications/smart",
            json={
                "summarized_content": "",
                "priority": 1,
                "channel": 0,
                "timing": 0,
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /notifications/smart — routing integration
# ---------------------------------------------------------------------------


class TestCreateSmartNotificationRouting:
    def test_routing_returns_empty_deliveries(self):
        """priority=normal with no user_id returns200 with empty deliveries list."""
        with (
            patch("api.routers.notifications.NotificationService") as svc_cls,
            patch("api.routers.notifications.NotificationRoutingService") as routing_cls,
        ):
            svc = svc_cls.return_value
            mock_record = _MockSmartNotificationModel({"priority": 1})
            svc.create_smart_notification = AsyncMock(return_value=mock_record)

            routing_svc = routing_cls.return_value
            routing_svc.route = AsyncMock(return_value=[])

            client = _app()
            response = client.post(
                "/api/v1/notifications/smart",
                json={
                    "summarized_content": "Update",
                    "priority": 1,
                    "channel": 0,
                    "timing": 0,
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["data"]["deliveries"] == []


# ---------------------------------------------------------------------------
# POST /notifications/smart — tenant isolation
# ---------------------------------------------------------------------------


class TestCreateSmartNotificationTenantIsolation:
    def _app_invalid_tenant(self) -> TestClient:
        app = _make_test_app(lambda: _make_auth_ctx(tenant_id=0, user_id=99))
        return TestClient(app, raise_server_exceptions=False)

    def test_invalid_tenant_returns_401(self):
        """tenant_id=0 returns 401."""
        client = self._app_invalid_tenant()
        response = client.post(
            "/api/v1/notifications/smart",
            json={
                "summarized_content": "Test",
                "priority": 1,
                "channel": 0,
                "timing": 0,
            },
        )
        assert response.status_code == 401
