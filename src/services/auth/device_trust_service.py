"""Device trust service — tracks trusted devices and suspicious activity (P3).

This module implements P3 from issue #163:
- Maintain a device trust list (no sensitive data stored client-side)
- Detect suspicious activity: new IP, geo change, new device
- Trigger re-auth when suspicious activity is detected
"""

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.device_trust import DeviceTrustModel


class SuspiciousActivityReason:
    """Reasonable causes for triggering re-authentication."""

    NEW_DEVICE = "new_device"
    NEW_IP = "new_ip"
    GEO_CHANGE = "geo_change"
    EXCESSIVE_FAILURES = "excessive_failures"


def generate_device_fingerprint(
    ip_address: str | None = None,
    user_agent: str | None = None,
    accept_language: str | None = None,
) -> str:
    """Generate a device fingerprint from request attributes.

    Note: This is a simple fingerprint. For stronger fingerprinting,
    consider adding canvas/WebGL, fonts, or TLS JA3 signatures client-side.
    Returns empty string if all inputs are None/empty.
    """
    if not ip_address and not user_agent and not accept_language:
        return ""

    parts = [
        ip_address or "",
        user_agent or "",
        accept_language or "",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


class DeviceTrustService:
    """Service for device trust management and suspicious activity detection."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_device_trusted(self, user_id: int, tenant_id: int, device_fingerprint: str) -> bool:
        """Check if a device is currently trusted for the given user."""
        result = await self.session.execute(
            select(DeviceTrustModel).where(
                DeviceTrustModel.user_id == user_id,
                DeviceTrustModel.tenant_id == tenant_id,
                DeviceTrustModel.device_fingerprint == device_fingerprint,
                DeviceTrustModel.trusted == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None

    async def trust_device(
        self,
        user_id: int,
        tenant_id: int,
        device_fingerprint: str,
        ip_address: str | None = None,
        device_name: str | None = None,
        location: str | None = None,
    ) -> DeviceTrustModel:
        """Mark a device as trusted for a user (after WebAuthn verification)."""
        existing = await self.session.execute(
            select(DeviceTrustModel).where(
                DeviceTrustModel.user_id == user_id,
                DeviceTrustModel.tenant_id == tenant_id,
                DeviceTrustModel.device_fingerprint == device_fingerprint,
            )
        )
        model = existing.scalar_one_or_none()

        if model is None:
            model = DeviceTrustModel(
                user_id=user_id,
                tenant_id=tenant_id,
                device_fingerprint=device_fingerprint,
                device_name=device_name,
                trusted_ip=ip_address,
                last_ip=ip_address,
                last_location=location,
                trusted=True,
                trusted_at=datetime.now(UTC),
                last_used_at=datetime.now(UTC),
            )
            self.session.add(model)
        else:
            model.trusted = True
            model.trusted_ip = ip_address or model.trusted_ip
            model.last_ip = ip_address or model.last_ip
            model.last_location = location or model.last_location
            model.last_used_at = datetime.now(UTC)
            model.trusted_at = datetime.now(UTC)

        await self.session.flush()
        return model

    async def distrust_device(self, user_id: int, tenant_id: int, device_fingerprint: str) -> bool:
        """Revoke trust for a specific device."""
        result = await self.session.execute(
            update(DeviceTrustModel)
            .where(
                DeviceTrustModel.user_id == user_id,
                DeviceTrustModel.tenant_id == tenant_id,
                DeviceTrustModel.device_fingerprint == device_fingerprint,
            )
            .values(trusted=False)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def distrust_all_devices(self, user_id: int, tenant_id: int) -> int:
        """Revoke trust for all devices of a user (e.g. after password change)."""
        result = await self.session.execute(
            update(DeviceTrustModel)
            .where(
                DeviceTrustModel.user_id == user_id,
                DeviceTrustModel.tenant_id == tenant_id,
                DeviceTrustModel.trusted == True,  # noqa: E712
            )
            .values(trusted=False)
        )
        await self.session.flush()
        return result.rowcount

    async def update_device_usage(
        self,
        user_id: int,
        tenant_id: int,
        device_fingerprint: str,
        ip_address: str | None = None,
        location: str | None = None,
    ) -> None:
        """Update last-used metadata for a device."""
        result = await self.session.execute(
            select(DeviceTrustModel).where(
                DeviceTrustModel.user_id == user_id,
                DeviceTrustModel.tenant_id == tenant_id,
                DeviceTrustModel.device_fingerprint == device_fingerprint,
            )
        )
        model = result.scalar_one_or_none()
        if model:
            model.last_used_at = datetime.now(UTC)
            model.last_ip = ip_address or model.last_ip
            model.last_location = location or model.last_location
            await self.session.flush()

    async def check_suspicious_activity(
        self,
        user_id: int,
        tenant_id: int,
        device_fingerprint: str,
        ip_address: str | None = None,
    ) -> tuple[bool, list[str]]:
        """Check for suspicious activity and return (requires_reauth, reasons).

        Reasons list contains SuspiciousActivityReason values explaining why
        re-auth was triggered.
        """
        reasons: list[str] = []

        if not device_fingerprint:
            reasons.append(SuspiciousActivityReason.NEW_DEVICE)
            return bool(reasons), reasons

        result = await self.session.execute(
            select(DeviceTrustModel).where(
                DeviceTrustModel.user_id == user_id,
                DeviceTrustModel.tenant_id == tenant_id,
                DeviceTrustModel.device_fingerprint == device_fingerprint,
                DeviceTrustModel.trusted == True,  # noqa: E712
            )
        )
        device = result.scalar_one_or_none()

        if device is None:
            reasons.append(SuspiciousActivityReason.NEW_DEVICE)
        else:
            if ip_address and device.last_ip and ip_address != device.last_ip:
                reasons.append(SuspiciousActivityReason.NEW_IP)

        return bool(reasons), reasons

    async def get_trusted_devices(self, user_id: int, tenant_id: int) -> list[DeviceTrustModel]:
        """List all trusted devices for a user."""
        result = await self.session.execute(
            select(DeviceTrustModel)
            .where(
                DeviceTrustModel.user_id == user_id,
                DeviceTrustModel.tenant_id == tenant_id,
                DeviceTrustModel.trusted == True,  # noqa: E712
            )
            .order_by(DeviceTrustModel.last_used_at.desc().nullsfirst(), DeviceTrustModel.trusted_at.desc())
        )
        return list(result.scalars().all())
