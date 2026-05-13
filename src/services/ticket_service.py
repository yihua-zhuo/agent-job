"""Ticket service — CRUD + replies + auto-assignment via SQLAlchemy ORM."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.activity import ActivityModel
from db.models.ticket import TicketModel
from db.models.ticket_reply import TicketReplyModel
from models.ticket import (
    SLA_CONFIGS,
    SLALevel,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from pkg.errors.app_exceptions import NotFoundException

_AGENT_POOL = (1, 2, 3)


def _to_str(value) -> str:
    return value.value if hasattr(value, "value") else value


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with an async DB session.

        Args:
            session: SQLAlchemy async session (required, no default).
        """
        self.session = session

    async def _fetch(self, ticket_id: int, tenant_id: int) -> TicketModel:
        """Fetch a single ticket by ID, verifying tenant ownership.

        Args:
            ticket_id: Primary key of the ticket.
            tenant_id: Tenant context — must match the ticket's tenant.

        Returns:
            The matching TicketModel.

        Raises:
            NotFoundException: Ticket does not exist or belongs to another tenant.
        """
        result = await self.session.execute(
            select(TicketModel).where(and_(TicketModel.id == ticket_id, TicketModel.tenant_id == tenant_id))
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise NotFoundException("Ticket")
        return ticket

    async def _next_agent(self, tenant_id: int) -> int:
        """Round-robin to select the next available agent for auto-assignment.

        Counts currently assigned tickets in the tenant, then picks
        ``_AGENT_POOL[count % len(_AGENT_POOL)]``.

        Args:
            tenant_id: Tenant context.

        Returns:
            User ID of the selected agent.
        """
        count_result = await self.session.execute(
            select(func.count(TicketModel.id)).where(
                and_(
                    TicketModel.tenant_id == tenant_id,
                    TicketModel.assigned_to.is_not(None),
                )
            )
        )
        count = count_result.scalar() or 0
        return _AGENT_POOL[count % len(_AGENT_POOL)]

    async def create_ticket(
        self,
        subject: str,
        description: str,
        customer_id: int,
        channel: TicketChannel,
        priority: TicketPriority = TicketPriority.MEDIUM,
        sla_level: SLALevel = SLALevel.STANDARD,
        assigned_to: int | None = None,
        tenant_id: int = 0,
    ) -> TicketModel:
        """Create and persist a new ticket with SLA deadline.

        If ``assigned_to`` is not supplied, auto-assigns via round-robin.

        Args:
            subject: Ticket subject line.
            description: Initial description / body.
            customer_id: FK to the owning customer.
            channel: How the ticket was opened (email, chat, …).
            priority: Defaults to MEDIUM.
            sla_level: Defaults to STANDARD; controls response deadline.
            assigned_to: Optional agent user ID; auto-assigned when omitted.
            tenant_id: Tenant context.

        Returns:
            The newly created TicketModel (persisted and refreshed).
        """
        now = datetime.now(UTC)
        sla_config = SLA_CONFIGS[sla_level]
        response_deadline = now + timedelta(hours=sla_config.first_response_hours)

        if assigned_to is None:
            assigned_to = await self._next_agent(tenant_id)

        ticket = TicketModel(
            tenant_id=tenant_id,
            subject=subject,
            description=description,
            status=TicketStatus.OPEN.value,
            priority=_to_str(priority),
            channel=_to_str(channel),
            customer_id=customer_id,
            assigned_to=assigned_to,
            sla_level=_to_str(sla_level),
            response_deadline=response_deadline,
            created_at=now,
            updated_at=now,
        )
        self.session.add(ticket)
        await self.session.flush()
        await self.session.refresh(ticket)
        return ticket

    async def get_ticket(self, ticket_id: int, tenant_id: int = 0) -> TicketModel:
        """Fetch a ticket by ID, verifying tenant ownership.

        Args:
            ticket_id: Primary key.
            tenant_id: Tenant context.

        Returns:
            The matching TicketModel.

        Raises:
            NotFoundException: Ticket not found or wrong tenant.
        """
        return await self._fetch(ticket_id, tenant_id)

    async def update_ticket(self, ticket_id: int, tenant_id: int = 0, **kwargs) -> TicketModel:
        """Apply a partial update to an existing ticket.

        Args:
            ticket_id: Primary key of the ticket to update.
            tenant_id: Tenant context.
            **kwargs: Fields to update — subject, description, customer_id,
                assigned_to, status, priority, channel, sla_level.
                Enum-valued fields (``status``, ``priority``, ``channel``,
                ``sla_level``) are converted to their ``.value`` automatically.

        Returns:
            The updated TicketModel.

        Raises:
            NotFoundException: Ticket not found or wrong tenant.
        """
        await self._fetch(ticket_id, tenant_id)

        update_values: dict = {"updated_at": datetime.now(UTC)}
        for key in ("subject", "description", "customer_id", "assigned_to"):
            if key in kwargs:
                update_values[key] = kwargs[key]
        for enum_key in ("status", "priority", "channel", "sla_level"):
            if enum_key in kwargs:
                update_values[enum_key] = _to_str(kwargs[enum_key])

        await self.session.execute(update(TicketModel).where(TicketModel.id == ticket_id).values(**update_values))
        await self.session.flush()
        return await self._fetch(ticket_id, tenant_id)

    async def assign_ticket(
        self,
        ticket_id: int,
        assigned_to: int,
        tenant_id: int = 0,
    ) -> TicketModel:
        """Explicitly assign (or re-assign) a ticket to an agent.

        Args:
            ticket_id: Primary key of the ticket.
            assigned_to: User ID of the agent to assign.
            tenant_id: Tenant context.

        Returns:
            The updated TicketModel.

        Raises:
            NotFoundException: Ticket not found or wrong tenant.
        """
        return await self.update_ticket(ticket_id, tenant_id=tenant_id, assigned_to=assigned_to)

    async def add_reply(
        self,
        ticket_id: int,
        content: str,
        created_by: int,
        is_internal: bool = False,
        tenant_id: int = 0,
    ) -> TicketReplyModel:
        """Append a reply (or internal note) to a ticket.

        If the reply is external (not internal) and this is the first such reply,
        the ticket's ``first_response_at`` timestamp is set.

        Args:
            ticket_id: Primary key of the ticket.
            content: Reply body.
            created_by: User ID who authored the reply.
            is_internal: ``True`` for internal notes, ``False`` for customer-facing.
            tenant_id: Tenant context.

        Returns:
            The newly created TicketReplyModel (persisted and refreshed).

        Raises:
            NotFoundException: Ticket not found or wrong tenant.
        """
        ticket = await self._fetch(ticket_id, tenant_id)
        now = datetime.now(UTC)

        reply = TicketReplyModel(
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            content=content,
            is_internal=is_internal,
            created_by=created_by,
            created_at=now,
        )
        self.session.add(reply)

        if not ticket.first_response_at and not is_internal:
            await self.session.execute(
                update(TicketModel).where(TicketModel.id == ticket_id).values(first_response_at=now, updated_at=now)
            )

        await self.session.flush()
        await self.session.refresh(reply)
        return reply

    async def change_status(
        self,
        ticket_id: int,
        new_status: TicketStatus,
        tenant_id: int = 0,
    ) -> TicketModel:
        """Transition a ticket to a new status.

        When transitioning to RESOLVED, the ``resolved_at`` timestamp is set.

        Args:
            ticket_id: Primary key of the ticket.
            new_status: Target status enum value.
            tenant_id: Tenant context.

        Returns:
            The updated TicketModel.

        Raises:
            NotFoundException: Ticket not found or wrong tenant.
        """
        await self._fetch(ticket_id, tenant_id)
        now = datetime.now(UTC)
        update_values: dict = {"status": _to_str(new_status), "updated_at": now}
        if new_status == TicketStatus.RESOLVED:
            update_values["resolved_at"] = now
        await self.session.execute(update(TicketModel).where(TicketModel.id == ticket_id).values(**update_values))
        await self.session.flush()
        return await self._fetch(ticket_id, tenant_id)

    async def get_customer_tickets(
        self,
        customer_id: int,
        tenant_id: int = 0,
    ) -> list[TicketModel]:
        """List all tickets belonging to a specific customer.

        Sorted newest-first.

        Args:
            customer_id: FK to the customer.
            tenant_id: Tenant context.

        Returns:
            List of matching TicketModel objects.
        """
        result = await self.session.execute(
            select(TicketModel)
            .where(
                and_(
                    TicketModel.tenant_id == tenant_id,
                    TicketModel.customer_id == customer_id,
                )
            )
            .order_by(TicketModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_tickets(
        self,
        page: int = 1,
        page_size: int = 20,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        assigned_to: int | None = None,
        tenant_id: int = 0,
    ) -> tuple[list[TicketModel], int]:
        """Paginated ticket listing with optional filters.

        Args:
            page: 1-based page number.
            page_size: Number of items per page (default 20).
            status: Optional status filter.
            priority: Optional priority filter.
            assigned_to: Optional assignee filter (null = unassigned).
            tenant_id: Tenant context.

        Returns:
            A ``(items, total)`` tuple where ``items`` is the page of TicketModels
            and ``total`` is the unfiltered count for pagination arithmetic.
        """
        conditions = [TicketModel.tenant_id == tenant_id]
        if status is not None:
            conditions.append(TicketModel.status == _to_str(status))
        if priority is not None:
            conditions.append(TicketModel.priority == _to_str(priority))
        if assigned_to is not None:
            conditions.append(TicketModel.assigned_to == assigned_to)

        count_result = await self.session.execute(select(func.count(TicketModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(TicketModel)
            .where(and_(*conditions))
            .order_by(TicketModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_sla_breaches(self, tenant_id: int = 0) -> list[TicketModel]:
        """Return all unresolved tickets whose response deadline has passed.

        Args:
            tenant_id: Tenant context.

        Returns:
            List of TicketModels in breach state.
        """
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(TicketModel).where(
                and_(
                    TicketModel.tenant_id == tenant_id,
                    TicketModel.resolved_at.is_(None),
                    TicketModel.response_deadline.is_not(None),
                    TicketModel.response_deadline < now,
                )
            )
        )
        return list(result.scalars().all())

    async def auto_assign(self, ticket_id: int, tenant_id: int = 0) -> TicketModel:
        """Auto-assign a ticket using round-robin, but only if it is currently unassigned.

        Idempotent — returns the ticket unchanged if it already has an assignee.

        Args:
            ticket_id: Primary key of the ticket.
            tenant_id: Tenant context.

        Returns:
            The TicketModel (with or without the new assignment).

        Raises:
            NotFoundException: Ticket not found or wrong tenant.
        """
        ticket = await self._fetch(ticket_id, tenant_id)
        if ticket.assigned_to is not None:
            return ticket
        agent_id = await self._next_agent(tenant_id)
        return await self.update_ticket(ticket_id, tenant_id=tenant_id, assigned_to=agent_id)

    async def get_ticket_replies(self, ticket_id: int, tenant_id: int = 0) -> list[TicketReplyModel]:
        """Fetch all replies for a ticket in chronological (ASC) order.

        Used by the replies thread UI.

        Args:
            ticket_id: Primary key of the ticket.
            tenant_id: Tenant context.

        Returns:
            List of TicketReplyModels ordered by ``created_at`` ascending.

        Raises:
            NotFoundException: Ticket not found or wrong tenant.
        """
        await self._fetch(ticket_id, tenant_id)
        result = await self.session.execute(
            select(TicketReplyModel)
            .where(
                and_(
                    TicketReplyModel.ticket_id == ticket_id,
                    TicketReplyModel.tenant_id == tenant_id,
                )
            )
            .order_by(TicketReplyModel.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_ticket_activity(self, ticket_id: int, tenant_id: int = 0) -> list[ActivityModel]:
        """Fetch the activity/audit log for a ticket in reverse-chronological order.

        Activity records are identified by ``content LIKE '%ticket#<id>%'`` and
        must not be linked to an opportunity.

        Args:
            ticket_id: Primary key of the ticket.
            tenant_id: Tenant context.

        Returns:
            List of ActivityModels ordered by ``created_at`` descending.

        Raises:
            NotFoundException: Ticket not found or wrong tenant.
        """
        await self._fetch(ticket_id, tenant_id)
        result = await self.session.execute(
            select(ActivityModel)
            .where(
                and_(
                    ActivityModel.tenant_id == tenant_id,
                    ActivityModel.opportunity_id.is_(None),
                )
            )
            .where(ActivityModel.content.like(f"%ticket#{ticket_id}%"))
            .order_by(ActivityModel.created_at.desc())
        )
        return list(result.scalars().all())
