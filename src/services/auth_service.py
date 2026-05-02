"""Authentication service for JWT token generation and verification - async PostgreSQL via SQLAlchemy."""
import jwt
import bcrypt
import re
import os
from datetime import datetime, timedelta, UTC
from typing import cast, Optional, Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


from db.connection import get_db_session


class AuthService:
    """Service for handling authentication operations including token generation and verification."""

    TOKEN_EXPIRY_HOURS = 24
    TOKEN_ISSUER = "crm-agent-system"
    TOKEN_AUDIENCE = "crm-api"

    def __init__(self, session: AsyncSession = None, secret_key: Optional[str] = None):
        self._session_context = None
        if session is None:
            try:
                context = get_db_session()
                # async generator — only use in async context; otherwise leave session=None
                session = None
            except Exception:
                session = None
        self.session = session
        self.secret_key: str = cast(str, secret_key) or os.environ["JWT_SECRET_KEY"]
        if not self.secret_key:
            raise ValueError("JWT_SECRET_KEY must be set")

    def generate_token(
        self, user_id: int, username: str, role: str, tenant_id: int = None
    ) -> str:
        """Generate a JWT token for a user.

        Args:
            user_id: The user's unique identifier.
            username: The user's username.
            role: The user's role name.
            tenant_id: Optional tenant ID for multi-tenancy.

        Returns:
            Encoded JWT token string.
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "user_id": user_id,
            "username": username,
            "role": role,
            "iss": self.TOKEN_ISSUER,
            "aud": self.TOKEN_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(hours=self.TOKEN_EXPIRY_HOURS),
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate a user by username and password.

        Args:
            username: The username to authenticate.
            password: The plain-text password to verify.

        Returns:
            User dict if authentication succeeds, None otherwise.
        """
        async with self.session:
            result = await self.session.execute(
                text(
                    """
                    SELECT id, tenant_id, username, email, password_hash, role,
                           status, full_name, bio, created_at, updated_at
                    FROM users
                    WHERE username = :username
                    LIMIT 1
                    """
                ),
                {"username": username},
            )
            row = result.fetchone()
            if row is None:
                return None
        if not self.verify_password(password, row[4]):
            return None

        return {
            "id": row[0],
            "tenant_id": row[1],
            "username": row[2],
            "email": row[3],
            "role": row[5],
            "status": row[6],
            "full_name": row[7],
            "bio": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
            "updated_at": row[10].isoformat() if row[10] else None,
        }

    async def create_token(self, user_id: int, username: str, role: str, tenant_id: int = None) -> str:
        """Create a JWT token for an existing user.

        Alias for generate_token for backward compatibility.
        """
        return self.generate_token(user_id, username, role, tenant_id)

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode a JWT token.

        Args:
            token: The JWT token string to verify.

        Returns:
            Decoded payload dict if valid, None if invalid or expired.
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                issuer=self.TOKEN_ISSUER,
                audience=self.TOKEN_AUDIENCE,
                options={"require": ["exp", "iat", "sub"]},
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "user",
        tenant_id: int = 0,
        full_name: str = None,
        **kwargs,
    ) -> Dict:
        """Create a new user in the database.

        Args:
            username: Unique username.
            email: Unique email address.
            password: Plain-text password (will be hashed).
            role: User role. Defaults to 'user'.
            tenant_id: Tenant ID for multi-tenancy. Defaults to 0.
            full_name: Optional full name.

        Returns:
            Dict with 'success', 'data', and 'message' keys.
        """
        from services.user_service import UserService

        user_svc = UserService(self.session)
        return await user_svc.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            tenant_id=tenant_id,
            full_name=full_name,
            **kwargs,
        )

    async def get_current_user(self, token: str) -> Optional[Dict]:
        """Get the current user from a JWT token.

        Args:
            token: The JWT token string.

        Returns:
            User dict if the token is valid, None otherwise.
        """
        payload = self.verify_token(token)
        if payload is None:
            return None

        user_id = payload.get("user_id")
        if not user_id:
            return None

        async with self.session:
            result = await self.session.execute(
                text(
                    """
                    SELECT id, tenant_id, username, email, role, status,
                           full_name, bio, created_at, updated_at
                    FROM users
                    WHERE id = :user_id
                    LIMIT 1
                    """
                ),
                {"user_id": user_id},
            )
            row = result.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "tenant_id": row[1],
                "username": row[2],
                "email": row[3],
                "role": row[4],
                "status": row[5],
                "full_name": row[6],
                "bio": row[7],
                "created_at": row[8].isoformat() if row[8] else None,
                "updated_at": row[9].isoformat() if row[9] else None,
            }

    async def refresh_token(self, old_token: str) -> Optional[str]:
        """Refresh an existing token with a new expiry time.

        Args:
            old_token: The current JWT token to refresh.

        Returns:
            New JWT token if old token is valid, None otherwise.
        """
        payload = self.verify_token(old_token)
        if not payload:
            return None

        user_id = payload.get("user_id")
        username = payload.get("username")
        role = payload.get("role")
        tenant_id = payload.get("tenant_id")

        if not all([user_id, username, role]):
            return None

        return self.generate_token(
            cast(int, user_id),
            cast(str, username),
            cast(str, role),
            cast(Optional[int], tenant_id),
        )

    async def revoke_token(self, token: str) -> bool:
        """Revoke a token by storing it in a blocklist.

        Args:
            token: The JWT token string to revoke.

        Returns:
            True if the token was successfully revoked, False otherwise.
        """
        payload = self.verify_token(token)
        if payload is None:
            return False

        jti = payload.get("jti") or payload.get("sub")
        exp = payload.get("exp")
        async with self.session:
            await self.session.execute(
                text(
                    """
                    INSERT INTO revoked_tokens (jti, revoked_at, expires_at)
                    VALUES (:jti, :revoked_at, :exp)
                    ON CONFLICT (jti) DO NOTHING
                    """
                ),
                {
                    "jti": str(jti),
                    "revoked_at": datetime.now(UTC),
                    "exp": datetime.utcfromtimestamp(exp) if exp else None,
                },
            )
            await self.session.commit()
        return True

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plain-text password using bcrypt.

        Args:
            password: The plain-text password to hash.

        Returns:
            The bcrypt hash string.
        """
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a plain-text password against a bcrypt hash.

        Args:
            password: The plain-text password.
            password_hash: The bcrypt hash to verify against.

        Returns:
            True if the password matches, False otherwise.
        """
        if not password_hash:
            return False
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except (ValueError, TypeError):
            return False


def is_valid_email(email: str) -> bool:
    """Validate email format.

    Args:
        email: Email address to validate.

    Returns:
        True if valid email format, False otherwise.
    """
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def sanitize_string(s: str) -> str:
    """Sanitize string to prevent XSS and injection attacks.

    Args:
        s: String to sanitize.

    Returns:
        Sanitized string safe for use in responses and queries.
    """
    if not s:
        return s
    # Remove HTML tags
    s = re.sub(r"<[^>]*>", "", s)
    # Remove control characters
    s = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", s)
    # Remove SQL comment patterns
    s = re.sub(r"--", "", s)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    return s.strip()


def validate_id(id_value: int, field_name: str = "id") -> None:
    """Validate that an ID is a positive integer.

    Args:
        id_value: The ID value to validate.
        field_name: Name of the field for error messages.

    Raises:
        ValueError: If the ID is not a positive integer.
    """
    if not isinstance(id_value, int) or id_value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
