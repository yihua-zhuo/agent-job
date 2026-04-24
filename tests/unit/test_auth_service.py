"""Unit tests for AuthService."""
import base64
import json
import sys
import pytest


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

from services.auth_service import AuthService, is_valid_email, sanitize_string, validate_id


@pytest.fixture
def auth_service():
    return AuthService(secret_key="test-secret-key")


@pytest.mark.asyncio
class TestAuthService:
    async def test_generate_token_returns_string(self, auth_service):
        token = auth_service.generate_token(1, "alice", "admin", tenant_id=1)
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_generate_token_without_tenant(self, auth_service):
        token = auth_service.generate_token(2, "bob", "user")
        assert isinstance(token, str)
        assert len(token) > 0

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



    async def test_is_valid_email(self):
        assert is_valid_email("alice@example.com") is True
        assert is_valid_email("user+tag@domain.co.uk") is True
        assert is_valid_email("invalid") is False
        assert is_valid_email("") is False
        assert is_valid_email("missing@domain") is False

    # ── Password hashing ───────────────────────────────────────────────────────

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

    # ── Token with / without tenant ───────────────────────────────────────────

    def test_generate_token_with_tenant_id(self, auth_service):
        token = auth_service.generate_token(1, "alice", "admin", tenant_id=42)
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["tenant_id"] == 42

    def test_generate_token_without_tenant(self, auth_service):
        """When tenant_id is None it should not appear in payload."""
        token = auth_service.generate_token(2, "bob", "user")
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert "tenant_id" not in payload

    # ── sanitize_string ───────────────────────────────────────────────────────

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

    # ── validate_id ───────────────────────────────────────────────────────────

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

    # ── create_token is alias of generate_token ───────────────────────────────

    @pytest.mark.asyncio
    async def test_create_token_returns_valid_token(self, auth_service):
        """create_token is async alias that calls generate_token internally."""
        token = await auth_service.create_token(1, "alice", "admin", tenant_id=1)
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "alice"
        assert payload["tenant_id"] == 1
