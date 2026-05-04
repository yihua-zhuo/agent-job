"""Tenant service — CRUD via SQLAlchemy ORM (TenantModel)."""
from datetime import UTC, datetime

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.tenant import TenantModel
from db.models.user import UserModel
from pkg.errors.app_exceptions import NotFoundException


class TenantService:
    """Tenant management backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dict(t: TenantModel) -> dict:
        d = t.to_dict()
        settings = d.get("settings") or {}
        d["admin_email"] = settings.get("admin_email")
        d["deleted_at"] = settings.get("deleted_at")
        return d

    async def create_tenant(
        self, name: str, plan: str, admin_email: str | None = None, settings: dict | None = None,
        tenant_id: int = 0,
    ) -> dict:
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
        await self.session.refresh(tenant)
        await self.session.commit()
        return self._to_dict(tenant)

    async def _fetch(self, tenant_id: int) -> TenantModel:
        result = await self.session.execute(
            select(TenantModel).where(TenantModel.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if tenant is None or tenant.status == "deleted":
            raise NotFoundException(f"Tenant {tenant_id}")
        return tenant

    async def get_tenant(self, tenant_id: int, _tenant_id: int = 0) -> dict:
        tenant = await self._fetch(tenant_id)
        return self._to_dict(tenant)

    async def update_tenant(self, tenant_id: int, _tenant_id: int = 0, **kwargs) -> dict:
        tenant = await self._fetch(tenant_id)

        allowed = {"name", "plan", "status"}
        update_values: dict = {"updated_at": datetime.now(UTC)}
        for key, value in kwargs.items():
            if key in allowed:
                update_values[key] = value

        settings_changed = False
        new_settings = dict(tenant.settings or {})
        if "admin_email" in kwargs:
            new_settings["admin_email"] = kwargs["admin_email"]
            settings_changed = True
        if "settings" in kwargs and isinstance(kwargs["settings"], dict):
            new_settings.update(kwargs["settings"])
            settings_changed = True
        if settings_changed:
            update_values["settings"] = new_settings

        await self.session.execute(
            update(TenantModel).where(TenantModel.id == tenant_id).values(**update_values)
        )
        await self.session.commit()

        refreshed = await self.session.execute(
            select(TenantModel).where(TenantModel.id == tenant_id)
        )
        return self._to_dict(refreshed.scalar_one())

    async def suspend_tenant(self, tenant_id: int, _tenant_id: int = 0) -> dict:
        return await self.update_tenant(tenant_id, status="suspended")

    async def delete_tenant(self, tenant_id: int, _tenant_id: int = 0) -> dict:
        tenant = await self._fetch(tenant_id)
        now = datetime.now(UTC)
        new_settings = dict(tenant.settings or {})
        new_settings["deleted_at"] = now.isoformat()
        await self.session.execute(
            update(TenantModel)
            .where(TenantModel.id == tenant_id)
            .values(status="deleted", settings=new_settings, updated_at=now)
        )
        await self.session.commit()
        return {"id": tenant_id}

    async def list_tenants(
        self, page: int = 1, page_size: int = 20, status: str | None = None, _tenant_id: int = 0,
    ) -> tuple[list[dict], int]:
        conditions = [TenantModel.status != "deleted"]
        if status:
            conditions = [TenantModel.status == status]

        count_result = await self.session.execute(
            select(func.count(TenantModel.id)).where(and_(*conditions))
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(TenantModel)
            .where(and_(*conditions))
            .order_by(TenantModel.id)
            .offset(offset)
            .limit(page_size)
        )
        items = [self._to_dict(t) for t in result.scalars().all()]
        return items, total

    async def get_tenant_stats(self, tenant_id: int = 0) -> dict:
        await self._fetch(tenant_id)
        user_count_result = await self.session.execute(
            select(func.count(UserModel.id)).where(UserModel.tenant_id == tenant_id)
        )
        user_count = user_count_result.scalar() or 0
        return {
            "tenant_id": tenant_id,
            "user_count": user_count,
            "storage_used": 0,
            "api_calls": 0,
        }

    async def get_tenant_usage(self, tenant_id: int, _tenant_id: int = 0) -> dict:
        return await self.get_tenant_stats(tenant_id)
