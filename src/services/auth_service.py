"""Authentication service for JWT token generation and verification."""

import re
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import UserModel
from pkg.errors.app_exceptions import (
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def sanitize_string(value: str) -> str | None:
    """Remove HTML tags, control characters, and SQL comment patterns."""
    if value is None:
        return None
    # Strip HTML tags (keep content inside)
    s = re.sub(r"<[^>]*>", "", value)
    # Strip block comments
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    # Strip control chars
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    # Strip SQL comment marker
    s = s.replace("--", "")
    # Trim leading/trailing whitespace (but preserve internal spaces)
    return s.strip()


def validate_id(value, field_name: str = "id") -> None:
    """Validate value is a positive integer."""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


class AuthService:
    """Service for handling authentication operations including token generation and verification."""

    TOKEN_EXPIRY_HOURS = 24

    def __init__(self, session: AsyncSession, secret_key: str | None = None):
        """Initialize AuthService.

        Args:
            session: DB session.
            secret_key: Secret key for JWT encoding. Falls back to JWT_SECRET_KEY env var.

        Raises:
            ValueError: If neither secret_key nor JWT_SECRET_KEY env var is set.
        """
        import os

        key = secret_key if secret_key is not None else os.environ.get("JWT_SECRET_KEY")
        if not key:
            raise ValueError("JWT_SECRET_KEY must be set")
        self.secret_key = key
        self.session = session

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against a bcrypt hash."""
        if not hashed:
            return False
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            return False

    def generate_token(self, user_id: int, username: str, role: str, tenant_id: int = None) -> str:
        """Generate a JWT token for a user.

        Args:
            user_id: The user's unique identifier.
            username: The user's username.
            role: The user's role name.
            tenant_id: Optional tenant ID to include in payload.

        Returns:
            Encoded JWT token string.
        """
        now = datetime.now(UTC)
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=self.TOKEN_EXPIRY_HOURS),
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> dict | None:
        """Verify and decode a JWT token.

        Args:
            token: The JWT token string to verify.

        Returns:
            Decoded payload dict if valid, None if invalid or expired.
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    async def create_token(self, user_id: int, username: str, role: str, tenant_id: int = None) -> str:
        """Async alias for generate_token."""
        return self.generate_token(user_id, username, role, tenant_id=tenant_id)

    async def authenticate_user(self, username: str, password: str) -> UserModel:
        """Authenticate a user by username and password.

        Returns:
            UserModel if credentials are valid.

        Raises:
            UnauthorizedException: If credentials are invalid.
        """
        result = await self.session.execute(select(UserModel).where(UserModel.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            raise UnauthorizedException("Invalid credentials")
        if not self.verify_password(password, user.password_hash or ""):
            raise UnauthorizedException("Invalid credentials")
        return user

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "user",
        tenant_id: int = 0,
        full_name: str | None = None,
    ) -> UserModel:
        """Register a new user via UserService."""
        from services.user_service import UserService

        svc = UserService(self.session)
        return await svc.create_user(
            username=username,
            email=email,
            password=password,
            tenant_id=tenant_id,
            role=role,
            full_name=full_name,
        )

    async def get_current_user(self, token: str) -> UserModel:
        """Return UserModel for a valid token.

        Raises:
            UnauthorizedException: If token is invalid.
            NotFoundException: If user not found.
        """
        payload = self.verify_token(token)
        if not payload:
            raise UnauthorizedException("Invalid or expired token")
        user_id = payload.get("user_id")
        if not user_id:
            raise UnauthorizedException("Invalid token payload")
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundException("用户")
        return user

    async def revoke_token(self, token: str) -> bool:
        """Revoke a token by inserting it into the revoked tokens table.

        Raises:
            UnauthorizedException: If token is invalid.
        """
        payload = self.verify_token(token)
        if not payload:
            raise UnauthorizedException("Invalid or expired token")
        if not self.session:
            return True
        jti = payload.get("jti") or f"{payload.get('user_id')}-{payload.get('exp')}"
        await self.session.execute(
            text("INSERT INTO revoked_tokens (jti, expires_at) VALUES (:jti, :expires_at)"),
            {"jti": jti, "expires_at": datetime.fromtimestamp(payload.get("exp", 0), tz=UTC)},
        )
        await self.session.commit()
        return True

    async def refresh_token(self, old_token: str) -> str:
        """Refresh an existing token with a new expiry time.

        Args:
            old_token: The current JWT token to refresh.

        Returns:
            New JWT token string.

        Raises:
            UnauthorizedException: If old token is invalid or missing required fields.
        """
        payload = self.verify_token(old_token)
        if not payload:
            raise UnauthorizedException("Invalid or expired token")
        user_id = payload.get("user_id")
        username = payload.get("username")
        role = payload.get("role")
        tenant_id = payload.get("tenant_id")
        if not all([user_id, username, role]):
            raise UnauthorizedException("Invalid token payload")
        return self.generate_token(user_id, username, role, tenant_id=tenant_id)
