"""Authentication middleware for JWT token verification and role-based access control."""
import jwt
from functools import wraps
from flask import request, g


class AuthMiddleware:
    """Middleware for handling JWT authentication and role verification."""

    def __init__(self, secret_key: str):
        """Initialize with the secret key for JWT verification.

        Args:
            secret_key: Secret key used for JWT encoding/decoding.
        """
        self.secret_key = secret_key

    def verify_token(self, token: str) -> dict | None:
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

    def require_auth(self, f):
        """Decorator that requires a valid JWT token for the endpoint.

        The decoded token payload is stored in flask.g.current_user.
        """
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not token:
                return {'error': 'No token'}, 401
            payload = self.verify_token(token)
            if not payload:
                return {'error': 'Invalid token'}, 401
            g.current_user = payload
            return f(*args, **kwargs)
        return decorated

    def require_role(self, *roles):
        """Decorator that requires the user to have one of the specified roles.

        Must be used after require_auth decorator.

        Args:
            *roles: Variable number of role names that are allowed access.
        """
        def decorator(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                if not hasattr(g, 'current_user'):
                    return {'error': 'Not authenticated'}, 401
                user_role = g.current_user.get('role')
                if user_role not in roles:
                    return {'error': 'Forbidden'}, 403
                return f(*args, **kwargs)
            return decorated
        return decorator
