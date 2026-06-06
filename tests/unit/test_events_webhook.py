"""Unit tests for src/api/routers/events.py — tests for the events webhook router and EventService validation path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.routers.events import router
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.score import ScoreTier
from pkg.errors.app_exceptions import AppException, ValidationException
from services.event_service import VALID_EVENT_TYPES


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


def _make_score_result(score: int = 75, tier: ScoreTier = ScoreTier.B):
    result = MagicMock()
    result.score = score
    result.tier = tier
    result.tier_label = tier.value
    return result


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def app_with_overrides(monkeypatch, mock_db_session):
    """Build a FastAPI app with the events router and override auth/db deps.

    This is a router-level delegation test — the EventService and ScoreService
    classes are patched at the router module level with thin lambdas so we
    exercise the router wiring only. The services' own SQL is covered by
    integration tests.
    """
    mock_event = MagicMock()
    mock_event.record_engagement_event = AsyncMock()

    mock_score = MagicMock()
    mock_score.calculate_score = AsyncMock(return_value=_make_score_result())

    monkeypatch.setattr("api.routers.events.EventService", lambda session: mock_event)
    monkeypatch.setattr("api.routers.events.ScoreService", lambda session: mock_score)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_db_session

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_event, mock_score


class TestEngagementWebhook:
    """Tests for POST /events/engagement."""

    def test_valid_engagement_returns_envelope(self, app_with_overrides):
        """POST /engagement with valid body returns 200 and recalculated score/tier."""
        client, mock_event, mock_score = app_with_overrides

        response = client.post(
            "/api/v1/events/engagement",
            json={"customer_id": 1, "event_type": "email_open", "event_metadata": {"campaign": "spring"}},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["data"]["customer_id"] == 1
        assert body["data"]["score"] == 75
        assert body["data"]["tier"] == "B"

    def test_valid_engagement_calls_event_service(self, app_with_overrides):
        """EventService.record_engagement_event is awaited once with the request payload."""
        client, mock_event, mock_score = app_with_overrides

        client.post(
            "/api/v1/events/engagement",
            json={"customer_id": 42, "event_type": "website_visit"},
        )

        mock_event.record_engagement_event.assert_awaited_once()
        call_kwargs = mock_event.record_engagement_event.call_args.kwargs
        assert call_kwargs["tenant_id"] == 1
        assert call_kwargs["customer_id"] == 42
        assert call_kwargs["event_type"] == "website_visit"
        # event_metadata was not provided — defaults to None (EventService handles None)
        assert call_kwargs["metadata"] is None

    def test_valid_engagement_triggers_score_recalculation(self, app_with_overrides):
        """ScoreService.calculate_score is awaited exactly once after the event is recorded."""
        client, mock_event, mock_score = app_with_overrides

        client.post(
            "/api/v1/events/engagement",
            json={"customer_id": 7, "event_type": "email_open"},
        )

        mock_score.calculate_score.assert_awaited_once_with(
            customer_id=7,
            tenant_id=1,
        )

    def test_event_recorded_before_score_calculation(self, app_with_overrides):
        """EventService.record_engagement_event is called before ScoreService.calculate_score."""
        client, mock_event, mock_score = app_with_overrides
        call_order: list[str] = []

        async def _record(*args, **kwargs):
            call_order.append("record")

        async def _calc(*args, **kwargs):
            call_order.append("calc")
            return _make_score_result()

        mock_event.record_engagement_event = AsyncMock(side_effect=_record)
        mock_score.calculate_score = AsyncMock(side_effect=_calc)

        response = client.post(
            "/api/v1/events/engagement",
            json={"customer_id": 1, "event_type": "email_open"},
        )

        assert response.status_code == 200
        assert call_order == ["record", "calc"]

    def test_invalid_event_type_returns_422(self, app_with_overrides):
        """POST /engagement with an invalid event_type returns 422 (Pydantic validation)."""
        client, mock_event, mock_score = app_with_overrides

        response = client.post(
            "/api/v1/events/engagement",
            json={"customer_id": 1, "event_type": "not_a_real_event"},
        )

        assert response.status_code == 422, response.text
        # Pydantic 422 returns FastAPI's default validation error shape with "detail"
        body = response.json()
        assert "detail" in body or "message" in body
        # Neither service should be called when Pydantic validation fails
        mock_event.record_engagement_event.assert_not_called()
        mock_score.calculate_score.assert_not_called()

    def test_missing_customer_id_returns_422(self, app_with_overrides):
        """POST /engagement with missing customer_id returns 422 (Pydantic validation)."""
        client, mock_event, _ = app_with_overrides

        response = client.post(
            "/api/v1/events/engagement",
            json={"event_type": "email_open"},
        )

        assert response.status_code == 422, response.text
        mock_event.record_engagement_event.assert_not_called()

    @pytest.mark.parametrize("bad_id", [0, -1, -999])
    def test_non_positive_customer_id_returns_422(self, app_with_overrides, bad_id):
        """POST /engagement with customer_id <= 0 (boundary: 0, -1, -999) returns 422."""
        client, mock_event, _ = app_with_overrides

        response = client.post(
            "/api/v1/events/engagement",
            json={"customer_id": bad_id, "event_type": "email_open"},
        )

        assert response.status_code == 422, response.text
        mock_event.record_engagement_event.assert_not_called()


class TestEventServiceValidation:
    """Unit tests for the standalone EventService.record_engagement_event validation path."""

    @pytest.mark.asyncio
    async def test_record_engagement_event_invalid_type_raises(self):
        """EventService raises ValidationException for event_type not in the allowlist."""
        from services.event_service import EventService

        # validation path does not touch the DB; MagicMock is safe here
        svc = EventService(MagicMock())
        with pytest.raises(ValidationException, match="event_type must be one of"):
            await svc.record_engagement_event(tenant_id=1, customer_id=1, event_type="bogus")

    @pytest.mark.asyncio
    async def test_valid_event_types_accepted(self):
        """All event types in VALID_EVENT_TYPES are accepted by the service (exact equality)."""
        from services.event_service import EventService

        assert set(VALID_EVENT_TYPES) == {"email_open", "website_visit"}

        for event_type in VALID_EVENT_TYPES:
            session = MagicMock()
            session.add = MagicMock()
            session.flush = AsyncMock()
            session.refresh = AsyncMock()
            # Customer existence check returns a row -> customer exists -> insert proceeds
            existence_result = MagicMock()
            existence_result.scalar_one_or_none.return_value = 1
            session.execute = AsyncMock(return_value=existence_result)
            svc = EventService(session)
            await svc.record_engagement_event(
                tenant_id=1,
                customer_id=1,
                event_type=event_type,
            )
            session.add.assert_called_once()
