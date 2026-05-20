"""Unit tests for AuthService JWT token operations and is_valid_email."""

import time
from unittest.mock import MagicMock

import pytest

from src.services.auth_service import AuthService, is_valid_email


@pytest.fixture
def auth_service():
    return AuthService(MagicMock(), secret_key="test-secret")


class TestGenerateToken:
    """Tests for AuthService.generate_token."""

    def test_generate_token_returns_string(self, auth_service):
        """generate_token should return a non-empty string."""
        token = auth_service.generate_token(1, "alice", "admin", 10)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_without_tenant(self, auth_service):
        """generate_token without tenant_id should not include tenant_id in payload."""
        token = auth_service.generate_token(1, "alice", "admin")
        assert isinstance(token, str)
        decoded = auth_service.verify_token(token)
        assert decoded is not None
        assert "tenant_id" not in decoded


class TestVerifyToken:
    """Tests for AuthService.verify_token."""

    def test_verify_token_valid(self, auth_service):
        """verify_token should return payload dict for a valid token."""
        token = auth_service.generate_token(1, "alice", "admin", 10)
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"

    def test_verify_token_invalid(self, auth_service):
        """verify_token should return None for a nonsense string."""
        result = auth_service.verify_token("not.a.valid.token.string")
        assert result is None

    def test_verify_token_tampered(self, auth_service):
        """verify_token should return None when token was signed with a different secret."""
        other_service = AuthService(MagicMock(), secret_key="different-secret")
        token = other_service.generate_token(1, "alice", "admin", 10)
        result = auth_service.verify_token(token)
        assert result is None


class TestRefreshToken:
    """Tests for AuthService.refresh_token."""

    @pytest.mark.asyncio
    async def test_refresh_token_valid(self, auth_service):
        """refresh_token should return a new non-empty string different from the original."""
        original = auth_service.generate_token(1, "alice", "admin", 10)
        time.sleep(1.1)
        new_token = await auth_service.refresh_token(original)
        assert isinstance(new_token, str)
        assert len(new_token) > 0
        assert new_token != original

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, auth_service):
        """refresh_token should raise UnauthorizedException for a malformed token."""
        from src.services.auth_service import UnauthorizedException

        try:
            await auth_service.refresh_token("not.a.valid.token.string")
        except UnauthorizedException:
            return
        except Exception as exc:
            pytest.fail(f"Expected UnauthorizedException but got {type(exc).__name__}: {exc}")
        pytest.fail("Expected UnauthorizedException was not raised")


class TestIsValidEmail:
    """Tests for is_valid_email module-level function."""

    def test_is_valid_email(self):
        """is_valid_email should return True for valid addresses and False for invalid ones."""
        assert is_valid_email("alice@example.com") is True
        assert is_valid_email("user.name+tag@domain.co.uk") is True
        assert is_valid_email("test@sub.domain.example.com") is True
        assert is_valid_email("not-an-email") is False
        assert is_valid_email("@example.com") is False
        assert is_valid_email("user@") is False
        assert is_valid_email("") is False
