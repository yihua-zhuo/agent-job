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

from services.auth_service import AuthService, is_valid_email


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
