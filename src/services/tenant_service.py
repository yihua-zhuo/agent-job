"""Tenant service — CRUD via SQLAlchemy ORM (TenantModel)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.tenant import TenantModel
from db.models.user import UserModel
from pkg.constants.tenant_constants import VALID_PLANS
from pkg.errors.app_exceptions import ForbiddenException, NotFoundException, ValidationException


class TenantService:
    """Tenant management backed by PostgreSQL via SQLAlchemy async ORM."""

    @dataclass
    class _TenantStats:
        """Stats aggregate returned by get_tenant_stats / get_tenant_usage."""

        tenant: TenantModel
        user_count: int

        def to_dict(self) -> dict:
            return {
                "tenant_id": self.tenant.id,
                "name": self.tenant.name,
                "plan": self.tenant.plan,
                "status": self.tenant.status,
                "user_count": self.user_count,
            }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_tenant(
        self,
        name: str,
        plan: str,
        admin_email: str | None = None,
        settings: dict | None = None,
    ) -> TenantModel:
        if plan not in VALID_PLANS:
            raise ValidationException(f"plan must be one of {sorted(VALID_PLANS)}, got {plan!r}")
        merged: dict = dict(settings or {})
        if admin_email is not None:
            merged["admin_email"] = admin_email
        now = datetime.now(UTC)
        tenant = TenantModel(
            name=name,
            plan=plan,
            status="active",
            settings=merged,
            created_at=now,
            updated_at=now,
        )
        self.session.add(tenant)
        await self.session.flush()
        return tenant

    async def _fetch_tenant(self, target_tenant_id: int, requesting_tenant_id: int) -> TenantModel:
        if requesting_tenant_id != target_tenant_id:
            raise ForbiddenException("Access denied")
        conditions = [TenantModel.id == target_tenant_id]
        result = await self.session.execute(select(TenantModel).where(and_(*conditions)))
        tenant = result.scalar_one_or_none()
        if tenant is None or tenant.status == "deleted":
            raise NotFoundException("Tenant")
        return tenant

    async def get_tenant(self, tenant_id: int, requesting_tenant_id: int) -> TenantModel:
        return await self._fetch_tenant(tenant_id, requesting_tenant_id)

    async def update_tenant(self, tenant_id: int, requesting_tenant_id: int, **kwargs) -> TenantModel:
        if tenant_id != requesting_tenant_id:
            raise ForbiddenException("Access denied")
        tenant = await self._fetch_tenant(tenant_id, requesting_tenant_id)

        allowed = {"name", "plan", "status", "admin_email", "settings"}
        unknown = [k for k in kwargs if k not in allowed]
        if unknown:
            raise ValidationException(f"Unknown fields: {', '.join(sorted(unknown))}")

        if "plan" in kwargs and kwargs["plan"] not in VALID_PLANS:
            raise ValidationException(f"plan must be one of {sorted(VALID_PLANS)}, got {kwargs['plan']!r}")

        settings_changed = False
        new_settings = dict(tenant.settings or {})
        if "admin_email" in kwargs:
            new_settings["admin_email"] = kwargs["admin_email"]
            settings_changed = True
        if "settings" in kwargs and isinstance(kwargs["settings"], dict):
            new_settings.update(kwargs["settings"])
            settings_changed = True

        for key in allowed:
            if key in kwargs and key not in ("admin_email", "settings"):
                setattr(tenant, key, kwargs[key])
        tenant.updated_at = datetime.now(UTC)
        if settings_changed:
            tenant.settings = new_settings

        await self.session.flush()
        return tenant

    async def suspend_tenant(self, tenant_id: int, requesting_tenant_id: int) -> TenantModel:
        return await self.update_tenant(tenant_id, requesting_tenant_id=requesting_tenant_id, status="suspended")

    async def delete_tenant(self, tenant_id: int, requesting_tenant_id: int) -> TenantModel:
        tenant = await self._fetch_tenant(tenant_id, requesting_tenant_id)
        now = datetime.now(UTC)
        new_settings = dict(tenant.settings or {})
        new_settings["deleted_at"] = now.isoformat()
        tenant.status = "deleted"
        tenant.settings = new_settings
        tenant.updated_at = now
        await self.session.flush()
        return tenant

    async def list_tenants(
        self,
        requesting_tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[TenantModel], int]:
        conditions = [TenantModel.status != "deleted"]
        if status:
            conditions.append(TenantModel.status == status)
        if search:
            conditions.append(TenantModel.name.ilike(f"%{search}%"))
        # Rule126: requesting_tenant_id restricts visibility to its own tenant record.
        conditions.append(TenantModel.id == requesting_tenant_id)

        count_result = await self.session.execute(select(func.count(TenantModel.id)).where(and_(*conditions)))
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(TenantModel).where(and_(*conditions)).order_by(TenantModel.id).offset(offset).limit(page_size)
        )
        items = list(result.scalars().all())
        return items, total

    async def get_tenant_stats(self, tenant_id: int, requesting_tenant_id: int) -> _TenantStats:
        tenant = await self._fetch_tenant(tenant_id, requesting_tenant_id)
        user_count_result = await self.session.execute(
            select(func.count(UserModel.id)).where(UserModel.tenant_id == tenant_id)
        )
        user_count = user_count_result.scalar() or 0
        return self._TenantStats(tenant, user_count)

    async def get_tenant_usage(self, tenant_id: int, requesting_tenant_id: int) -> _TenantStats:
        """Return tenant usage data. Delegates to get_tenant_stats for real implementation."""
        return await self.get_tenant_stats(tenant_id, requesting_tenant_id)
