"""Authentication service for JWT token generation and verification."""
import jwt
from datetime import datetime, timedelta, timezone
from typing import cast, Optional
import os
import re


class AuthService:
    """Service for handling authentication operations including token generation and verification."""

    TOKEN_EXPIRY_HOURS = 24
    TOKEN_ISSUER = 'crm-agent-system'
    TOKEN_AUDIENCE = 'crm-api'

    def __init__(self, secret_key: str = None):
        """Initialize with the secret key for JWT operations.

        Args:
            secret_key: Secret key used for JWT encoding. Defaults to JWT_SECRET_KEY env var.
        """
        self.secret_key = secret_key or os.environ.get('JWT_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("JWT_SECRET_KEY must be set")

    def generate_token(self, user_id: int, username: str, role: str, tenant_id: int = None) -> str:
        """Generate a JWT token for a user.

        Args:
            user_id: The user's unique identifier.
            username: The user's username.
            role: The user's role name.
            tenant_id: Optional tenant ID for multi-tenancy.

        Returns:
            Encoded JWT token string.
        """
        now = datetime.now(timezone.utc)
        payload = {
            'sub': str(user_id),
            'user_id': user_id,
            'username': username,
            'role': role,
            'iss': self.TOKEN_ISSUER,
            'aud': self.TOKEN_AUDIENCE,
            'iat': now,
            'exp': now + timedelta(hours=self.TOKEN_EXPIRY_HOURS),
        }
        if tenant_id is not None:
            payload['tenant_id'] = tenant_id
        return jwt.encode(payload, self.secret_key, algorithm='HS256')

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
                algorithms=['HS256'],
                issuer=self.TOKEN_ISSUER,
                audience=self.TOKEN_AUDIENCE,
                options={'require': ['exp', 'iat', 'sub']}
            )
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
        tenant_id = payload.get('tenant_id')

        if not all([user_id, username, role]):
            return None

        # Type assertions since mypy can't infer from all() check
        return self.generate_token(
            cast(int, user_id),
            cast(str, username),
            cast(str, role),
            cast(Optional[int], tenant_id)
        )


def is_valid_email(email: str) -> bool:
    """Validate email format.
    
    Args:
        email: Email address to validate.
        
    Returns:
        True if valid email format, False otherwise.
    """
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
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
    s = re.sub(r'<[^>]*>', '', s)
    # Remove control characters
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    # Remove SQL comment patterns
    s = re.sub(r'--', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
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