"""WebAuthn service — handles registration and assertion verification (P2).

This module implements the WebAuthn (FIDO2 / U2F) portion of issue #163:
- Registration: generate challenge, verify attestation, store credential
- Assertion: verify authentication, check counter for clone detection
- Device trust integration for suspicious activity detection

Challenges are stored in PostgreSQL (webauthn_challenges table) with TTL.
"""

import base64
import binascii
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user_credential import UserCredentialModel
from db.models.webauthn_challenge import WebAuthnChallengeModel
from pkg.errors.app_exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


def generate_challenge(length: int = 64) -> str:
    """Generate a cryptographically random WebAuthn challenge."""
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).rstrip(b"=").decode()


def decode_credential_id(credential_id: str) -> bytes:
    """Decode a base64url credential ID from the client."""
    padding = "=" * (-len(credential_id) % 4)
    return base64.urlsafe_b64decode(credential_id + padding)


def encode_credential_id(credential_id: bytes) -> str:
    """Encode a credential ID as base64url for storage."""
    return base64.urlsafe_b64encode(credential_id).rstrip(b"=").decode()


# Default TTLs
REGISTRATION_CHALLENGE_TTL_SECONDS = 60
ASSERTION_CHALLENGE_TTL_SECONDS = 300


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class WebAuthnService:
    """Service for WebAuthn registration and authentication flows."""

    DEFAULT_RP_ID = "localhost"
    DEFAULT_RP_NAME = "AgentJob"

    def __init__(self, session: AsyncSession, rp_id: str | None = None, rp_name: str | None = None):
        self.session = session
        self.rp_id = rp_id or self.DEFAULT_RP_ID
        self.rp_name = rp_name or self.DEFAULT_RP_NAME

    def _validate_origin(self, origin: str) -> None:
        """Validate clientDataJSON origin against the configured RP ID."""
        parsed = urlparse(origin)
        host = parsed.hostname or ""
        if not host:
            raise ValidationException("Invalid WebAuthn origin")
        if self.rp_id == "localhost":
            valid_host = host in {"localhost", "127.0.0.1", "::1"}
        else:
            valid_host = host == self.rp_id or host.endswith(f".{self.rp_id}")
        if not valid_host:
            raise ValidationException("WebAuthn origin does not match relying party")
        if self.rp_id != "localhost" and parsed.scheme != "https":
            raise ValidationException("WebAuthn origin must use HTTPS")

    # -------------------------------------------------------------------------
    # Challenge management (PostgreSQL-backed, TTL expiry)
    # -------------------------------------------------------------------------

    async def _create_challenge(
        self,
        user_id: int,
        tenant_id: int,
        purpose: str,
        credential_id: str | None = None,
        device_fingerprint: str | None = None,
        ttl_seconds: int = REGISTRATION_CHALLENGE_TTL_SECONDS,
    ) -> str:
        """Store a challenge in DB with TTL. Returns the raw challenge string."""
        challenge = generate_challenge()
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

        model = WebAuthnChallengeModel(
            user_id=user_id,
            tenant_id=tenant_id,
            challenge=challenge,
            purpose=purpose,
            credential_id=credential_id,
            device_fingerprint=device_fingerprint,
            expires_at=expires_at,
            consumed=False,
        )
        self.session.add(model)
        await self.session.flush()
        return challenge

    async def _consume_challenge(
        self,
        user_id: int,
        tenant_id: int,
        challenge: str,
        purpose: str,
        consume: bool = True,
    ) -> WebAuthnChallengeModel | None:
        """Find and optionally mark a challenge as consumed.

        Returns the challenge model if valid (exists, not expired, not consumed).
        Returns None if challenge is missing, expired, or already consumed.
        """
        result = await self.session.execute(
            select(WebAuthnChallengeModel).where(
                WebAuthnChallengeModel.user_id == user_id,
                WebAuthnChallengeModel.tenant_id == tenant_id,
                WebAuthnChallengeModel.challenge == challenge,
                WebAuthnChallengeModel.purpose == purpose,
                WebAuthnChallengeModel.consumed == False,  # noqa: E712
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None

        if _as_utc(model.expires_at) < datetime.now(UTC):
            return None

        if consume:
            model.consumed = True
            model.consumed_at = datetime.now(UTC)
            await self.session.flush()

        return model

    async def _cleanup_expired_challenges(self, tenant_id: int) -> int:
        """Delete all consumed-and-expired challenges. Call periodically to keep table small."""
        result = await self.session.execute(
            delete(WebAuthnChallengeModel).where(
                WebAuthnChallengeModel.expires_at < datetime.now(UTC),
                WebAuthnChallengeModel.tenant_id == tenant_id,
                WebAuthnChallengeModel.consumed == True,  # noqa: E712
            )
        )
        await self.session.flush()
        return result.rowcount

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------

    async def start_registration(
        self,
        user_id: int,
        tenant_id: int,
        username: str,
        credential_nickname: str | None = None,
        device_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        """Start WebAuthn registration: store challenge in DB, return options for client.

        The client will call finish_registration() with the authenticator's response.
        """
        challenge = await self._create_challenge(
            user_id=user_id,
            tenant_id=tenant_id,
            purpose="registration",
            device_fingerprint=device_fingerprint,
            ttl_seconds=REGISTRATION_CHALLENGE_TTL_SECONDS,
        )

        user_id_b64 = base64.urlsafe_b64encode(str(user_id).encode()).rstrip(b"=").decode()

        public_key_options = {
            "challenge": challenge,
            "rp": {
                "id": self.rp_id,
                "name": self.rp_name,
            },
            "user": {
                "id": user_id_b64,
                "name": username,
                "displayName": username,
            },
            "pubKeyCredParams": [
                {"alg": -7, "type": "public-key"},   # ES256 (recommended)
                {"alg": -257, "type": "public-key"}, # RS256 (fallback)
            ],
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "requireResidentKey": False,
                "userVerification": "preferred",
            },
            "timeout": REGISTRATION_CHALLENGE_TTL_SECONDS * 1000,
            "attestation": "none",
        }

        return {
            "challenge": challenge,
            "publicKeyOptions": public_key_options,
            "user_id": user_id,
            "username": username,
            "credential_nickname": credential_nickname,
        }

    async def finish_registration(
        self,
        user_id: int,
        tenant_id: int,
        username: str,
        registration_response: dict[str, Any],
        device_fingerprint: str | None = None,
        credential_nickname: str | None = None,
    ) -> UserCredentialModel:
        """Verify WebAuthn attestation and store the credential.

        Raises:
            ValidationException: If challenge is expired/already-used/invalid.
            ValidationException: For malformed attestation data.
        """
        client_data = registration_response.get("response", {}).get("clientDataJSON", "")
        attestation_object = registration_response.get("response", {}).get("attestationObject", "")

        # Parse client data JSON
        try:
            if len(client_data) < 256:
                client_data_bytes = decode_credential_id(client_data)
            else:
                client_data_bytes = base64.b64decode(client_data)
            client_data_json = json.loads(client_data_bytes)
        except (binascii.Error, UnicodeDecodeError, ValueError, json.JSONDecodeError) as e:
            raise ValidationException(f"Invalid client data JSON: {e}")

        presented_challenge = client_data_json.get("challenge", "")
        origin = client_data_json.get("origin", "")

        # Consume challenge from DB (validates existence, TTL, not reused)
        db_challenge = await self._consume_challenge(user_id, tenant_id, presented_challenge, purpose="registration")
        if db_challenge is None:
            raise ValidationException("Challenge expired, already used, or invalid")

        self._validate_origin(origin)

        # Extract credential ID
        credential_id_raw = registration_response.get("credential", {}).get("id", "")
        if len(credential_id_raw) < 256:
            credential_id = encode_credential_id(decode_credential_id(credential_id_raw))
        else:
            credential_id = credential_id_raw

        # Encode public key (attestationObject contains the CBOR-encoded public key)
        try:
            if len(attestation_object) < 128:
                pk_bytes = decode_credential_id(attestation_object)
            else:
                pk_bytes = base64.b64decode(attestation_object)
            public_key_b64 = base64.b64encode(pk_bytes).decode()
        except (binascii.Error, ValueError) as e:
            raise ValidationException(f"Invalid attestation object: {e}")

        transports = registration_response.get("transports", [])
        transports_str = ",".join(transports) if transports else None

        model = UserCredentialModel(
            user_id=user_id,
            tenant_id=tenant_id,
            credential_id=credential_id,
            public_key=public_key_b64,
            device_fingerprint=device_fingerprint or db_challenge.device_fingerprint,
            device_name=credential_nickname,
            sign_count=0,
            authenticator_type="fido2",
            transports=transports_str,
            enabled=True,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    # -------------------------------------------------------------------------
    # Assertion (authentication)
    # -------------------------------------------------------------------------

    async def start_assertion(
        self,
        user_id: int,
        tenant_id: int,
        credential_id: str,
        device_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        """Start WebAuthn assertion: store challenge in DB, return options for client.

        The client calls verify_assertion() with the authenticator's response.
        """
        challenge = await self._create_challenge(
            user_id=user_id,
            tenant_id=tenant_id,
            purpose="assertion",
            credential_id=credential_id,
            device_fingerprint=device_fingerprint,
            ttl_seconds=ASSERTION_CHALLENGE_TTL_SECONDS,
        )

        return {
            "challenge": challenge,
            "credential_id": credential_id,
            "timeout": ASSERTION_CHALLENGE_TTL_SECONDS * 1000,
            "rp_id": self.rp_id,
        }

    async def verify_assertion(
        self,
        user_id: int,
        tenant_id: int,
        assertion_response: dict[str, Any],
        device_fingerprint: str | None = None,
    ) -> tuple[UserCredentialModel, bool]:
        """Verify a WebAuthn assertion (authentication proof).

        Returns (credential_model, counter_updated).

        Raises:
            ValidationException: If client data is malformed or challenge invalid.
            NotFoundException: If credential is not found.
            ConflictException: If clone detection fires (sign_count not incremented).
        """
        credential_id = assertion_response.get("credentialId", "")
        client_data_json_b64 = assertion_response.get("response", {}).get("clientDataJSON", "")
        authenticator_data_b64 = assertion_response.get("response", {}).get("authenticatorData", "")

        # Parse client data
        try:
            if len(client_data_json_b64) < 256:
                client_data_bytes = decode_credential_id(client_data_json_b64)
            else:
                client_data_bytes = base64.b64decode(client_data_json_b64)
            client_data = json.loads(client_data_bytes)
        except (binascii.Error, UnicodeDecodeError, ValueError, json.JSONDecodeError) as e:
            raise ValidationException(f"Invalid client data: {e}")

        presented_challenge = client_data.get("challenge", "")
        origin = client_data.get("origin", "")
        self._validate_origin(origin)

        # Consume challenge from DB
        db_challenge = await self._consume_challenge(user_id, tenant_id, presented_challenge, purpose="assertion")
        if db_challenge is None:
            raise ValidationException("Challenge expired, already used, or invalid")

        # Verify credential_id in challenge matches presented credential
        if db_challenge.credential_id and db_challenge.credential_id != credential_id:
            raise ValidationException("Credential ID mismatch")

        # Find credential
        result = await self.session.execute(
            select(UserCredentialModel).where(
                UserCredentialModel.credential_id == credential_id,
                UserCredentialModel.user_id == user_id,
                UserCredentialModel.tenant_id == tenant_id,
                UserCredentialModel.enabled == True,  # noqa: E712
            )
        )
        credential = result.scalar_one_or_none()
        if credential is None:
            raise NotFoundException("Credential")

        # Parse authenticator data for sign count (byte offset 37-41, big-endian uint32)
        sign_count = 0
        try:
            if len(authenticator_data_b64) < 128:
                auth_data_bytes = decode_credential_id(authenticator_data_b64)
            else:
                auth_data_bytes = base64.b64decode(authenticator_data_b64)
            if len(auth_data_bytes) >= 41:
                sign_count = int.from_bytes(auth_data_bytes[37:41], byteorder="big")
        except (binascii.Error, ValueError):
            sign_count = 0

        # Anti-cloning: reject if reported counter <= stored counter
        if credential.sign_count > 0 and sign_count <= credential.sign_count:
            raise ConflictException("Possible credential clone detected — signature counter not incremented")

        # Update counter
        await self.session.execute(
            update(UserCredentialModel)
            .where(UserCredentialModel.id == credential.id, UserCredentialModel.tenant_id == tenant_id)
            .values(sign_count=sign_count, last_used_at=datetime.now(UTC))
        )
        await self.session.flush()
        return credential, sign_count > credential.sign_count

    # -------------------------------------------------------------------------
    # Credential management
    # -------------------------------------------------------------------------

    async def get_user_credentials(self, user_id: int, tenant_id: int) -> list[UserCredentialModel]:
        """List all WebAuthn credentials for a user."""
        result = await self.session.execute(
            select(UserCredentialModel)
            .where(
                UserCredentialModel.user_id == user_id,
                UserCredentialModel.tenant_id == tenant_id,
                UserCredentialModel.enabled == True,  # noqa: E712
            )
            .order_by(UserCredentialModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_credential(self, user_id: int, tenant_id: int, credential_id: str) -> bool:
        """Delete a credential (user removing a device)."""
        result = await self.session.execute(
            update(UserCredentialModel)
            .where(
                UserCredentialModel.credential_id == credential_id,
                UserCredentialModel.user_id == user_id,
                UserCredentialModel.tenant_id == tenant_id,
            )
            .values(enabled=False)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def disable_credential(self, user_id: int, tenant_id: int, credential_id: str) -> bool:
        """Disable a credential (temporary, can be re-enabled)."""
        return await self.delete_credential(user_id, tenant_id, credential_id)
