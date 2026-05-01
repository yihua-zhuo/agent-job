"""Integration tests for AuthService - tests password hashing, JWT tokens, and validation."""
import os
import sys
from pathlib import Path

# Ensure src/ is on sys.path
_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest
from src.services.auth_service import (
    AuthService,
    is_valid_email,
    sanitize_string,
    validate_id,
)


class TestPasswordHashing:
    """Test password hashing and verification roundtrip."""

    def test_hash_password_returns_string(self):
        password = "SecureP@ssw0rd!"
        hashed = AuthService.hash_password(password)
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) > 30

    def test_hash_password_different_each_time(self):
        """bcrypt generates unique salts, so hashes differ."""
        password = "SamePassword123"
        h1 = AuthService.hash_password(password)
        h2 = AuthService.hash_password(password)
        assert h1 != h2

    def test_verify_password_correct(self):
        password = "MyCorrectPassword"
        hashed = AuthService.hash_password(password)
        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        password = "MyCorrectPassword"
        hashed = AuthService.hash_password(password)
        assert AuthService.verify_password("WrongPassword", hashed) is False

    def test_verify_password_empty_hash_returns_false(self):
        assert AuthService.verify_password("password", "") is False
        assert AuthService.verify_password("password", None) is False  # type: ignore

    def test_verify_password_malformed_hash_returns_false(self):
        assert AuthService.verify_password("password", "not-a-bcrypt-hash") is False


class TestJWTTokens:
    """Test JWT token generation and verification."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService with a test secret."""
        os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-12345"
        return AuthService(secret_key="test-secret-key-for-testing-12345")

    def test_generate_token_returns_jwt_string(self, auth_service):
        token = auth_service.generate_token(
            user_id=123,
            username="testuser",
            role="admin",
            tenant_id=999,
        )
        assert isinstance(token, str)
        assert token.count(".") == 2  # JWT has 3 parts

    def test_generate_token_includes_custom_claims(self, auth_service):
        token = auth_service.generate_token(
            user_id=42,
            username="alice",
            role="user",
            tenant_id=10,
        )
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 42
        assert payload["username"] == "alice"
        assert payload["role"] == "user"
        assert payload["tenant_id"] == 10

    def test_generate_token_without_tenant(self, auth_service):
        token = auth_service.generate_token(
            user_id=1,
            username="bob",
            role="viewer",
        )
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert "tenant_id" not in payload

    def test_verify_token_valid(self, auth_service):
        token = auth_service.generate_token(user_id=1, username="user", role="admin")
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 1

    def test_verify_token_invalid_returns_none(self, auth_service):
        assert auth_service.verify_token("not.a.valid.token") is None
        assert auth_service.verify_token("") is None
        assert auth_service.verify_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjN9.sig") is None

    @pytest.mark.asyncio
    async def test_create_token_is_alias_for_generate(self, auth_service):
        """create_token is an async-compatible alias for generate_token."""
        token = await auth_service.create_token(user_id=55, username="charlie", role="user")
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 55


class TestValidationHelpers:
    """Test email validation, string sanitization, and ID validation."""

    @pytest.mark.parametrize("email,expected", [
        ("user@example.com", True),
        ("test.user+tag@domain.co.uk", True),
        ("admin@sub.domain.io", True),
        ("notanemail", False),
        ("@domain.com", False),
        ("user@", False),
        ("user@domain", False),
        ("", False),
        ("   ", False),
    ])
    def test_is_valid_email(self, email, expected):
        assert is_valid_email(email) is expected

    @pytest.mark.parametrize("s,expected", [
        # HTML tags removed
        ("<script>alert('xss')</script>", "alert('xss')"),
        ("<b>bold</b>", "bold"),
        # void tags like <img> stripped entirely when no visible text
        ("<img src=x onerror=alert(1)>", ""),
        # SQL comments: `--` and `/* */` patterns stripped
        ("user--comment", "usercomment"),  # -- replaced with empty
        ("/* block comment */", ""),  # block comment stripped entirely
        # Control chars stripped (not replaced with space)
        ("hello\x00world", "helloworld"),
        ("line1\nline2\rline3", "line1line2line3"),
        ("tab\there", "tabhere"),
        # Normal string preserved
        ("normal text 123", "normal text 123"),
        ("中文内容", "中文内容"),
    ])
    def test_sanitize_string(self, s, expected):
        assert sanitize_string(s) == expected

    def test_sanitize_string_empty(self):
        assert sanitize_string("") == ""
        assert sanitize_string(None) is None  # type: ignore

    @pytest.mark.parametrize("value", [1, 42, 999999])
    def test_validate_id_valid(self, value):
        validate_id(value)
        validate_id(value, "ticket_id")

    @pytest.mark.parametrize("value,field", [
        (0, "id"),
        (-1, "user_id"),
        (None, "order_id"),  # type: ignore
        ("abc", "id"),  # type: ignore
    ])
    def test_validate_id_invalid_raises(self, value, field):
        with pytest.raises(ValueError, match=r"must be a positive integer"):
            validate_id(value, field)  # type: ignore


class TestAuthServiceInstantiation:
    """Test AuthService __init__ behavior."""

    def test_init_requires_secret_key(self):
        os.environ["JWT_SECRET_KEY"] = ""
        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set"):
            AuthService()

    def test_init_with_explicit_secret(self):
        svc = AuthService(secret_key="my-secret-123")
        assert svc.secret_key == "my-secret-123"

    def test_init_reads_from_env(self):
        os.environ["JWT_SECRET_KEY"] = "env-secret-456"
        svc = AuthService()
        assert svc.secret_key == "env-secret-456"
