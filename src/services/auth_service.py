"""Authentication service for JWT token generation and verification."""
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional


class AuthService:
    """Service for handling authentication operations including token generation and verification."""

    TOKEN_EXPIRY_HOURS = 24

    def __init__(self, secret_key: str):
        """Initialize with the secret key for JWT operations.

        Args:
            secret_key: Secret key used for JWT encoding.
        """
        self.secret_key = secret_key

    def generate_token(self, user_id: int, username: str, role: str) -> str:
        """Generate a JWT token for a user.

        Args:
            user_id: The user's unique identifier.
            username: The user's username.
            role: The user's role name.

        Returns:
            Encoded JWT token string.
        """
        now = datetime.now(timezone.utc)
        payload = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'iat': now,
            'exp': now + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode a JWT token.

        Args:
            token: The JWT token string to verify.

        Returns:
            Decoded payload dict if valid, None if invalid or expired.
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def refresh_token(self, old_token: str) -> Optional[str]:
        """Refresh an existing token with a new expiry time.

        Args:
            old_token: The current JWT token to refresh.

        Returns:
            New JWT token if old token is valid, None otherwise.
        """
        payload = self.verify_token(old_token)
        if not payload:
            return None

        user_id = payload.get('user_id')
        username = payload.get('username')
        role = payload.get('role')

        if not all([user_id, username, role]):
            return None

        return self.generate_token(user_id, username, role)
