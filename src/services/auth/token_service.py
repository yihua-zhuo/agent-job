"""Token service — handles refresh token lifecycle (P0: HttpOnly Cookie + revocation).

This module implements the P0 priority from issue #163:
- Refresh tokens stored in DB with hash
- HttpOnly cookie transport
- Full revocation support
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.refresh_token import RefreshTokenModel

ACCESS_TOKEN_EXPIRY_MINUTES = 10
REFRESH_TOKEN_EXPIRY_DAYS = 7


def generate_secure_token(length: int = 64) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """SHA-256 hash a token for storage (never store raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _as_utc(value: datetime) -> datetime:
    """Treat naive DB datetimes as UTC and preserve aware datetimes."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _tenant_from_raw_token(raw_token: str) -> int | None:
    tenant, _, _ = raw_token.partition(".")
    if not tenant:
        return None
    try:
        return int(tenant)
    except ValueError:
        return None


class TokenService:
    """Service for access/refresh token lifecycle management.

    Refresh tokens are stored hashed in the DB. The raw token is returned
    to the client via HttpOnly cookie and must be stored securely.
    """

    def __init__(
        self,
        session: AsyncSession,
        secret_key: str,
        access_token_expiry_minutes: int = ACCESS_TOKEN_EXPIRY_MINUTES,
    ):
        self.session = session
        self.secret_key = secret_key
        self.access_token_expiry_minutes = access_token_expiry_minutes

    def create_access_token(
        self,
        user_id: int,
        username: str,
        role: str,
        tenant_id: int | None = None,
    ) -> str:
        """Create a short-lived access token (stateless JWT, stored in memory client-side)."""
        now = datetime.now(UTC)
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "roles": [role] if role else [],
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.access_token_expiry_minutes),
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_access_token(self, token: str) -> dict | None:
        """Verify an access token. Returns payload or None if invalid/expired."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            if payload.get("type") != "access":
                return None
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    async def create_refresh_token(
        self,
        user_id: int,
        tenant_id: int,
        device_fingerprint: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
        expiry_days: int = REFRESH_TOKEN_EXPIRY_DAYS,
        expiry_seconds: int | None = None,
    ) -> tuple[str, RefreshTokenModel]:
        """Issue a new refresh token and store its hash.

        Returns (raw_token, model) — raw_token must be sent to client via HttpOnly cookie.
        """
        raw_token = f"{tenant_id}.{generate_secure_token()}"
        token_hash = hash_token(raw_token)
        expires_at = datetime.now(UTC) + (
            timedelta(seconds=max(1, expiry_seconds)) if expiry_seconds is not None else timedelta(days=expiry_days)
        )

        model = RefreshTokenModel(
            user_id=user_id,
            tenant_id=tenant_id,
            token_hash=token_hash,
            device_fingerprint=device_fingerprint,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
            revoked=False,
        )
        self.session.add(model)
        await self.session.flush()
        return raw_token, model

    async def verify_refresh_token(self, raw_token: str) -> RefreshTokenModel | None:
        """Verify a raw refresh token against stored hashes.

        Returns the RefreshTokenModel if valid and not revoked/expired.
        """
        tenant_id = _tenant_from_raw_token(raw_token)
        if tenant_id is None:
            return None
        token_hash = hash_token(raw_token)
        result = await self.session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.tenant_id == tenant_id,
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.revoked == False,  # noqa: E712
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        if _as_utc(model.expires_at) < datetime.now(UTC):
            return None
        return model

    async def revoke_refresh_token(self, raw_token: str) -> bool:
        """Revoke a refresh token (logout / force re-auth)."""
        tenant_id = _tenant_from_raw_token(raw_token)
        if tenant_id is None:
            return False
        token_hash = hash_token(raw_token)
        result = await self.session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.tenant_id == tenant_id,
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.revoked == False,  # noqa: E712
            )
            .values(revoked=True, revoked_at=datetime.now(UTC))
        )
        await self.session.flush()
        return result.rowcount > 0

    async def revoke_all_user_tokens(self, user_id: int, tenant_id: int) -> int:
        """Revoke all refresh tokens for a user (account-wide logout)."""
        result = await self.session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.tenant_id == tenant_id,
                RefreshTokenModel.revoked == False,  # noqa: E712
            )
            .values(revoked=True, revoked_at=datetime.now(UTC))
        )
        await self.session.flush()
        return result.rowcount

    async def get_active_sessions(self, user_id: int, tenant_id: int) -> list[RefreshTokenModel]:
        """List all active (non-revoked, non-expired) sessions for a user."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.tenant_id == tenant_id,
                RefreshTokenModel.revoked == False,  # noqa: E712
                RefreshTokenModel.expires_at > now,
            )
            .order_by(RefreshTokenModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def rotate_refresh_token(
        self,
        old_raw_token: str,
        device_fingerprint: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[str, RefreshTokenModel] | None:
        """Atomically rotate a refresh token: revoke old, issue new with remaining TTL.

        Used for "silent re-login" when the token is still valid.
        Returns (new_raw_token, new_model) or None if old token is invalid/expired.
        """
        tenant_id = _tenant_from_raw_token(old_raw_token)
        if tenant_id is None:
            return None
        token_hash = hash_token(old_raw_token)
        result = await self.session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.tenant_id == tenant_id,
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.revoked == False,  # noqa: E712
            )
        )
        old_model = result.scalar_one_or_none()
        if old_model is None:
            return None
        expires_at = _as_utc(old_model.expires_at)
        if expires_at < datetime.now(UTC):
            return None

        # Compute remaining TTL precisely so rotation never extends the original session.
        now = datetime.now(UTC)
        expiry_seconds = max(1, int((expires_at - now).total_seconds()))

        new_raw, new_model = await self.create_refresh_token(
            user_id=old_model.user_id,
            tenant_id=old_model.tenant_id,
            device_fingerprint=device_fingerprint or old_model.device_fingerprint,
            user_agent=user_agent or old_model.user_agent,
            ip_address=ip_address or old_model.ip_address,
            expiry_seconds=expiry_seconds,
        )

        old_model.revoked = True
        old_model.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return new_raw, new_model
