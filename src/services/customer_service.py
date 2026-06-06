from datetime import UTC, datetime
from typing import Any

from db.repositories.customer import CustomerRepository
from models.customer import CustomerCreateDTO, CustomerStatus
from pkg.errors.app_exceptions import ValidationException
from services.lead_routing_service import LeadRoutingService


class CustomerService:
    """Business logic for customers — delegates SQL to CustomerRepository."""

    VALID_STATUSES = {status.value for status in CustomerStatus}

    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    async def create_customer(
        self,
        data: dict[str, Any] | CustomerCreateDTO,
        tenant_id: int,
        routing_service: "LeadRoutingService | None" = None,
    ) -> Any:
        """Create a customer and trigger auto-assignment for new leads with no owner.

        The repository handles the insert + flush; this method runs the
        auto-assignment side-effect afterward.
        """
        if isinstance(data, CustomerCreateDTO):
            d = data.to_dict()
        else:
            d = data or {}
            try:
                CustomerCreateDTO.from_dict(d)  # validates required fields
            except ValueError as e:
                raise ValidationException(str(e)) from e
        customer = await self.repository.create(d, tenant_id)

        if routing_service is not None and customer.status == CustomerStatus.LEAD.value and customer.owner_id == 0:
            await routing_service.auto_assign_lead(customer.id, tenant_id)

        # Upsert enrichment data when present in payload
        if isinstance(data, dict) and data.get("enrichment_data") is not None:
            await self._upsert_enrichment(customer.id, tenant_id, data["enrichment_data"])

        return customer

    # Maps the public lead_tier filter values (hot/warm/cold) to the stored
    # ScoreTier letter values (A/B/C) that the customer.tier column carries.
    # Tier "D" customers are below the cold threshold and excluded by design.
    LEAD_TIER_TO_STORED: dict[str, str] = {
        "hot": "A",
        "warm": "B",
        "cold": "C",
    }

    async def list_customers(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        owner_id: int | None = None,
        lead_tier: str | None = None,
        order_by_score: bool = False,
    ) -> tuple[list[Any], int]:
        """List customers for tenant with optional filters."""
        stored_tier: str | None = None
        if lead_tier is not None:
            if lead_tier not in self.LEAD_TIER_TO_STORED:
                raise ValidationException("lead_tier must be one of: hot, warm, cold")
            stored_tier = self.LEAD_TIER_TO_STORED[lead_tier]
        return await self.repository.list_customers(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            status=status,
            owner_id=owner_id,
            lead_tier=stored_tier,
            order_by_score=order_by_score,
        )

    async def get_customer(self, customer_id: int, tenant_id: int) -> Any:
        """Get a customer by id (tenant-scoped)."""
        return await self.repository.get_customer(customer_id, tenant_id)

    async def update_customer(
        self,
        customer_id: int,
        data: dict[str, Any],
        tenant_id: int,
    ) -> Any | None:
        """Update a customer (tenant-scoped)."""
        return await self.repository.update_customer(customer_id, data, tenant_id)

    async def delete_customer(self, customer_id: int, tenant_id: int) -> dict:
        """Delete a customer (tenant-scoped)."""
        return await self.repository.delete_customer(customer_id, tenant_id)

    async def count_by_status(self, tenant_id: int) -> dict[CustomerStatus, int]:
        """Count customers grouped by status."""
        return await self.repository.count_by_status(tenant_id)

    async def search_customers(self, keyword: str, tenant_id: int) -> list[Any]:
        """Search customers by name or email (case-insensitive)."""
        return await self.repository.search_customers(keyword, tenant_id)

    async def add_tag(self, customer_id: int, tag: str, tenant_id: int) -> Any:
        """Add a tag to a customer."""
        return await self.repository.add_tag(customer_id, tag, tenant_id)

    async def remove_tag(self, customer_id: int, tag: str, tenant_id: int) -> Any:
        """Remove a tag from a customer."""
        return await self.repository.remove_tag(customer_id, tag, tenant_id)

    async def change_status(
        self,
        customer_id: int,
        status: str,
        tenant_id: int,
    ) -> Any:
        """Change a customer's status."""
        if status not in self.VALID_STATUSES:
            raise ValidationException(f"Invalid status: {status}")
        return await self.repository.update_status(customer_id, status, tenant_id)

    async def assign_owner(
        self,
        customer_id: int,
        owner_id: int,
        tenant_id: int,
    ) -> Any:
        """Assign an owner to a customer."""
        return await self.repository.update_owner(customer_id, owner_id, tenant_id)

    async def bulk_import(self, customers: list[dict[str, Any]], tenant_id: int) -> int:
        """Bulk insert customers, returns imported count."""
        return await self.repository.bulk_import(customers, tenant_id)

    async def reassign_lead(
        self,
        customer_id: int,
        new_owner_id: int,
        tenant_id: int,
        reason: str | None = None,
    ) -> Any:
        """Reassign a lead with history tracking."""
        customer = await self.repository.get_customer(customer_id, tenant_id)
        now = datetime.now(UTC)
        entry = {
            "recycled_at": now.isoformat(),
            "previous_owner_id": customer.owner_id,
            "reason": reason or "manual_reassign",
        }
        history = list(customer.recycle_history) if customer.recycle_history is not None else []
        history.append(entry)
        return await self.repository.reassign_lead(
            new_owner_id,
            customer.recycle_count + 1,
            history,
            tenant_id,
            now,
            customer_id=customer_id,
        )

    async def get_unassigned_leads(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Any], int]:
        """Return leads with owner_id=0 and status=lead, ordered by created_at."""
        return await self.repository.get_unassigned_leads(tenant_id, page, page_size)

    async def get_leads_by_owner(
        self,
        owner_id: int,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Any], int]:
        """Return leads for a specific owner."""
        return await self.repository.get_leads_by_owner(owner_id, tenant_id, page, page_size)

    async def bulk_recycle(self, customer_ids: list[int], tenant_id: int) -> list[int]:
        """Bulk recycle a list of lead IDs (set owner_id=0, increment count, log history)."""
        return await self.repository.bulk_recycle(customer_ids, tenant_id)

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
        await self.repository.upsert_enrichment(customer_id, tenant_id, enrichment_data)
