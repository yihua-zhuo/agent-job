from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer_enrichment import CustomerEnrichmentModel
from db.repositories.customer import CustomerRepository
from models.customer import CustomerCreateDTO, CustomerStatus
from pkg.errors.app_exceptions import ValidationException
from services.lead_routing_service import LeadRoutingService


class CustomerService:
    """Business logic for customers — delegates SQL to CustomerRepository."""

    VALID_STATUSES = {status.value for status in CustomerStatus}

    def __init__(
        self,
        session: AsyncSession,
        customer_repo: CustomerRepository | None = None,
    ):
        self.session = session
        self.customer_repo = customer_repo if customer_repo is not None else CustomerRepository(session)

    async def create_customer(
        self,
        data: dict[str, Any] | CustomerCreateDTO,
        tenant_id: int,
    ) -> Any:
        """Create a customer and trigger auto-assignment for new leads with no owner.

        The repository handles the insert + flush; this method runs the
        auto-assignment side-effect afterward.
        """
        if isinstance(data, CustomerCreateDTO):
            d = data.to_dict()
        else:
            d = data or {}
        customer = await self.customer_repo.create(d, tenant_id)

        if customer.status == "lead" and customer.owner_id == 0:
            routing_svc = LeadRoutingService(self.session)
            await routing_svc.auto_assign_lead(customer.id, tenant_id)

        # Upsert enrichment data when present in payload
        if isinstance(data, dict) and data.get("enrichment_data") is not None:
            await self._upsert_enrichment(customer.id, tenant_id, data["enrichment_data"])

        return customer

    async def list_customers(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        owner_id: int | None = None,
    ) -> tuple[list[Any], int]:
        """List customers for tenant with optional filters."""
        return await self.customer_repo.list_customers(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            status=status,
            owner_id=owner_id,
        )

    async def get_customer(self, customer_id: int, tenant_id: int) -> Any:
        """Get a customer by id (tenant-scoped)."""
        return await self.customer_repo.get_customer(customer_id, tenant_id)

    async def update_customer(
        self,
        customer_id: int,
        data: dict[str, Any],
        tenant_id: int,
    ) -> Any | None:
        """Update a customer (tenant-scoped)."""
        return await self.customer_repo.update_customer(customer_id, data, tenant_id)

    async def delete_customer(self, customer_id: int, tenant_id: int) -> dict:
        """Delete a customer (tenant-scoped)."""
        return await self.customer_repo.delete_customer(customer_id, tenant_id)

    async def count_by_status(self, tenant_id: int) -> dict[CustomerStatus, int]:
        """Count customers grouped by status."""
        return await self.customer_repo.count_by_status(tenant_id)

    async def search_customers(self, keyword: str, tenant_id: int) -> list[Any]:
        """Search customers by name or email (case-insensitive)."""
        return await self.customer_repo.search_customers(keyword, tenant_id)

    async def add_tag(self, customer_id: int, tag: str, tenant_id: int) -> Any:
        """Add a tag to a customer."""
        return await self.customer_repo.add_tag(customer_id, tag, tenant_id)

    async def remove_tag(self, customer_id: int, tag: str, tenant_id: int) -> Any:
        """Remove a tag from a customer."""
        return await self.customer_repo.remove_tag(customer_id, tag, tenant_id)

    async def change_status(
        self,
        customer_id: int,
        status: str,
        tenant_id: int,
    ) -> Any:
        """Change a customer's status."""
        if status not in self.VALID_STATUSES:
            raise ValidationException(f"Invalid status: {status}")
        return await self.customer_repo.update_status(customer_id, status, tenant_id)

    async def assign_owner(
        self,
        customer_id: int,
        owner_id: int,
        tenant_id: int,
    ) -> Any:
        """Assign an owner to a customer."""
        return await self.customer_repo.update_owner(customer_id, owner_id, tenant_id)

    async def bulk_import(self, customers: list[dict[str, Any]], tenant_id: int) -> int:
        """Bulk insert customers, returns imported count."""
        return await self.customer_repo.bulk_import(customers, tenant_id)

    async def reassign_lead(
        self,
        customer_id: int,
        new_owner_id: int,
        tenant_id: int,
        reason: str | None = None,
    ) -> Any:
        """Reassign a lead with history tracking."""
        customer = await self.customer_repo.get_customer(customer_id, tenant_id)
        now = datetime.now(UTC)
        entry = {
            "recycled_at": now.isoformat(),
            "previous_owner_id": customer.owner_id,
            "reason": reason or "manual_reassign",
        }
        history = list(customer.recycle_history or [])
        history.append(entry)
        return await self.customer_repo.reassign_lead(
            customer_id,
            new_owner_id,
            customer.recycle_count + 1,
            history,
            tenant_id,
        )

    async def get_unassigned_leads(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Any], int]:
        """Return leads with owner_id=0 and status=lead, ordered by created_at."""
        from sqlalchemy import and_, func, select

        from db.models.customer import CustomerModel

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
    ) -> tuple[list[Any], int]:
        """Return leads for a specific owner."""
        from sqlalchemy import and_, func, select

        from db.models.customer import CustomerModel

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
        """Bulk recycle a list of lead IDs (set owner_id=0, increment count, log history)."""
        from sqlalchemy import and_, select, update

        from db.models.customer import CustomerModel

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
        leads = result.scalars().all()
        if not leads:
            return []

        recycle_entries = [
            {
                "recycled_at": now.isoformat(),
                "previous_owner_id": lead.owner_id,
                "reason": "manual_bulk_recycle",
            }
            for lead in leads
        ]
        new_histories = []
        for lead, entry in zip(leads, recycle_entries):
            history = list(lead.recycle_history or [])
            history.append(entry)
            new_histories.append(history)

        recycled_ids = [lead.id for lead in leads]
        for lead, new_hist in zip(leads, new_histories):
            await self.session.execute(
                update(CustomerModel)
                .where(and_(CustomerModel.id == lead.id, CustomerModel.tenant_id == tenant_id))
                .values(
                    owner_id=0,
                    assigned_at=None,
                    recycle_count=lead.recycle_count + 1,
                    recycle_history=new_hist,
                    updated_at=now,
                )
            )
        await self.session.flush()
        return recycled_ids

    # -------------------------------------------------------------------------
    # Enrichment helpers
    # -------------------------------------------------------------------------

    async def _upsert_enrichment(
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
