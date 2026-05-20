"""Customer service — business logic on top of CustomerRepository."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories.customer import CustomerRepository
from models.customer import CustomerStatus
from models.customer_create_dto import CustomerCreateDTO
from pkg.errors.app_exceptions import ValidationException


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
            d = {
                "name": data.name,
                "email": data.email,
                "phone": data.phone,
                "company": data.company,
                "status": data.status,
                "owner_id": data.owner_id,
                "tags": data.tags,
            }
        else:
            d = data or {}

        customer = await self.customer_repo.create(d, tenant_id)

        if customer.status == "lead" and customer.owner_id == 0:
            from services.lead_routing_service import LeadRoutingService

            routing_svc = LeadRoutingService(self.session)
            await routing_svc.auto_assign_lead(customer.id, tenant_id)

        return customer

    async def list_customers(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        owner_id: int | None = None,
        tags: str | None = None,
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

    async def delete_customer(self, customer_id: int, tenant_id: int) -> dict[str, int]:
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
        customer = await self.customer_repo.get_customer(customer_id, tenant_id)
        customer.status = status
        customer.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def assign_owner(
        self,
        customer_id: int,
        owner_id: int,
        tenant_id: int,
    ) -> Any:
        """Assign an owner to a customer."""
        customer = await self.customer_repo.get_customer(customer_id, tenant_id)
        now = datetime.now(UTC)
        customer.owner_id = owner_id
        if customer.assigned_at is None:
            customer.assigned_at = now
        customer.updated_at = now
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

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
        from sqlalchemy import and_, update

        from db.models.customer import CustomerModel

        customer = await self.customer_repo.get_customer(customer_id, tenant_id)
        now = datetime.now(UTC)
        entry = {
            "recycled_at": now.isoformat(),
            "previous_owner_id": customer.owner_id,
            "reason": reason or "manual_reassign",
        }
        history = list(customer.recycle_history or [])
        history.append(entry)
        await self.session.execute(
            update(CustomerModel)
            .where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id))
            .values(
                owner_id=new_owner_id,
                assigned_at=now,
                recycle_count=customer.recycle_count + 1,
                recycle_history=history,
                updated_at=now,
            )
        )
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

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
