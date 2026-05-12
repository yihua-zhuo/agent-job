"""Ticket service — CRUD + replies + auto-assignment via SQLAlchemy ORM."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _fetch(self, ticket_id: int, tenant_id: int) -> TicketModel:
        result = await self.session.execute(
            select(TicketModel).where(and_(TicketModel.id == ticket_id, TicketModel.tenant_id == tenant_id))
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise NotFoundException("Ticket")
        return ticket

    async def _next_agent(self, tenant_id: int) -> int:
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
        return await self._fetch(ticket_id, tenant_id)

    async def update_ticket(self, ticket_id: int, tenant_id: int = 0, **kwargs) -> TicketModel:
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
        return await self.update_ticket(ticket_id, tenant_id=tenant_id, assigned_to=assigned_to)

    async def add_reply(
        self,
        ticket_id: int,
        content: str,
        created_by: int,
        is_internal: bool = False,
        tenant_id: int = 0,
    ) -> TicketReplyModel:
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
        ticket = await self._fetch(ticket_id, tenant_id)
        if ticket.assigned_to is not None:
            return ticket
        agent_id = await self._next_agent(tenant_id)
        return await self.update_ticket(ticket_id, tenant_id=tenant_id, assigned_to=agent_id)
