"""Unit tests for src/api/routers/users.py — /api/v1/users and /api/v1/auth endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from models.response import ResponseStatus
from api.routers.users import (
    users_router,
    _http_status,
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
# Mock user-like object for service responses
# ---------------------------------------------------------------------------

class MockUser:
    def __init__(self, data=None):
        for k, v in (data or {}).items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_service(monkeypatch):
    from internal.middleware.fastapi_auth import require_auth

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

    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_service


# ---------------------------------------------------------------------------
# POST /api/v1/users — create user
# ---------------------------------------------------------------------------

class TestCreateUserEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        mock_user = MockUser({
            "id": 1, "tenant_id": 1, "username": "alice",
            "email": "alice@example.com", "role": "user", "status": "active",
            "full_name": "Alice", "bio": None,
        })
        svc.create_user = AsyncMock(
            return_value=_make_service_response(data=mock_user, message="用户创建成功")
        )
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
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR,
                message="用户名已存在",
            )
        )
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 400

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
        mock_user = MockUser({
            "id": 1, "tenant_id": 1, "username": "alice",
            "email": "alice@example.com", "role": "user", "status": "active",
            "full_name": "Alice", "bio": None, "created_at": None, "updated_at": None,
        })
        mock_list = MagicMock()
        mock_list.items = [mock_user]
        mock_list.total = 1
        mock_list.page = 1
        mock_list.page_size = 20
        mock_list.total_pages = 1
        mock_list.has_next = False
        mock_list.has_prev = False
        svc.list_users = AsyncMock(
            return_value=_make_service_response(data=mock_list)
        )
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1

    def test_service_error_propagates(self, client_with_service):
        client, svc = client_with_service
        svc.list_users = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.SERVER_ERROR, message="Server error"
            )
        )
        resp = client.get("/api/v1/users")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/users/{user_id} — get user
# ---------------------------------------------------------------------------

class TestGetUserEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_user = MockUser({
            "id": 1, "tenant_id": 1, "username": "alice",
            "email": "alice@example.com", "role": "user", "status": "active",
            "full_name": "Alice", "bio": None, "created_at": None, "updated_at": None,
        })
        svc.get_user_by_id = AsyncMock(return_value=mock_user)
        resp = client.get("/api/v1/users/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.get_user_by_id = AsyncMock(return_value=None)
        resp = client.get("/api/v1/users/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/users/{user_id} — update user
# ---------------------------------------------------------------------------

class TestUpdateUserEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_user = MockUser({
            "id": 1, "tenant_id": 1, "username": "alice",
            "email": "alice@example.com", "role": "user", "status": "active",
            "full_name": "Updated", "bio": None, "created_at": None, "updated_at": None,
        })
        svc.update_user = AsyncMock(
            return_value=_make_service_response(data=mock_user, message="用户更新成功")
        )
        resp = client.put("/api/v1/users/1", json={"full_name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["data"]["full_name"] == "Updated"

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.update_user = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="用户不存在"
            )
        )
        resp = client.put("/api/v1/users/9999", json={"full_name": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/users/{user_id} — delete user
# ---------------------------------------------------------------------------

class TestDeleteUserEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.delete_user = AsyncMock(
            return_value=_make_service_response(message="用户删除成功")
        )
        resp = client.delete("/api/v1/users/1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_not_found_returns_404(self, client_with_service):
        client, svc = client_with_service
        svc.delete_user = AsyncMock(
            return_value=_make_service_response(
                status=ResponseStatus.NOT_FOUND, message="用户不存在"
            )
        )
        resp = client.delete("/api/v1/users/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/users/search — search users
# ---------------------------------------------------------------------------

class TestSearchUsersEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        mock_user = MockUser({
            "id": 1, "tenant_id": 1, "username": "alice",
            "email": "alice@example.com", "role": "user", "status": "active",
            "full_name": "Alice", "bio": None, "created_at": None, "updated_at": None,
        })
        mock_list = MagicMock()
        mock_list.items = [mock_user]
        mock_list.total = 1
        mock_list.page = 1
        mock_list.page_size = 20
        mock_list.total_pages = 1
        mock_list.has_next = False
        mock_list.has_prev = False
        svc.search_users = AsyncMock(
            return_value=_make_service_response(data=mock_list)
        )
        resp = client.post("/api/v1/users/search?keyword=alice")
        # Note: keyword is a Query param so it's GET, but the router uses POST
        # Actually the router is POST with Query param, let's try POST with query string
        resp = client.post("/api/v1/users/search?keyword=alice", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_empty_keyword_rejected(self, client_with_service):
        client, _ = client_with_service
        # keyword is required min_length=1
        resp = client.post("/api/v1/users/search?keyword=", json={})
        assert resp.status_code in (422, 400)


# ---------------------------------------------------------------------------
# POST /api/v1/users/{user_id}/password — change password
# ---------------------------------------------------------------------------

class TestChangePasswordEndpoint:
    def test_success(self, client_with_service):
        client, svc = client_with_service
        svc.change_password = AsyncMock(
            return_value=_make_service_response(message="密码修改成功")
        )
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
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR,
                message="旧密码不正确",
            )
        )
        resp = client.post(
            "/api/v1/users/1/password",
            json={"old_password": "wrong", "new_password": "new123456"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register — register
# ---------------------------------------------------------------------------

class TestRegisterEndpoint:
    def test_success_returns_201(self, client_with_service):
        client, svc = client_with_service
        mock_user = MockUser({
            "id": 1, "tenant_id": 0, "username": "newuser",
            "email": "new@example.com", "role": "user", "status": "active",
            "full_name": "New User", "bio": None,
            "created_at": None, "updated_at": None,
        })
        svc.create_user = AsyncMock(
            return_value=_make_service_response(data=mock_user, message="注册成功")
        )
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
            return_value=_make_service_response(
                status=ResponseStatus.VALIDATION_ERROR,
                message="用户名已存在",
            )
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 400


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