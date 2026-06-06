"""Unit tests for src/api/routers/customers.py — router endpoint tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.customers import (
    _is_valid_email,
    _sanitize,
    customers_router,
)
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext
from pkg.errors.app_exceptions import AppException, NotFoundException, ValidationException

# ---------------------------------------------------------------------------
# Helpers: build a minimal FastAPI app with overridden deps for each test
# ---------------------------------------------------------------------------


def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


# ---------------------------------------------------------------------------
# _sanitize
# ---------------------------------------------------------------------------


class TestSanitize:
    def test_strips_html_tags(self):
        assert _sanitize("<b>hello</b>") == "hello"

    def test_strips_nested_tags(self):
        assert _sanitize("<script>alert(1)</script>text") == "text"

    def test_removes_control_chars(self):
        result = _sanitize("hello\x00world")
        assert "\x00" not in result

    def test_strips_whitespace(self):
        assert _sanitize("  hello  ") == "hello"

    def test_empty_string_passthrough(self):
        assert _sanitize("") == ""

    def test_none_passthrough(self):
        assert _sanitize(None) is None

    def test_normal_string_unchanged(self):
        assert _sanitize("john doe") == "john doe"


# ---------------------------------------------------------------------------
# _is_valid_email
# ---------------------------------------------------------------------------


class TestIsValidEmail:
    def test_valid_email(self):
        assert _is_valid_email("user@example.com") is True

    def test_valid_email_with_plus(self):
        assert _is_valid_email("user+tag@domain.co.uk") is True

    def test_missing_at_sign(self):
        assert _is_valid_email("userexample.com") is False

    def test_missing_domain(self):
        assert _is_valid_email("user@") is False

    def test_invalid_tld_too_short(self):
        assert _is_valid_email("user@domain.c") is False

    def test_empty_string(self):
        assert _is_valid_email("") is False


# ---------------------------------------------------------------------------
# Router endpoint tests using TestClient with mocked CustomerService
# ---------------------------------------------------------------------------


def _mock_to_dict(data):
    m = MagicMock()
    m.to_dict = MagicMock(return_value=data)
    return m


CUSTOMER_ROW = {
    "id": 1,
    "tenant_id": 1,
    "name": "Alice",
    "email": "alice@example.com",
    "phone": "555",
    "company": "ACME",
    "status": "lead",
    "owner_id": 1,
    "tags": [],
    "created_at": None,
    "updated_at": None,
}


@pytest.fixture
def client_with_service(monkeypatch):
    """Return a TestClient with CustomerService fully mocked."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from internal.middleware.fastapi_auth import require_auth

    # Create mock eagerly so the fixture can return it before any request is made.
    # Each test gets its own fresh mock (no module-level singleton = no cross-test pollution).
    _mock = MagicMock()
    _repo_sessions = []

    def override_customer_service(repository):
        return _mock

    # Async-aware mock session for session.execute() calls (enrichment queries)
    mock_session = MagicMock()
    mock_enrich_result = MagicMock()
    mock_enrich_result.all = MagicMock(return_value=[])
    mock_enrich_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_enrich_result)

    app = FastAPI()
    app.include_router(customers_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_session

    # Patch CustomerService in the router's module namespace so the
    # router uses mock_service directly instead of instantiating the real class.
    monkeypatch.setattr(
        "api.routers.customers.CustomerService",
        override_customer_service,
    )

    # Mock CustomerRepository so that CustomerRepository(session) in the router
    # returns a mock whose .session attribute is the mock_session we control.
    # Track every session argument so tests can assert the right one was used.
    def make_mock_repo(session):
        _repo_sessions.append(session)
        return MagicMock(session=session)

    monkeypatch.setattr(
        "api.routers.customers.CustomerRepository",
        make_mock_repo,
    )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, _mock, _repo_sessions


class TestCreateCustomerEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc, _ = client_with_service
        svc.create_customer = AsyncMock(return_value=_mock_to_dict({"name": "Alice"}))
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "email": "alice@example.com", "owner_id": 1},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Alice"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc, _ = client_with_service
        svc.create_customer = AsyncMock(side_effect=ValidationException("Invalid data"))
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "owner_id": 1},
        )
        assert resp.status_code == 422

    def test_invalid_email_rejected_by_validator(self, client_with_service):
        client, svc, _ = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Alice", "email": "not-an-email", "owner_id": 1},
        )
        assert resp.status_code == 422

    def test_empty_name_rejected(self, client_with_service):
        client, svc, _ = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "   ", "owner_id": 1},
        )
        assert resp.status_code == 422

    def test_invalid_status_rejected(self, client_with_service):
        client, svc, _ = client_with_service
        resp = client.post(
            "/api/v1/customers",
            json={"name": "Bob", "status": "invalid", "owner_id": 1},
        )
        assert resp.status_code == 422


class TestListCustomersEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.list_customers = AsyncMock(return_value=([_mock_to_dict(CUSTOMER_ROW)], 1))
        resp = client.get("/api/v1/customers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert len(body["data"]["items"]) == 1

    def test_with_pagination_params(self, client_with_service):
        client, svc, _ = client_with_service
        svc.list_customers = AsyncMock(return_value=([_mock_to_dict(CUSTOMER_ROW)], 10))
        resp = client.get("/api/v1/customers?page=2&page_size=5")
        assert resp.status_code == 200
        assert resp.json()["data"]["page"] == 2

    def test_page_size_over_100_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.get("/api/v1/customers?page_size=101")
        assert resp.status_code == 422


class TestSearchCustomersEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.search_customers = AsyncMock(return_value=[_mock_to_dict(CUSTOMER_ROW)])
        resp = client.get("/api/v1/customers/search?keyword=alice")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["keyword"] == "alice"
        assert len(body["data"]["items"]) == 1

    def test_empty_keyword(self, client_with_service):
        client, svc, _ = client_with_service
        svc.search_customers = AsyncMock(return_value=[])
        resp = client.get("/api/v1/customers/search")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

    def test_keyword_too_long_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.get(f"/api/v1/customers/search?keyword={'x' * 201}")
        assert resp.status_code == 422

    def test_sanitize_strips_html_from_keyword(self, client_with_service):
        client, svc, _ = client_with_service
        svc.search_customers = AsyncMock(return_value=[])
        client.get("/api/v1/customers/search?keyword=<script>alert(1)</script>")
        svc.search_customers.assert_called_once()
        call_args = svc.search_customers.call_args
        # The sanitized keyword should have HTML stripped (empty string —
        # _sanitize removes the entire <script>...</script> as a matched pair)
        assert call_args[0][0] == "", f"Expected empty string after HTML strip, got {call_args[0][0]!r}"

    def test_keyword_exactly_200_chars_accepted(self, client_with_service):
        client, svc, _ = client_with_service
        svc.search_customers = AsyncMock(return_value=[])
        resp = client.get(f"/api/v1/customers/search?keyword={'y' * 200}")
        assert resp.status_code == 200


class TestGetCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.get_customer = AsyncMock(return_value=_mock_to_dict(CUSTOMER_ROW))
        resp = client.get("/api/v1/customers/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.get_customer = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.get("/api/v1/customers/9999")
        assert resp.status_code == 404


class TestUpdateCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.update_customer = AsyncMock(return_value=_mock_to_dict({**CUSTOMER_ROW, "name": "Updated"}))
        resp = client.put("/api/v1/customers/1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.update_customer = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.put("/api/v1/customers/9999", json={"name": "X"})
        assert resp.status_code == 404


class TestDeleteCustomerEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.delete_customer = AsyncMock(return_value=_mock_to_dict(CUSTOMER_ROW))
        resp = client.delete("/api/v1/customers/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.delete_customer = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.delete("/api/v1/customers/9999")
        assert resp.status_code == 404


class TestAddTagEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.add_tag = AsyncMock(return_value=_mock_to_dict({"id": 1, "tag": "vip"}))
        resp = client.post("/api/v1/customers/1/tags", json={"tag": "vip"})
        assert resp.status_code == 200
        assert resp.json()["data"]["tag"] == "vip"

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.add_tag = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.post("/api/v1/customers/9999/tags", json={"tag": "vip"})
        assert resp.status_code == 404

    def test_empty_tag_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.post("/api/v1/customers/1/tags", json={"tag": ""})
        assert resp.status_code == 422


class TestRemoveTagEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.remove_tag = AsyncMock(return_value=_mock_to_dict({"id": 1, "tag": "vip"}))
        resp = client.delete("/api/v1/customers/1/tags/vip")
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.remove_tag = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.delete("/api/v1/customers/9999/tags/vip")
        assert resp.status_code == 404


class TestChangeStatusEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.change_status = AsyncMock(return_value=_mock_to_dict({"id": 1, "status": "active"}))
        resp = client.put("/api/v1/customers/1/status", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "active"

    def test_invalid_status_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.put("/api/v1/customers/1/status", json={"status": "lead"})
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.change_status = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.put("/api/v1/customers/9999/status", json={"status": "active"})
        assert resp.status_code == 404


class TestAssignOwnerEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.assign_owner = AsyncMock(return_value=_mock_to_dict({"id": 1, "owner_id": 5}))
        resp = client.put("/api/v1/customers/1/owner", json={"owner_id": 5})
        assert resp.status_code == 200
        assert resp.json()["data"]["owner_id"] == 5

    def test_negative_owner_id_rejected(self, client_with_service):
        client, _, _ = client_with_service
        resp = client.put("/api/v1/customers/1/owner", json={"owner_id": -1})
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client_with_service):
        client, svc, _ = client_with_service
        svc.assign_owner = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.put("/api/v1/customers/9999/owner", json={"owner_id": 1})
        assert resp.status_code == 404


class TestBulkImportEndpoint:
    def test_success(self, client_with_service):
        client, svc, _ = client_with_service
        svc.bulk_import = AsyncMock(return_value=2)
        resp = client.post(
            "/api/v1/customers/import",
            json={"customers": [{"name": "A"}, {"name": "B"}]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["imported"] == 2

    def test_empty_customers_allowed(self, client_with_service):
        client, svc, _ = client_with_service
        svc.bulk_import = AsyncMock(return_value=0)
        resp = client.post("/api/v1/customers/import", json={"customers": []})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Score endpoint tests
# ---------------------------------------------------------------------------


def _register_app_exception_handler(app: FastAPI) -> None:
    from fastapi import HTTPException
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail},
        )


def _build_score_test_app(monkeypatch, *, override_score: bool = True, override_auth: bool = True):
    """Build a TestClient for the score endpoints with CustomerService and optionally ScoreService mocked.

    Returns (client, customer_mock, score_mock). A single score_mock instance is reused
    across all requests in the test (router calls ScoreService(session) per request, but
    the override returns the same mock each time). Tests reassign the relevant method
    on score_mock before each request to avoid state leaking between tests.
    """
    from internal.middleware.fastapi_auth import require_auth

    customer_mock = MagicMock()
    score_mock = MagicMock()

    def override_customer_service(repository):
        return customer_mock

    def override_score_service(session):
        return score_mock

    mock_session = MagicMock()
    mock_enrich_result = MagicMock()
    mock_enrich_result.all = MagicMock(return_value=[])
    mock_enrich_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_enrich_result)

    app = FastAPI()
    app.include_router(customers_router)
    if override_auth:
        app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_session

    monkeypatch.setattr(
        "api.routers.customers.CustomerService",
        override_customer_service,
    )
    if override_score:
        monkeypatch.setattr(
            "api.routers.customers.ScoreService",
            override_score_service,
        )

    monkeypatch.setattr(
        "api.routers.customers.CustomerRepository",
        lambda session: MagicMock(session=session),
    )

    _register_app_exception_handler(app)

    client = TestClient(app, raise_server_exceptions=False)
    return client, customer_mock, score_mock


@pytest.fixture
def client_with_score_service(monkeypatch):
    client, cust_mock, score_mock = _build_score_test_app(monkeypatch)
    return client, cust_mock, score_mock


class TestScoreEndpoints:
    def test_post_score_returns_data(self, client_with_score_service):
        from models.score import ScoreTier
        from services.score_service import ScoreResult

        client, _cust, score_svc = client_with_score_service
        score_svc.calculate_score = AsyncMock(
            return_value=ScoreResult(
                score=85,
                tier=ScoreTier.B,
                top_factors=["engagement_level"],
                recommendations=["Increase touchpoints with targeted campaigns"],
                similar_leads=[],
            )
        )
        resp = client.post("/api/v1/customers/1/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["score"] == 85
        assert body["data"]["tier"] == "B"
        assert body["data"]["top_factors"] == ["engagement_level"]
        assert body["data"]["recommendations"] == ["Increase touchpoints with targeted campaigns"]
        assert "message" in body
        score_svc.calculate_score.assert_called_once_with(1, tenant_id=1, include_ai=True)

    def test_get_score_returns_data_with_factors(self, client_with_score_service):
        from models.score import ScoreTier
        from services.score_service import ScoreResult

        client, _cust, score_svc = client_with_score_service
        score_svc.get_score = AsyncMock(
            return_value=ScoreResult(
                score=75,
                tier=ScoreTier.B,
                top_factors=["deal_velocity"],
                recommendations=["Accelerate pipeline with limited-time offers"],
                similar_leads=[],
            )
        )
        resp = client.get("/api/v1/customers/1/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["score"] == 75
        assert body["data"]["tier"] == "B"
        assert body["data"]["top_factors"] == ["deal_velocity"]
        assert body["data"]["recommendations"] == ["Accelerate pipeline with limited-time offers"]

    def test_get_score_returns_404_when_no_score(self, client_with_score_service):
        client, _cust, score_svc = client_with_score_service
        score_svc.get_score = AsyncMock(side_effect=NotFoundException("Score"))
        resp = client.get("/api/v1/customers/9999/score")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "Score" in body["message"]

    def test_get_score_returns_404_when_customer_missing(self, client_with_score_service):
        client, _cust, score_svc = client_with_score_service
        score_svc.get_score = AsyncMock(side_effect=NotFoundException("Customer"))
        resp = client.get("/api/v1/customers/9999/score")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "Customer" in body["message"]

    def test_post_score_requires_auth(self, monkeypatch):
        client, _cust, _ = _build_score_test_app(monkeypatch, override_auth=False)
        resp = client.post("/api/v1/customers/1/score")
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False

    def test_get_score_requires_auth(self, monkeypatch):
        client, _cust, _ = _build_score_test_app(monkeypatch, override_auth=False)
        resp = client.get("/api/v1/customers/1/score")
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
