"""Unit tests for src/main.py — exception handlers and app factory changes."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException


# ---------------------------------------------------------------------------
# Helpers: build a minimal app with the same exception handlers as main.py
# ---------------------------------------------------------------------------

def _make_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the same exception handlers used in main.py."""
    from fastapi.responses import JSONResponse
    from fastapi import Request
    from pkg.errors.app_exceptions import AppException

    app = FastAPI()

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

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Internal server error", "code": "INTERNAL_ERROR"},
        )

    @app.get("/trigger-http-exc")
    async def trigger_http_exc():
        raise HTTPException(status_code=404, detail="Resource not found")

    @app.get("/trigger-http-exc-400")
    async def trigger_http_exc_400():
        raise HTTPException(status_code=400, detail="Bad request")

    @app.get("/trigger-generic-exc")
    async def trigger_generic_exc():
        raise RuntimeError("Something went wrong internally")

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    return app


@pytest.fixture
def test_client():
    app = _make_test_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# HTTPException handler
# ---------------------------------------------------------------------------

class TestHTTPExceptionHandler:
    def test_http_404_returns_error_envelope_shape(self, test_client):
        resp = test_client.get("/trigger-http-exc")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["message"] == "Resource not found"
        # ErrorEnvelope shape — no 'code' field for plain HTTPException
        assert "code" not in body

    def test_http_400_returns_error_envelope_shape(self, test_client):
        resp = test_client.get("/trigger-http-exc-400")
        assert resp.status_code == 400
        body = resp.json()
        assert body["success"] is False
        assert body["message"] == "Bad request"

    def test_success_flag_is_false(self, test_client):
        resp = test_client.get("/trigger-http-exc")
        assert resp.json()["success"] is False

    def test_message_matches_detail(self, test_client):
        resp = test_client.get("/trigger-http-exc")
        assert "Resource not found" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Generic exception handler (unhandled exceptions)
# ---------------------------------------------------------------------------

class TestGenericExceptionHandler:
    def test_returns_500(self, test_client):
        resp = test_client.get("/trigger-generic-exc")
        assert resp.status_code == 500

    def test_body_has_success_false(self, test_client):
        resp = test_client.get("/trigger-generic-exc")
        body = resp.json()
        assert body["success"] is False

    def test_body_has_generic_message(self, test_client):
        resp = test_client.get("/trigger-generic-exc")
        assert resp.json()["message"] == "Internal server error"

    def test_body_has_internal_error_code(self, test_client):
        resp = test_client.get("/trigger-generic-exc")
        assert resp.json()["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# AppException handler
# ---------------------------------------------------------------------------

class TestAppExceptionHandler:
    def test_app_exception_returns_correct_status(self):
        from pkg.errors.app_exceptions import AppException
        from fastapi.responses import JSONResponse

        app = _make_test_app()

        @app.get("/trigger-app-exc")
        async def trigger_app_exc():
            raise AppException(status_code=403, code="FORBIDDEN", detail="Access denied")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/trigger-app-exc")
        assert resp.status_code == 403

    def test_app_exception_body_shape(self):
        from pkg.errors.app_exceptions import AppException

        app = _make_test_app()

        @app.get("/trigger-app-exc-body")
        async def trigger_app_exc_body():
            raise AppException(status_code=401, code="UNAUTHORIZED", detail="Not authorized")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/trigger-app-exc-body")
        body = resp.json()
        assert body["success"] is False
        assert body["message"] == "Not authorized"
        assert body["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Health check / normal routes unaffected
# ---------------------------------------------------------------------------

class TestHealthRoute:
    def test_ok_route_works(self, test_client):
        resp = test_client.get("/ok")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# create_app function tests (smoke test)
# ---------------------------------------------------------------------------

class TestCreateApp:
    def test_create_app_returns_fastapi_instance(self):
        """Smoke test: create_app() returns a FastAPI app without errors."""
        import sys
        from pathlib import Path

        # Ensure src is on path
        src = Path(__file__).resolve().parents[3] / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))

        with (
            patch("db.connection.ensure_engine"),
            patch("db.connection.dispose_engine"),
        ):
            from main import create_app
            app = create_app()
            assert isinstance(app, FastAPI)

    def test_app_includes_customers_router(self):
        """Routes for /api/v1/customers are registered."""
        with (
            patch("db.connection.ensure_engine"),
            patch("db.connection.dispose_engine"),
        ):
            from main import create_app
            app = create_app()
            routes = [r.path for r in app.routes]
            customer_routes = [r for r in routes if "customers" in r]
            assert len(customer_routes) > 0

    def test_app_includes_sales_router(self):
        """Routes for /api/v1/sales are registered."""
        with (
            patch("db.connection.ensure_engine"),
            patch("db.connection.dispose_engine"),
        ):
            from main import create_app
            app = create_app()
            routes = [r.path for r in app.routes]
            sales_routes = [r for r in routes if "sales" in r]
            assert len(sales_routes) > 0

    def test_app_has_health_check(self):
        """GET / health check route is present."""
        with (
            patch("db.connection.ensure_engine"),
            patch("db.connection.dispose_engine"),
        ):
            from main import create_app
            app = create_app()
            routes = [r.path for r in app.routes]
            assert "/" in routes