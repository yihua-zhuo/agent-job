"""Customer service — CRUD + tagging + status management via SQLAlchemy ORM."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, or_, select
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
        await self.session.refresh(customer)
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
        if tenant_id <= 0:
            return {}
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
        customer.owner_id = owner_id
        customer.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def bulk_import(self, customers: list[dict], tenant_id: int) -> int:
        """Bulk insert customers, returns imported count."""
        if not customers:
            return 0
        now = datetime.now(UTC)
        for c in customers:
            self.session.add(
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
            )
        await self.session.flush()
        return len(customers)
