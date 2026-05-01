"""Unit tests for AuthService."""
import base64
import json
import sys
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch


# Install fake jwt before auth_service imports it.
class _ExpiredSignatureError(Exception):
    pass


class _InvalidTokenError(Exception):
    pass


class _FakeJWT:
    @staticmethod
    def encode(payload: dict, key: str, algorithm: str) -> str:
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": algorithm, "typ": "JWT"}, separators=(",", ":")).encode()
        ).rstrip(b"=")
        payload_encoded = base64.urlsafe_b64encode(
            json.dumps(payload, default=str, separators=(",", ":")).encode()
        ).rstrip(b"=")
        sig = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=")
        return f"{header.decode()}.{payload_encoded.decode()}.{sig.decode()}"

    @staticmethod
    def decode(token: str, key: str, algorithms: list, issuer=None, audience=None, options=None):
        parts = token.split(".")
        if len(parts) != 3:
            raise _InvalidTokenError()
        try:
            padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))
        except Exception:
            raise _InvalidTokenError()
        if issuer and payload.get("iss") != issuer:
            raise _InvalidTokenError()
        if audience and payload.get("aud") != audience:
            raise _InvalidTokenError()
        return payload

    ExpiredSignatureError = _ExpiredSignatureError
    InvalidTokenError = _InvalidTokenError


sys.modules["jwt"] = _FakeJWT  # type: ignore[assign]

from src.services.auth_service import AuthService, is_valid_email, sanitize_string, validate_id


@pytest.fixture
def auth_service():
    """Each test gets its own AuthService with fake JWT pre-installed."""
    # Re-install fake jwt so patches from other tests don't leak real jwt
    sys.modules["jwt"] = _FakeJWT
    return AuthService(secret_key="test-secret-key")


