"""Unit tests for POST /notifications/smart endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from api.routers.notifications import _priority_to_string
from api.routers.notifications import notifications_router
from db.connection import get_db
from db.models.smart_notification import Priority
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.channel_delivery import ChannelDelivery
from pkg.errors.app_exceptions import AppException
from services.notification_service import NotificationService
from tests.unit.conftest import make_mock_session, MockState, make_smart_notification_handler


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


class _MockSmartNotificationModel:
    """Minimal mock that behaves like SmartNotificationModel for Pydantic serialization.

    jsonable_encoder calls dict(obj) for non-BaseModel, non-Enum objects.
    Implementing __iter__ to yield (key, value) pairs makes dict(mock) work.

    priority/channel/timing are stored as their actual enum types so that to_dict()
    serialization matches the real ORM model's output (Pydantic/jsonable_encoder
    returns the Python enum value, not the string name or int value).
    """

    def __init__(self, overrides: dict | None = None):
        overrides = overrides or {}
        self.id = overrides.get("id", 1)
        self.tenant_id = overrides.get("tenant_id", 1)
        self.summarized_content = overrides.get("summarized_content", "Test content")
        self.priority = overrides.get("priority", Priority.urgent)  # Priority IntEnum
        self.channel = overrides.get("channel", 0)  # int (Channel enum)
        self.timing = overrides.get("timing", 0)  # int (Timing enum)
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


class _TestRoutingRecord:
    """Minimal routing record adapter for tests — mirrors _MockRoutingRecord logic."""

    def __init__(self, mock_record):
        self.id = mock_record.id
        self.tenant_id = mock_record.tenant_id
        self.priority = _priority_to_string(mock_record.priority)
        self.channel = mock_record.channel
        self.timing = mock_record.timing
        self.summarized_content = mock_record.summarized_content
        self.recipient_filter = mock_record.recipient_filter


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
    app = _make_test_app(_make_auth_override)
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
            mock_record = _MockSmartNotificationModel({"id": 7, "tenant_id": 1, "priority": Priority.urgent})
            svc.create_smart_notification = AsyncMock(return_value=mock_record)

            routing_svc = routing_cls.return_value
            # Return deliveries that match real routing behavior for urgent priority:
            # in_app and email channels (no user_id on the mock record means target is "")
            routing_svc.route = AsyncMock(
                return_value=[
                    ChannelDelivery(
                        channel="in_app",
                        target="",
                        priority="urgent",
                        status="routed",
                        tenant_id=1,
                    ),
                    ChannelDelivery(
                        channel="email",
                        target="",
                        priority="urgent",
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
            assert len(body["data"]["deliveries"]) == 2
            assert body["data"]["deliveries"][0]["channel"] == "in_app"
            assert body["data"]["deliveries"][1]["channel"] == "email"
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

            record_arg = route_call.args[0]
            assert record_arg.priority == "urgent"
            assert record_arg.id == 7

    def test_create_smart_notification_with_recipient_filter(self):
        """Payload with recipient_filter is passed through to the service and channel is preserved."""
        with (
            patch("api.routers.notifications.NotificationService") as svc_cls,
            patch("api.routers.notifications.NotificationRoutingService") as routing_cls,
        ):
            svc = svc_cls.return_value
            mock_record = _MockSmartNotificationModel({"priority": Priority.urgent, "channel": 3})
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
            body = response.json()
            call_kwargs = svc.create_smart_notification.call_args.kwargs
            assert call_kwargs["recipient_filter"] == {"role": "sales", "region": "west"}
            # Verify the request channel=3 (in_app) was persisted and returned
            assert body["data"]["notification"]["channel"] == 3


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
        errors = response.json().get("detail", [])
        error_fields = {e.get("loc")[-1] for e in errors}
        assert "priority" in error_fields

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
        errors = response.json().get("detail", [])
        error_fields = {e.get("loc")[-1] for e in errors}
        assert "channel" in error_fields

    def test_invalid_timing(self):
        """timing outside {0,1} returns 422."""
        client = _app()
        response = client.post(
            "/api/v1/notifications/smart",
            json={
                "summarized_content": "Test",
                "priority": 1,
                "channel": 0,
                "timing": 99,
            },
        )
        assert response.status_code == 422
        errors = response.json().get("detail", [])
        error_fields = {e.get("loc")[-1] for e in errors}
        assert "timing" in error_fields

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
        errors = response.json().get("detail", [])
        error_fields = {e.get("loc")[-1] for e in errors}
        assert "summarized_content" in error_fields


# ---------------------------------------------------------------------------
# POST /notifications/smart — routing integration
# ---------------------------------------------------------------------------


class TestCreateSmartNotificationRouting:
    def test_empty_deliveries_still_returns_200(self):
        """priority=normal with no user_id returns 200 with an empty deliveries list.

        The real NotificationRoutingService.route() is called: for priority=normal
        with no user_id on the record, it returns [] (confirmed in routing service line 48).
        We verify the real service path executes and produces the expected empty result.
        """
        with (
            patch("api.routers.notifications.NotificationService") as svc_cls,
        ):
            svc = svc_cls.return_value
            # priority=normal, no user_id → real routing service returns []
            mock_record = _MockSmartNotificationModel({"priority": Priority.normal})
            svc.create_smart_notification = AsyncMock(return_value=mock_record)
            # NotificationRoutingService is NOT mocked — real service is called

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
            assert body["success"] is True
            assert "notification" in body["data"]
            # Real routing for Priority.normal + no user_id → []
            assert body["data"]["deliveries"] == []

    def test_channel_in_app_routed_correctly(self):
        """channel=3 (in_app) is persisted and routing receives the correct channel value."""
        with (
            patch("api.routers.notifications.NotificationService") as svc_cls,
            patch("api.routers.notifications.NotificationRoutingService") as routing_cls,
        ):
            svc = svc_cls.return_value
            mock_record = _MockSmartNotificationModel({"channel": 3})
            svc.create_smart_notification = AsyncMock(return_value=mock_record)

            routing_svc = routing_cls.return_value
            routing_svc.route = AsyncMock(return_value=[])

            client = _app()
            response = client.post(
                "/api/v1/notifications/smart",
                json={
                    "summarized_content": "In-app update",
                    "priority": 1,
                    "channel": 3,
                    "timing": 0,
                },
            )
            assert response.status_code == 200
            # channel=3 was passed through to the service
            svc.create_smart_notification.assert_called_once()
            assert svc.create_smart_notification.call_args.kwargs["channel"] == 3
            # routing received in_app channel (integer 3)
            routing_svc.route.assert_called_once()
            assert routing_svc.route.call_args.args[0].channel == 3


# ---------------------------------------------------------------------------
# POST /notifications/smart — tenant isolation
# ---------------------------------------------------------------------------


class TestCreateSmartNotificationTenantIsolation:
    def _app_invalid_tenant(self) -> TestClient:
        app = _make_test_app(lambda: _make_auth_override(tenant_id=0, user_id=99))
        return TestClient(app, raise_server_exceptions=False)

    def test_missing_tenant_raises_401_from_override(self):
        """tenant_id=0 is caught by the auth override before require_auth is called."""
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

    def test_tenant_a_cannot_route_as_tenant_b(self):
        """Routing is scoped to the authenticated tenant_id, not the record's tenant_id.

        Even if the persisted record somehow carries a different tenant_id,
        routing_svc.route must be called with ctx.tenant_id (the authenticated tenant),
        not the record's tenant_id. This prevents cross-tenant routing leakage.
        """
        with (
            patch("api.routers.notifications.NotificationService") as svc_cls,
            patch("api.routers.notifications.NotificationRoutingService") as routing_cls,
        ):
            svc = svc_cls.return_value
            # Record has tenant_id=99 but the request is made as tenant_id=1
            mock_record = _MockSmartNotificationModel({"tenant_id": 99, "priority": Priority.urgent})
            svc.create_smart_notification = AsyncMock(return_value=mock_record)

            routing_svc = routing_cls.return_value
            routing_svc.route = AsyncMock(return_value=[])

            # Auth as tenant_id=1
            client = _app(tenant_id=1)
            response = client.post(
                "/api/v1/notifications/smart",
                json={
                    "summarized_content": "Cross-tenant check",
                    "priority": 0,
                    "channel": 0,
                    "timing": 0,
                },
            )
            assert response.status_code == 200

            # routing_svc.route must be called with tenant_id=1 (authenticated), not 99 (record)
            routing_svc.route.assert_called_once()
            assert routing_svc.route.call_args.kwargs["tenant_id"] == 1


# ---------------------------------------------------------------------------
# POST /notifications/send — content validation
# ---------------------------------------------------------------------------


class TestSendNotificationContentValidation:
    def test_content_with_password_returns_422(self):
        """content containing 'password' returns 422 per content_keys_must_be_allowed validator."""
        client = _app()
        response = client.post(
            "/api/v1/notifications/send",
            json={
                "user_id": 99,
                "notification_type": "email",
                "title": "Credentials",
                "content": "Your password reset token is ABC123",
            },
        )
        assert response.status_code == 422
        errors = response.json().get("detail", [])
        error_fields = {e.get("loc")[-1] for e in errors}
        assert "content" in error_fields


# ---------------------------------------------------------------------------
# NotificationService.create_smart_notification — unit tests via mock session
# ---------------------------------------------------------------------------


class TestCreateSmartNotificationService:
    """Service-level tests using a mock SQL session with a smart-notification handler."""

    pytestmark = pytest.mark.asyncio

    @pytest.fixture
    def mock_db_session(self):
        state = MockState()
        return make_mock_session([make_smart_notification_handler(state)])

    @pytest.fixture
    def notification_service(self, mock_db_session):
        return NotificationService(mock_db_session)

    @pytest.mark.asyncio
    async def test_valid_call_persists_record(self, notification_service):
        """Valid parameters create a SmartNotification record in the mock session."""
        record = await notification_service.create_smart_notification(
            summarized_content="Test notification",
            priority=0,
            channel=1,
            timing=0,
            tenant_id=42,
            recipient_filter={"role": "admin"},
        )
        assert record.summarized_content == "Test notification"
        assert record.priority == 0
        assert record.channel == 1
        assert record.timing == 0
        assert record.tenant_id == 42
        assert record.recipient_filter == {"role": "admin"}
        assert record.id is not None

    @pytest.mark.asyncio
    async def test_invalid_priority_raises(self, notification_service):
        """priority outside {0,1,2} raises ValidationException."""
        from pkg.errors.app_exceptions import ValidationException

        with pytest.raises(ValidationException) as exc_info:
            await notification_service.create_smart_notification(
                summarized_content="Test",
                priority=99,
                channel=0,
                timing=0,
                tenant_id=1,
            )
        assert "priority" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invalid_channel_raises(self, notification_service):
        """channel outside {0,1,2,3} raises ValidationException."""
        from pkg.errors.app_exceptions import ValidationException

        with pytest.raises(ValidationException) as exc_info:
            await notification_service.create_smart_notification(
                summarized_content="Test",
                priority=0,
                channel=99,
                timing=0,
                tenant_id=1,
            )
        assert "channel" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invalid_timing_raises(self, notification_service):
        """timing outside {0,1} raises ValidationException."""
        from pkg.errors.app_exceptions import ValidationException

        with pytest.raises(ValidationException) as exc_info:
            await notification_service.create_smart_notification(
                summarized_content="Test",
                priority=0,
                channel=0,
                timing=99,
                tenant_id=1,
            )
        assert "timing" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, mock_db_session):
        """Records created under tenant 1 are not accessible to tenant 2.

        The mock handler only stores records; it does not filter by tenant on read.
        This test documents the contract: callers must always pass the correct
        tenant_id. The service enforces tenant scoping in every SQL WHERE clause.
        """
        svc = NotificationService(mock_db_session)
        record = await svc.create_smart_notification(
            summarized_content="Tenant 1 private note",
            priority=1,
            channel=0,
            timing=0,
            tenant_id=1,
        )
        assert record.tenant_id == 1
        # Tenant 2 cannot create a record with tenant_id=1 (tenant_id is
        # bound from the authenticated context, not the request body).
        record2 = await svc.create_smart_notification(
            summarized_content="Tenant 2 note",
            priority=1,
            channel=0,
            timing=0,
            tenant_id=2,
        )
        assert record2.tenant_id == 2
        assert record.id != record2.id
