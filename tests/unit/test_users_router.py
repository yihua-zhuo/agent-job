"""Unit tests for src/api/routers/users.py — /api/v1/users and /api/v1/auth endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routers.users import users_router
from internal.middleware.fastapi_auth import AuthContext
from db.connection import get_db
from pkg.errors.app_exceptions import (
    AppException,
    NotFoundException,
    ValidationException,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_ctx(tenant_id: int = 1, user_id: int = 99) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=[])


USER_ROW = {
    "id": 1,
    "tenant_id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "role": "user",
    "status": "active",
    "full_name": "Alice Smith",
    "bio": None,
    "created_at": None,
    "updated_at": None,
}


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_service(monkeypatch):
    from internal.middleware.fastapi_auth import require_auth
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    mock_service = MagicMock()
    monkeypatch.setattr(
        "api.routers.users.UserService",
        lambda session: mock_service,
    )
    monkeypatch.setattr(
        "api.routers.users.AuthService",
        lambda session, secret_key=None: mock_service,
    )

    app = FastAPI()
    app.include_router(users_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: MagicMock()

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "code": exc.code},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(exc)},
        )

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


# ---------------------------------------------------------------------------
# POST /api/v1/users — create user
# ---------------------------------------------------------------------------

class TestCreateUserEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        svc.create_user = AsyncMock(return_value=USER_ROW)
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "password123",
                "full_name": "Alice",
                "role": "user",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["username"] == "alice"

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.create_user = AsyncMock(
            side_effect=ValidationException("用户名已存在")
        )
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 422

    def test_short_username_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "ab",
                "email": "alice@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 422

    def test_short_password_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "short",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/users — list users
# ---------------------------------------------------------------------------

class TestListUsersEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.list_users = AsyncMock(return_value=([USER_ROW], 1))
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1


# ---------------------------------------------------------------------------
# GET /api/v1/users/{user_id} — get user
# ---------------------------------------------------------------------------

class TestGetUserEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.get_user_by_id = AsyncMock(return_value=USER_ROW)
        resp = client.get("/api/v1/users/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_user_by_id = AsyncMock(
            side_effect=NotFoundException("User")
        )
        resp = client.get("/api/v1/users/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/users/{user_id} — update user
# ---------------------------------------------------------------------------

class TestUpdateUserEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.update_user = AsyncMock(
            return_value={**USER_ROW, "full_name": "Updated"}
        )
        resp = client.put("/api/v1/users/1", json={"full_name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["data"]["full_name"] == "Updated"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_user = AsyncMock(
            side_effect=NotFoundException("User")
        )
        resp = client.put("/api/v1/users/9999", json={"full_name": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/users/{user_id} — delete user
# ---------------------------------------------------------------------------

class TestDeleteUserEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.delete_user = AsyncMock(return_value=None)
        resp = client.delete("/api/v1/users/1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.delete_user = AsyncMock(
            side_effect=NotFoundException("User")
        )
        resp = client.delete("/api/v1/users/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/users/search — search users
# ---------------------------------------------------------------------------

class TestSearchUsersEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.search_users = AsyncMock(return_value=([USER_ROW], 1))
        resp = client.post("/api/v1/users/search?keyword=alice")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_empty_keyword_rejected(self, client_with_service):
        client, _ = client_with_service
        # keyword is required min_length=1
        resp = client.post("/api/v1/users/search?keyword=")
        assert resp.status_code in (422, 400)


# ---------------------------------------------------------------------------
# POST /api/v1/users/{user_id}/password — change password
# ---------------------------------------------------------------------------

class TestChangePasswordEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.change_password = AsyncMock(return_value=None)
        resp = client.post(
            "/api/v1/users/1/password",
            json={"old_password": "old123456", "new_password": "new123456"},
        )
        assert resp.status_code == 200

    def test_short_new_password_rejected(self, client_with_service):
        client, _ = client_with_service
        resp = client.post(
            "/api/v1/users/1/password",
            json={"old_password": "old123456", "new_password": "short"},
        )
        assert resp.status_code == 422

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.change_password = AsyncMock(
            side_effect=ValidationException("旧密码不正确")
        )
        resp = client.post(
            "/api/v1/users/1/password",
            json={"old_password": "wrong", "new_password": "new123456"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register — register
# ---------------------------------------------------------------------------

class TestRegisterEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        svc.create_user = AsyncMock(return_value=USER_ROW)
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True

    def test_service_error_returns_4xx(self, client_with_service):
        client, svc = client_with_service
        svc.create_user = AsyncMock(
            side_effect=ValidationException("用户名已存在")
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login — login
# ---------------------------------------------------------------------------

class TestLoginEndpoint:
    def test_success_returns_200(self, client_with_service):
        client, svc = client_with_service
        svc.authenticate_user = AsyncMock(
            return_value={
                "id": 1,
                "username": "alice",
                "role": "user",
                "tenant_id": 1,
            }
        )
        svc.generate_token = MagicMock(return_value="fake-jwt-token")
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "alice", "password": "password123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_invalid_credentials_returns_401(self, client_with_service):
        client, svc = client_with_service
        svc.authenticate_user = AsyncMock(return_value=None)
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "alice", "password": "wrong"},
        )
        assert resp.status_code == 401