@pytest.mark.asyncio
class TestAuthService:
    # ── generate_token ───────────────────────────────────────────────────────

    async def test_generate_token_returns_string(self, auth_service):
        token = auth_service.generate_token(1, "alice", "admin", tenant_id=1)
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_generate_token_without_tenant(self, auth_service):
        token = auth_service.generate_token(2, "bob", "user")
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_generate_token_with_tenant_id(self, auth_service):
        token = auth_service.generate_token(1, "alice", "admin", tenant_id=42)
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["tenant_id"] == 42

    async def test_generate_token_without_tenant(self, auth_service):
        """When tenant_id is None it should not appear in payload."""
        token = auth_service.generate_token(2, "bob", "user")
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert "tenant_id" not in payload

    # ── verify_token ──────────────────────────────────────────────────────────

    async def test_verify_token_valid(self, auth_service):
        token = auth_service.generate_token(1, "alice", "admin", tenant_id=1)
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"

    async def test_verify_token_invalid(self, auth_service):
        result = auth_service.verify_token("not.a.valid.token")
        assert result is None

    async def test_verify_token_tampered(self, auth_service):
        result = auth_service.verify_token("not.even.close")
        assert result is None

    async def test_verify_token_expired(self, auth_service):
        """jwt.decode raises ExpiredSignatureError → verify_token returns None."""
        import services.auth_service as auth_mod
        orig = auth_mod.jwt.decode
        auth_mod.jwt.decode = MagicMock(side_effect=auth_mod.jwt.ExpiredSignatureError())
        try:
            result = auth_service.verify_token("expired.token.here")
            assert result is None
        finally:
            auth_mod.jwt.decode = orig

    async def test_verify_token_invalid_signature(self, auth_service):
        """jwt.decode raises InvalidTokenError → verify_token returns None."""
        import services.auth_service as auth_mod
        orig = auth_mod.jwt.decode
        auth_mod.jwt.decode = MagicMock(side_effect=auth_mod.jwt.InvalidTokenError())
        try:
            result = auth_service.verify_token("bad.signature")
            assert result is None
        finally:
            auth_mod.jwt.decode = orig

    async def test_verify_token_malformed(self, auth_service):
        """Malformed token causes decode error → verify_token returns None."""
        import services.auth_service as auth_mod
        orig = auth_mod.jwt.decode
        auth_mod.jwt.decode = MagicMock(side_effect=auth_mod.jwt.InvalidTokenError("malformed"))
        try:
            result = auth_service.verify_token("not-valid")
            assert result is None
        finally:
            auth_mod.jwt.decode = orig

    # ── authenticate_user (login) ────────────────────────────────────────────

    async def test_authenticate_user_user_not_found(self, auth_service, mock_get_db_session):
        """User does not exist → returns None."""
        # Override: make users query return empty
        mock_get_db_session.execute.side_effect = lambda sql, params: MagicMock(
            fetchone=MagicMock(return_value=None)
        )
        result = await auth_service.authenticate_user("ghost", "anypassword")
        assert result is None

    async def test_authenticate_user_wrong_password(self, auth_service, mock_get_db_session):
        """User exists but password is wrong → returns None."""
        hashed = auth_service.hash_password("CorrectPassword")

        async def fake_execute(sql, params=None):
            if "username" in str(sql).lower():
                # simulate user found with correct hash stored
                return MagicMock(
                    fetchone=MagicMock(
                        return_value=MagicMock(
                            __getitem__=lambda s, k: {
                                0: 1,        # id
                                1: 1,        # tenant_id
                                2: "alice",   # username
                                3: "alice@test.com",  # email
                                4: hashed,   # password_hash
                                5: "user",   # role
                                6: "active", # status
                                7: "Alice",  # full_name
                                8: "bio",    # bio
                                9: datetime.now(UTC),  # created_at
                                10: datetime.now(UTC),  # updated_at
                            }.get(k)
                        )
                    )
                )
            return MagicMock(fetchone=MagicMock(return_value=None))

        mock_get_db_session.execute = AsyncMock(side_effect=fake_execute)
        result = await auth_service.authenticate_user("alice", "WrongPassword")
        assert result is None

    async def test_authenticate_user_success(self, auth_service, mock_get_db_session):
        """Valid credentials → returns user dict."""
        password = "CorrectPassword123"
        hashed = auth_service.hash_password(password)

        async def fake_execute(sql, params=None):
            if "username" in str(sql).lower():
                return MagicMock(
                    fetchone=MagicMock(
                        return_value=MagicMock(
                            __getitem__=lambda s, k: {
                                0: 1,
                                1: 1,
                                2: "alice",
                                3: "alice@test.com",
                                4: hashed,
                                5: "user",
                                6: "active",
                                7: "Alice",
                                8: "bio",
                                9: datetime.now(UTC),
                                10: datetime.now(UTC),
                            }.get(k)
                        )
                    )
                )
            return MagicMock(fetchone=MagicMock(return_value=None))

        mock_get_db_session.execute = AsyncMock(side_effect=fake_execute)
        result = await auth_service.authenticate_user("alice", password)
        assert result is not None
        assert result["username"] == "alice"
        assert result["email"] == "alice@test.com"

    # ── create_user (register) ───────────────────────────────────────────────

    async def test_create_user_duplicate_email(self, auth_service, mock_get_db_session):
        """UserService.create_user returns duplicate email error → propagate."""
        from unittest.mock import AsyncMock as AMock

        error_response = MagicMock()
        error_response.success = False
        error_response.message = "邮箱已被注册"
        error_response.errors = [MagicMock(code=2005, message="邮箱已被使用", field="email")]

        fake_user_svc = MagicMock()
        fake_user_svc.create_user = AMock(return_value=error_response)

        with patch("services.user_service.UserService", return_value=fake_user_svc):
            result = await auth_service.create_user(
                username="newuser",
                email="existing@test.com",
                password="StrongPass1",
            )
        assert result.success is False
        assert "邮箱已被注册" in result.message

    async def test_create_user_weak_password(self, auth_service, mock_get_db_session):
        """UserService.create_user rejects weak password → propagate."""
        from unittest.mock import AsyncMock as AMock

        error_response = MagicMock()
        error_response.success = False
        error_response.message = "密码长度至少8位"
        error_response.errors = [MagicMock(code=1001, message="密码长度至少8位", field="password")]

        fake_user_svc = MagicMock()
        fake_user_svc.create_user = AMock(return_value=error_response)

        with patch("services.user_service.UserService", return_value=fake_user_svc):
            result = await auth_service.create_user(
                username="newuser",
                email="new@test.com",
                password="weak",
            )
        assert result.success is False
        assert "密码" in result.message

    async def test_create_user_success(self, auth_service, mock_get_db_session):
        """UserService.create_user succeeds → propagate."""
        from unittest.mock import AsyncMock as AMock

        success_response = MagicMock()
        success_response.success = True
        success_response.message = "用户创建成功"
        success_response.data = MagicMock(id=99, username="newuser")

        fake_user_svc = MagicMock()
        fake_user_svc.create_user = AMock(return_value=success_response)

        with patch("services.user_service.UserService", return_value=fake_user_svc):
            result = await auth_service.create_user(
                username="newuser",
                email="new@test.com",
                password="StrongPass1",
            )
        assert result.success is True

    # ── get_current_user ────────────────────────────────────────────────────

    async def test_get_current_user_invalid_token(self, auth_service, mock_get_db_session):
        """verify_token returns None → get_current_user returns None."""
        with patch.object(auth_service, "verify_token", return_value=None):
            result = await auth_service.get_current_user("bad.token")
            assert result is None

    async def test_get_current_user_no_user_id_in_payload(self, auth_service, mock_get_db_session):
        """verify_token returns payload without user_id → returns None."""
        with patch.object(auth_service, "verify_token", return_value={"sub": "1"}):
            result = await auth_service.get_current_user("any.token")
            assert result is None

    async def test_get_current_user_not_found_in_db(self, auth_service, mock_get_db_session):
        """Token valid but user not in DB → returns None."""
        async def fake_execute(sql, params=None):
            return MagicMock(fetchone=MagicMock(return_value=None))

        mock_get_db_session.execute = AsyncMock(side_effect=fake_execute)

        with patch.object(auth_service, "verify_token", return_value={"user_id": 99, "username": "ghost", "role": "user"}):
            result = await auth_service.get_current_user("valid.token")
            assert result is None

    async def test_get_current_user_success(self, auth_service, mock_get_db_session):
        """Token valid + user exists → returns user dict."""
        now = datetime.now(UTC)

        async def fake_execute(sql, params=None):
            return MagicMock(
                fetchone=MagicMock(
                    return_value=MagicMock(
                        __getitem__=lambda s, k: {
                            0: 5,           # id
                            1: 1,           # tenant_id
                            2: "charlie",   # username
                            3: "charlie@test.com",  # email
                            4: "admin",     # role
                            5: "active",    # status
                            6: "Charlie",   # full_name
                            7: "dev",       # bio
                            8: now,         # created_at
                            9: now,         # updated_at
                        }.get(k)
                    )
                )
            )

        mock_get_db_session.execute = AsyncMock(side_effect=fake_execute)

        with patch.object(auth_service, "verify_token", return_value={"user_id": 5, "username": "charlie", "role": "admin"}):
            result = await auth_service.get_current_user("valid.token")
            assert result is not None
            assert result["id"] == 5
            assert result["username"] == "charlie"
            assert result["role"] == "admin"

    # ── revoke_token ─────────────────────────────────────────────────────────

    async def test_revoke_token_invalid(self, auth_service, mock_get_db_session):
        """verify_token returns None → revoke_token returns False."""
        with patch.object(auth_service, "verify_token", return_value=None):
            result = await auth_service.revoke_token("bad.token")
            assert result is False

    async def test_revoke_token_success(self, auth_service, mock_get_db_session):
        """Valid token → revoke_token calls DB and returns True."""
        mock_execute = AsyncMock()
        mock_commit = AsyncMock()
        mock_get_db_session.execute = mock_execute
        mock_get_db_session.commit = mock_commit

        with patch.object(auth_service, "verify_token", return_value={"jti": "abc123", "exp": 9999999999, "sub": "1"}):
            result = await auth_service.revoke_token("valid.token")
            assert result is True
            mock_execute.assert_called_once()
            mock_commit.assert_called_once()

    # ── refresh_token ─────────────────────────────────────────────────────────

    async def test_refresh_token_invalid(self, auth_service):
        """verify_token returns None → refresh_token returns None."""
        with patch.object(auth_service, "verify_token", return_value=None):
            result = await auth_service.refresh_token("bad.token")
            assert result is None

    async def test_refresh_token_missing_fields(self, auth_service):
        """Payload missing user_id/username/role → returns None."""
        with patch.object(auth_service, "verify_token", return_value={"sub": "1"}):
            result = await auth_service.refresh_token("token.without.user.fields")
            assert result is None

    async def test_refresh_token_success(self, auth_service):
        """Valid payload → returns new token string."""
        with patch.object(auth_service, "verify_token", return_value={
            "user_id": 7,
            "username": "diana",
            "role": "admin",
            "tenant_id": 3,
        }):
            result = await auth_service.refresh_token("old.token")
            assert result is not None
            # Verify the new token is valid and contains updated exp
            payload = auth_service.verify_token(result)
            assert payload["user_id"] == 7
            assert payload["username"] == "diana"

    # ── create_token (async alias) ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_token_returns_valid_token(self, auth_service):
        """create_token is async alias that calls generate_token internally."""
        token = await auth_service.create_token(1, "alice", "admin", tenant_id=1)
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "alice"
        assert payload["tenant_id"] == 1


