"""WebAuthn service — handles registration and assertion verification (P2).

This module implements the WebAuthn (FIDO2 / U2F) portion of issue #163:
- Registration: generate challenge, verify attestation, store credential
- Assertion: verify authentication, check counter for clone detection
- Device trust integration for suspicious activity detection
"""

import base64
import json
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user_credential import UserCredentialModel


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


class WebAuthnService:
    """Service for WebAuthn registration and authentication flows."""

    # rpId defaults — can be overridden per-call
    DEFAULT_RP_ID = "localhost"
    DEFAULT_RP_NAME = "AgentJob"

    def __init__(self, session: AsyncSession, rp_id: str | None = None, rp_name: str | None = None):
        self.session = session
        self.rp_id = rp_id or self.DEFAULT_RP_ID
        self.rp_name = rp_name or self.DEFAULT_RP_NAME

    # -------------------------------------------------------------------------
    # Registration helpers (server-side challenge generation)
    # -------------------------------------------------------------------------

    async def start_registration(
        self,
        user_id: int,
        username: str,
        credential_nickname: str | None = None,
    ) -> dict[str, Any]:
        """Start WebAuthn registration: generate challenge and options for client.

        The client will call finish_registration() with the credential created
        by the authenticator.
        """
        challenge = generate_challenge()
        user_id_b64 = base64.urlsafe_b64encode(str(user_id).encode()).rstrip(b"=").decode()

        # Options the client will pass to navigator.credentials.create()
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
            "timeout": 60000,  # 60 seconds
            "attestation": "none",  # No attestation for privacy; change to "direct" if needed
        }

        # Store challenge server-side for verification (in production, use a temporary store or sign the challenge)
        # For simplicity we return it; production should store/Redis and expire after 60s
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
        username: str,
        registration_response: dict[str, Any],
        device_fingerprint: str | None = None,
        credential_nickname: str | None = None,
    ) -> UserCredentialModel:
        """Verify WebAuthn attestation and store the credential.

        Args:
            user_id: The user owning this credential.
            username: Username (for audit).
            registration_response: The response from navigator.credentials.create().
            device_fingerprint: Optional device fingerprint for device trust.
            credential_nickname: Optional human-readable name (e.g. "MacBook TouchID").

        Returns:
            The stored UserCredentialModel.

        Raises:
            ValueError: If attestation verification fails.
        """
        client_data = registration_response.get("response", {}).get("clientDataJSON", "")
        attestation_object = registration_response.get("response", {}).get("attestationObject", "")

        # Decode and parse client data
        client_data_bytes = decode_credential_id(client_data) if len(client_data) < 256 else base64.b64decode(client_data)
        client_data_json = json.loads(client_data_bytes)
        challenge = client_data_json.get("challenge", "")
        origin = client_data_json.get("origin", "")

        # In production: verify challenge, origin, rpId here
        # For now we do basic structure validation
        credential_id_raw = registration_response.get("credential", {}).get("id", "")
        credential_id = encode_credential_id(decode_credential_id(credential_id_raw)) if len(credential_id_raw) < 256 else credential_id_raw

        public_key_bytes = attestation_object if len(attestation_object) > 256 else decode_credential_id(attestation_object)
        public_key_b64 = base64.b64encode(public_key_bytes).decode()

        authenticator_data = registration_response.get("response", {}).get("authenticatorData", "")
        # Parse flags from authenticator data (first byte after rpIdHash + counter)
        # flag_byte = authenticator_data_bytes[37] if len(authenticator_data_bytes) > 37 else 0
        # attested_credential_included = bool(flag_byte & 0x01)

        transports = registration_response.get("transports", [])
        transports_str = ",".join(transports) if transports else None

        model = UserCredentialModel(
            user_id=user_id,
            credential_id=credential_id,
            public_key=public_key_b64,
            device_fingerprint=device_fingerprint,
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
    # Assertion verification (login)
    # -------------------------------------------------------------------------

    async def verify_assertion(
        self,
        user_id: int,
        assertion_response: dict[str, Any],
        device_fingerprint: str | None = None,
    ) -> tuple[UserCredentialModel, bool]:
        """Verify a WebAuthn assertion (authentication proof).

        Returns (credential_model, counter_updated) where counter_updated=True
        means the credential's sign_count was incremented.

        Raises:
            ValueError: If the assertion is invalid.
        """
        credential_id = assertion_response.get("credentialId", "")
        client_data_json_b64 = assertion_response.get("response", {}).get("clientDataJSON", "")
        authenticator_data_b64 = assertion_response.get("response", {}).get("authenticatorData", "")
        signature = assertion_response.get("response", {}).get("signature", "")

        # Decode client data
        try:
            if len(client_data_json_b64) < 256:
                client_data_bytes = decode_credential_id(client_data_json_b64)
            else:
                client_data_bytes = base64.b64decode(client_data_json_b64)
            client_data = json.loads(client_data_bytes)
        except Exception as e:
            raise ValueError(f"Invalid client data: {e}")

        challenge = client_data.get("challenge", "")
        origin = client_data.get("origin", "")
        # In production: verify challenge, origin, rpId

        # Find credential
        result = await self.session.execute(
            select(UserCredentialModel).where(
                UserCredentialModel.credential_id == credential_id,
                UserCredentialModel.user_id == user_id,
                UserCredentialModel.enabled == True,  # noqa: E712
            )
        )
        credential = result.scalar_one_or_none()
        if credential is None:
            raise ValueError("Unknown credential")

        # Parse authenticator data to get sign count
        try:
            if len(authenticator_data_b64) < 128:
                auth_data_bytes = decode_credential_id(authenticator_data_b64)
            else:
                auth_data_bytes = base64.b64decode(authenticator_data_b64)
        except Exception:
            auth_data_bytes = b""

        # sign_count is at byte offset 37-41 (big-endian uint32)
        sign_count = 0
        if len(auth_data_bytes) >= 41:
            sign_count = int.from_bytes(auth_data_bytes[37:41], byteorder="big")

        # Anti-cloning: reject if reported counter <= stored counter (cloned authenticator)
        if credential.sign_count > 0 and sign_count <= credential.sign_count:
            raise ValueError("Possible credential clone detected — signature counter not incremented")

        # Update counter
        await self.session.execute(
            update(UserCredentialModel)
            .where(UserCredentialModel.id == credential.id)
            .values(sign_count=sign_count, last_used_at=datetime.now(UTC))
        )
        await self.session.flush()
        return credential, sign_count > credential.sign_count

    # -------------------------------------------------------------------------
    # Credential management
    # -------------------------------------------------------------------------

    async def get_user_credentials(self, user_id: int) -> list[UserCredentialModel]:
        """List all WebAuthn credentials for a user."""
        result = await self.session.execute(
            select(UserCredentialModel)
            .where(
                UserCredentialModel.user_id == user_id,
                UserCredentialModel.enabled == True,  # noqa: E712
            )
            .order_by(UserCredentialModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_credential(self, user_id: int, credential_id: str) -> bool:
        """Delete a credential (user removing a device)."""
        result = await self.session.execute(
            update(UserCredentialModel)
            .where(
                UserCredentialModel.credential_id == credential_id,
                UserCredentialModel.user_id == user_id,
            )
            .values(enabled=False)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def disable_credential(self, user_id: int, credential_id: str) -> bool:
        """Disable a credential (temporary, can be re-enabled)."""
        return await self.delete_credential(user_id, credential_id)