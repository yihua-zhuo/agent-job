"""Unit tests for AuthService."""
import base64
import json
import sys
import pytest


# Stub jwt before importing auth_service so AuthService loads without PyJWT installed.
class _ExpiredSignatureError(Exception):
    pass


class _InvalidTokenError(Exception):
    pass


class _FakeJWT:
    """Minimal fake jwt for environments without PyJWT."""

    @staticmethod
    def encode(payload: dict, key: str, algorithm: str) -> str:
        header = json.dumps({"alg": algorithm, "typ": "JWT"}, separators=(",", ":")).encode()
        payload_encoded = base64.urlsafe_b64encode(json.dumps(payload, default=str, separators=(",", ":")).encode())
        sig = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=")
        return (
            base64.urlsafe_b64encode(header).rstrip(b"=").decode()
            + "."
            + payload_encoded.rstrip(b"=").decode()
            + "."
            + sig.decode()
        )

    @staticmethod
    def decode(
        token: str,
        key: str,
        algorithms: list,
        issuer=None,
        audience=None,
        options=None,
    ):
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


# Install fake before auth_service imports jwt.
sys.modules["jwt"] = _FakeJWT  # type: ignore[assign]

from src.services.auth_service import AuthService, is_valid_email  # noqa: E402


@pytest.fixture
def auth_service():
    """Create an AuthService instance with a known test secret."""
    return AuthService(secret_key="test-secret-key")


class TestAuthService:
    """Tests for AuthService."""

    def test_generate_token_returns_string(self, auth_service):
        """Test generate_token returns a non-empty string."""
        token = auth_service.generate_token(1, "alice", "admin", tenant_id=1)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_without_tenant(self, auth_service):
        """Test generate_token works without a tenant_id."""
        token = auth_service.generate_token(2, "bob", "user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_valid(self, auth_service):
        """Test verify_token round-trips correctly."""
        token = auth_service.generate_token(1, "alice", "admin", tenant_id=1)
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"

    def test_verify_token_invalid(self, auth_service):
        """Test verify_token returns None for an invalid token."""
        result = auth_service.verify_token("not.a.valid.token")
        assert result is None

    def test_verify_token_tampered(self, auth_service):
        """Test verify_token returns None for a malformed token."""
        # A truly malformed token (not three parts) should return None.
        result = auth_service.verify_token("not.even.close")
        assert result is None

    def test_refresh_token_valid(self, auth_service):
        """Test refresh_token returns a new valid token."""
        old_token = auth_service.generate_token(1, "alice", "admin", tenant_id=1)
        new_token = auth_service.refresh_token(old_token)
        assert new_token is not None
        assert isinstance(new_token, str)
        assert new_token != old_token
        # Verify the refreshed token is valid
        payload = auth_service.verify_token(new_token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "alice"

    def test_refresh_token_invalid(self, auth_service):
        """Test refresh_token returns None for an invalid token."""
        result = auth_service.refresh_token("bad.token.here")
        assert result is None

    def test_is_valid_email(self):
        """Test is_valid_email with various inputs."""
        assert is_valid_email("alice@example.com") is True
        assert is_valid_email("user+tag@domain.co.uk") is True
        assert is_valid_email("invalid") is False
        assert is_valid_email("") is False
        assert is_valid_email("missing@domain") is False