# ── Helper / static method tests ──────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_password_returns_string(self, auth_service):
        hashed = auth_service.hash_password("MySecret123")
        assert isinstance(hashed, str)
        assert hashed != "MySecret123"
        assert hashed.startswith("$2")  # bcrypt prefix

    def test_hash_password_different_each_time(self, auth_service):
        """bcrypt generates unique salts, so same password → different hashes."""
        h1 = auth_service.hash_password("Secret")
        h2 = auth_service.hash_password("Secret")
        assert h1 != h2

    def test_verify_password_correct(self, auth_service):
        hashed = auth_service.hash_password("CorrectPassword")
        assert auth_service.verify_password("CorrectPassword", hashed) is True

    def test_verify_password_incorrect(self, auth_service):
        hashed = auth_service.hash_password("CorrectPassword")
        assert auth_service.verify_password("WrongPassword", hashed) is False

    def test_verify_password_empty_hash(self, auth_service):
        assert auth_service.verify_password("any", "") is False

    def test_verify_password_none_hash(self, auth_service):
        assert auth_service.verify_password("any", None) is False

    def test_verify_password_malformed_hash(self, auth_service):
        assert auth_service.verify_password("pw", "not-a-bcrypt-hash") is False


class TestUtilityFunctions:
    def test_is_valid_email(self):
        assert is_valid_email("alice@example.com") is True
        assert is_valid_email("user+tag@domain.co.uk") is True
        assert is_valid_email("invalid") is False
        assert is_valid_email("") is False
        assert is_valid_email("missing@domain") is False

    def test_sanitize_string_strips_html_tags(self):
        assert sanitize_string("<script>alert('xss')</script>Hello") == "alert('xss')Hello"
        assert sanitize_string("<b>Bold</b>") == "Bold"

    def test_sanitize_string_removes_control_chars(self):
        assert sanitize_string("Hello\x00World") == "HelloWorld"
        assert sanitize_string("Line1\nLine2\rTab\t") == "Line1Line2Tab"

    def test_sanitize_string_removes_sql_comments(self):
        assert sanitize_string("SELECT * FROM users; -- comment") == "SELECT * FROM users;  comment"
        assert sanitize_string("SELECT /* block */ 1") == "SELECT  1"

    def test_sanitize_string_trims_whitespace(self):
        assert sanitize_string("  Hello World  ") == "Hello World"

    def test_sanitize_string_empty(self):
        assert sanitize_string("") == ""
        assert sanitize_string(None) is None

    def test_validate_id_positive_integer(self):
        validate_id(1)
        validate_id(42)
        validate_id(999999)
        # Should not raise

    def test_validate_id_zero_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            validate_id(0)

    def test_validate_id_negative_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            validate_id(-1)

    def test_validate_id_non_int_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            validate_id("1")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="positive integer"):
            validate_id(1.5)  # type: ignore[arg-type]

    def test_validate_id_custom_field_name(self):
        with pytest.raises(ValueError, match="workflow_id"):
            validate_id(0, field_name="workflow_id")