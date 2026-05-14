"""Customer service — CRUD + tagging + status management via SQLAlchemy ORM."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from models.customer import CustomerStatus
from models.customer_create_dto import CustomerCreateDTO
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class CustomerService:
    """Customer CRUD and management — backed by PostgreSQL via SQLAlchemy async ORM."""

    VALID_STATUSES = {status.value for status in CustomerStatus}

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_customer(
        self,
        data: dict[str, Any] | CustomerCreateDTO,
        tenant_id: int,
    ) -> CustomerModel:
        """Insert a customer row.

        Args:
            data: Either a raw dict or a CustomerCreateDTO instance.
            tenant_id: Tenant scope for the new customer.
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
        now = datetime.now(UTC)
        customer = CustomerModel(
            tenant_id=tenant_id,
            name=d.get("name") or "Customer",
            email=d.get("email"),
            phone=d.get("phone"),
            company=d.get("company"),
            status=d.get("status", "lead"),
            owner_id=d.get("owner_id", 0),
            tags=d.get("tags", []),
            created_at=now,
            updated_at=now,
        )
        self.session.add(customer)
        await self.session.flush()
        # refresh() intentionally omitted — router layer owns commit/flush cycle;
        # object in-memory state is sufficient for callers after flush.

        # Step 8 — trigger auto-assignment for new leads with no owner
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
    ) -> tuple[list[CustomerModel], int]:
        """List customers for tenant with optional filters."""
        conditions = [CustomerModel.tenant_id == tenant_id]
        if status:
            conditions.append(CustomerModel.status == status)
        if owner_id is not None:
            conditions.append(CustomerModel.owner_id == owner_id)

        count_result = await self.session.execute(select(func.count(CustomerModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(CustomerModel)
            .where(and_(*conditions))
            .order_by(CustomerModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def get_customer(self, customer_id: int, tenant_id: int) -> CustomerModel:
        """Get a customer by id (tenant-scoped)."""
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
        data: dict,
        tenant_id: int,
    ) -> CustomerModel | None:
        """Update a customer (tenant-scoped)."""
        if "status" in data and data["status"] not in self.VALID_STATUSES:
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

    async def delete_customer(self, customer_id: int, tenant_id: int) -> dict:
        """Delete a customer (tenant-scoped)."""
        result = await self.session.execute(
            delete(CustomerModel).where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id))
        )
        if (result.rowcount or 0) == 0:
            raise NotFoundException("客户")
        return {"id": customer_id}

    async def count_by_status(self, tenant_id: int) -> dict[CustomerStatus, int]:
        """Count customers grouped by status."""
        result = await self.session.execute(
            select(CustomerModel.status, func.count(CustomerModel.id))
            .where(CustomerModel.tenant_id == tenant_id)
            .group_by(CustomerModel.status)
        )
        counts: dict[CustomerStatus, int] = {}
        for raw_status, count in result.all():
            try:
                status = CustomerStatus(raw_status)
            except ValueError as exc:
                raise ValidationException(f"Invalid customer status in DB: {raw_status}") from exc
            counts[status] = int(count)
        return counts

    async def search_customers(self, keyword: str, tenant_id: int) -> list[CustomerModel]:
        """Search customers by name or email (case-insensitive)."""
        if not keyword:
            return []
        escaped_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        kw = f"%{escaped_keyword}%"
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

    async def change_status(
        self,
        customer_id: int,
        status: str,
        tenant_id: int,
    ) -> CustomerModel:
        """Change a customer's status."""
        if status not in self.VALID_STATUSES:
            raise ValidationException(f"Invalid status: {status}")
        customer = await self.get_customer(customer_id, tenant_id)
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
    ) -> CustomerModel:
        """Assign an owner to a customer."""
        customer = await self.get_customer(customer_id, tenant_id)
        now = datetime.now(UTC)
        customer.owner_id = owner_id
        if customer.assigned_at is None:
            customer.assigned_at = now
        customer.updated_at = now
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def bulk_import(self, customers: list[dict], tenant_id: int) -> int:
        """Bulk insert customers, returns imported count."""
        if not customers:
            return 0
        now = datetime.now(UTC)
        customers = [
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
        self.session.add_all(customers)
        await self.session.flush()
        return len(customers)

    async def reassign_lead(
        self,
        customer_id: int,
        new_owner_id: int,
        tenant_id: int,
        reason: str | None = None,
    ) -> CustomerModel:
        """Reassign a lead with history tracking."""
        customer = await self.get_customer(customer_id, tenant_id)
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
    ) -> tuple[list[CustomerModel], int]:
        """Return leads with owner_id=0 and status=lead, ordered by created_at."""
        conditions = [
            CustomerModel.tenant_id == tenant_id,
            CustomerModel.owner_id == 0,
            CustomerModel.status == "lead",
        ]
        count_result = await self.session.execute(
            select(func.count(CustomerModel.id)).where(and_(*conditions))
        )
        total = count_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(CustomerModel)
            .where(and_(*conditions))
            .order_by(CustomerModel.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

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
        count_result = await self.session.execute(
            select(func.count(CustomerModel.id)).where(and_(*conditions))
        )
        total = count_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(CustomerModel)
            .where(and_(*conditions))
            .order_by(CustomerModel.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def bulk_recycle(self, customer_ids: list[int], tenant_id: int) -> list[int]:
        """Bulk recycle a list of lead IDs (set owner_id=0, increment count, log history)."""
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

        # Collect all history entries into a single UPDATE using SQL array-append
        # to avoid N UPDATE statements.
        recycle_entries = [
            {
                "recycled_at": now.isoformat(),
                "previous_owner_id": lead.owner_id,
                "reason": "manual_bulk_recycle",
            }
            for lead in leads
        ]
        # Build new recycle_history by appending each entry to existing history
        # via PostgreSQL's || operator handled in Python for simplicity (N is small)
        new_histories = []
        for lead, entry in zip(leads, recycle_entries):
            history = list(lead.recycle_history or [])
            history.append(entry)
            new_histories.append(history)

        # Single UPDATE with id IN (...) and per-row arrays
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
