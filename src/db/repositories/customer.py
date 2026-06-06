"""Customer data-access layer — SQLAlchemy async ORM."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models.customer import CustomerModel
from db.models.customer_enrichment import CustomerEnrichmentModel
from db.repositories.base import BaseRepository
from models.customer import CustomerStatus
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class CustomerRepository(BaseRepository):
    """Data-access operations for CustomerModel."""

    async def create(self, data: dict[str, Any], tenant_id: int) -> CustomerModel:
        """Insert a customer row and flush (no commit — callers own the flush cycle)."""
        now = datetime.now(UTC)
        customer = CustomerModel(
            tenant_id=tenant_id,
            name=data.get("name") or "Customer",
            email=data.get("email"),
            phone=data.get("phone"),
            company=data.get("company"),
            status=data.get("status", "lead"),
            owner_id=data.get("owner_id", 0),
            tags=data.get("tags", []),
            created_at=now,
            updated_at=now,
        )
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def list_customers(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        owner_id: int | None = None,
        lead_tier: str | None = None,
        order_by_score: bool = False,
    ) -> tuple[list[CustomerModel], int]:
        """List customers for tenant with optional status / owner / tier filters."""
        conditions = [CustomerModel.tenant_id == tenant_id]
        if status:
            conditions.append(CustomerModel.status == status)
        if owner_id is not None:
            conditions.append(CustomerModel.owner_id == owner_id)
        if lead_tier is not None:
            conditions.append(CustomerModel.tier == lead_tier)

        count_result = await self.session.execute(select(func.count(CustomerModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        if order_by_score:
            order_clause = func.coalesce(CustomerModel.score, 0).desc()
        else:
            order_clause = CustomerModel.created_at.desc()
        result = await self.session.execute(
            select(CustomerModel).where(and_(*conditions)).order_by(order_clause).offset(offset).limit(page_size)
        )
        return result.scalars().all(), total

    async def get_customer(self, customer_id: int, tenant_id: int) -> CustomerModel:
        """Fetch a customer by id (tenant-scoped). Raises NotFoundException if missing."""
        result = await self.session.execute(
            select(CustomerModel).where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id))
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundException("客户")
        return customer

    async def update_customer(
        self,
        customer_id: int,
        data: dict[str, Any],
        tenant_id: int,
    ) -> CustomerModel | None:
        """Update allowed fields on a customer. Raises ValidationException for invalid status."""
        if "status" in data and data["status"] not in {s.value for s in CustomerStatus}:
            raise ValidationException(f"Invalid status: {data['status']}")

        customer = await self.get_customer(customer_id, tenant_id)

        allowed = {"name", "email", "phone", "company", "status", "owner_id"}
        any_changes = False
        for key, value in data.items():
            if key in allowed:
                setattr(customer, key, value)
                any_changes = True
        if not any_changes:
            return None

        customer.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def update_status(
        self,
        customer_id: int,
        status: str,
        tenant_id: int,
    ) -> CustomerModel:
        """Update a customer's status. Caller must flush/commit."""
        customer = await self.get_customer(customer_id, tenant_id)
        customer.status = status
        customer.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def update_owner(
        self,
        customer_id: int,
        owner_id: int,
        tenant_id: int,
    ) -> CustomerModel:
        """Update a customer's owner. Sets assigned_at if null. Caller must flush/commit."""
        customer = await self.get_customer(customer_id, tenant_id)
        now = datetime.now(UTC)
        customer.owner_id = owner_id
        if customer.assigned_at is None:
            customer.assigned_at = now
        customer.updated_at = now
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def reassign_lead(
        self,
        new_owner_id: int,
        recycle_count: int,
        recycle_history: list[dict[str, Any]],
        tenant_id: int,
        now: datetime,
        *,
        customer_id: int,
    ) -> CustomerModel:
        """Reassign a lead (update owner, increment recycle_count, append history)."""
        customer = await self.get_customer(customer_id, tenant_id)
        customer.owner_id = new_owner_id
        customer.assigned_at = now
        customer.recycle_count = recycle_count
        customer.recycle_history = recycle_history
        customer.updated_at = now
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def delete_customer(self, customer_id: int, tenant_id: int) -> dict[str, int]:
        """Delete a customer (tenant-scoped). Raises NotFoundException if not found."""
        result = await self.session.execute(
            delete(CustomerModel).where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id))
        )
        if (result.rowcount or 0) == 0:
            raise NotFoundException("客户")
        return {"id": customer_id}

    async def count_by_status(self, tenant_id: int) -> dict[CustomerStatus, int]:
        """Count customers grouped by status."""
        import logging

        result = await self.session.execute(
            select(CustomerModel.status, func.count(CustomerModel.id))
            .where(CustomerModel.tenant_id == tenant_id)
            .group_by(CustomerModel.status)
        )
        counts: dict[CustomerStatus, int] = {}
        for raw_status, count in result.all():
            try:
                status = CustomerStatus(raw_status)
            except ValueError:
                logging.warning("Skipping invalid customer status in DB: %s", raw_status)
                continue
            counts[status] = int(count)
        return counts

    async def search_customers(self, keyword: str, tenant_id: int) -> list[CustomerModel]:
        """Search customers by name or email (case-insensitive). Returns [] for empty keyword."""
        if not keyword:
            return []
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        kw = f"%{escaped}%"
        result = await self.session.execute(
            select(CustomerModel)
            .where(
                and_(
                    CustomerModel.tenant_id == tenant_id,
                    or_(
                        CustomerModel.name.ilike(kw, escape="\\"),
                        CustomerModel.email.ilike(kw, escape="\\"),
                    ),
                )
            )
            .order_by(CustomerModel.created_at.desc())
            .limit(100)
        )
        return result.scalars().all()

    async def add_tag(self, customer_id: int, tag: str, tenant_id: int) -> CustomerModel:
        """Add a tag to a customer."""
        customer = await self.get_customer(customer_id, tenant_id)
        tags = list(customer.tags or [])
        if tag not in tags:
            tags.append(tag)
        customer.tags = tags
        customer.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def remove_tag(self, customer_id: int, tag: str, tenant_id: int) -> CustomerModel:
        """Remove a tag from a customer."""
        customer = await self.get_customer(customer_id, tenant_id)
        customer.tags = [t for t in (customer.tags or []) if t != tag]
        customer.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def bulk_import(self, customers: list[dict[str, Any]], tenant_id: int) -> int:
        """Bulk insert customers. Returns the number of rows inserted."""
        if not customers:
            return 0
        now = datetime.now(UTC)
        rows = [
            CustomerModel(
                tenant_id=tenant_id,
                name=c.get("name") or "Customer",
                email=c.get("email"),
                phone=c.get("phone"),
                company=c.get("company"),
                status=c.get("status", "lead"),
                owner_id=c.get("owner_id", 0),
                tags=c.get("tags", []),
                created_at=now,
                updated_at=now,
            )
            for c in customers
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return len(rows)

    async def get_unassigned_leads(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CustomerModel], int]:
        """Return leads with owner_id=0 and status=lead, ordered by created_at."""
        conditions = [
            CustomerModel.tenant_id == tenant_id,
            CustomerModel.owner_id == 0,
            CustomerModel.status == "lead",
        ]
        count_result = await self.session.execute(select(func.count(CustomerModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(CustomerModel)
            .where(and_(*conditions))
            .order_by(CustomerModel.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_leads_by_owner(
        self,
        owner_id: int,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CustomerModel], int]:
        """Return leads for a specific owner."""
        conditions = [
            CustomerModel.tenant_id == tenant_id,
            CustomerModel.owner_id == owner_id,
            CustomerModel.status == "lead",
        ]
        count_result = await self.session.execute(select(func.count(CustomerModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(CustomerModel)
            .where(and_(*conditions))
            .order_by(CustomerModel.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def bulk_recycle(self, customer_ids: list[int], tenant_id: int) -> list[int]:
        """Set owner_id=0, increment recycle_count, append history for matching leads. Returns recycled IDs."""
        if not customer_ids:
            return []
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(CustomerModel).where(
                and_(
                    CustomerModel.tenant_id == tenant_id,
                    CustomerModel.id.in_(customer_ids),
                    CustomerModel.status == "lead",
                    CustomerModel.owner_id != 0,
                )
            )
        )
        leads = list(result.scalars().all())
        if not leads:
            return []
        recycled_ids = []
        for lead in leads:
            # Per-row UPDATE + flush so the refreshed lead object has the
            # correct incremented recycle_count for history construction.
            await self.session.execute(
                update(CustomerModel)
                .where(and_(CustomerModel.id == lead.id, CustomerModel.tenant_id == tenant_id))
                .values(
                    owner_id=0,
                    assigned_at=None,
                    recycle_count=lead.recycle_count + 1,
                    updated_at=now,
                )
            )
            await self.session.flush()
            await self.session.refresh(lead)
            # Refresh has reloaded the ORM object from DB; append the history entry
            # after the refresh so the in-memory change is not clobbered.
            history = list(lead.recycle_history or [])
            history.append(
                {
                    "recycled_at": now.isoformat(),
                    "previous_owner_id": lead.owner_id,
                    "reason": "manual_bulk_recycle",
                }
            )
            lead.recycle_history = history
            recycled_ids.append(lead.id)
        return recycled_ids

    async def upsert_enrichment(
        self,
        customer_id: int,
        tenant_id: int,
        enrichment_data: dict[str, Any],
    ) -> None:
        """Upsert a CustomerEnrichmentModel record for the given customer.

        Uses INSERT … ON CONFLICT (tenant_id, customer_id) DO UPDATE so that
        each call creates the record if absent, or updates the existing row if a
        record for the same (tenant_id, customer_id) pair already exists.
        """
        now = datetime.now(UTC)
        next_refresh = now + timedelta(days=7)
        stmt = pg_insert(CustomerEnrichmentModel).values(
            tenant_id=tenant_id,
            customer_id=customer_id,
            provider=enrichment_data.get("provider", "clearbit"),
            raw_data_json=enrichment_data.get("raw_data_json", enrichment_data),
            enriched_at=enrichment_data.get("enriched_at", now),
            next_refresh_at=next_refresh,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "customer_id"],
            set_={
                "provider": stmt.excluded.provider,
                "raw_data_json": stmt.excluded.raw_data_json,
                "enriched_at": stmt.excluded.enriched_at,
                "next_refresh_at": next_refresh,
                "updated_at": now,
            },
        )
        await self.session.execute(stmt)
