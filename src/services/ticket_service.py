"""
TicketService – async PostgreSQL implementation via SQLAlchemy.

Keeps identical public method signatures and return types as the original
in-memory version, but replaces _tickets/_replies dicts with DB queries.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db_session
from db.models.ticket import TicketModel
from db.models.ticket_reply import TicketReplyModel
from models.ticket import (
    Ticket,
    TicketReply,
    TicketStatus,
    TicketPriority,
    TicketChannel,
    SLALevel,
    SLA_CONFIGS,
)
from models.response import ApiResponse, PaginatedData, ApiError


# ---------------------------------------------------------------------------
# Helpers – map ORM rows → domain dataclasses
# ---------------------------------------------------------------------------

def _row_to_ticket(row: TicketModel) -> Ticket:
    return Ticket(
        id=row.id,
        tenant_id=row.tenant_id,
        subject=row.subject,
        description=row.description,
        status=TicketStatus(row.status),
        priority=TicketPriority(row.priority),
        channel=TicketChannel(row.channel),
        customer_id=row.customer_id,
        assigned_to=row.assigned_to,
        sla_level=SLALevel(row.sla_level),
        resolved_at=row.resolved_at,
        first_response_at=row.first_response_at,
        response_deadline=row.response_deadline,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_reply(row: TicketReplyModel) -> TicketReply:
    return TicketReply(
        id=row.id,
        ticket_id=row.ticket_id,
        tenant_id=row.tenant_id,
        content=row.content,
        is_internal=row.is_internal,
        created_by=row.created_by,
        created_at=row.created_at,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TicketService:
    def __init__(self) -> None:
        # Agent pool – kept as instance state (not persisted to DB) to preserve
        # the original round-robin auto_assign behaviour.
        self._agent_pool: List[int] = [1, 2, 3]
        self._agent_index: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _owned_by(self, ticket: Optional[Ticket], tenant_id: int) -> bool:
        """Return True if the ticket exists and belongs to the tenant (or tenant check skipped)."""
        if ticket is None:
            return False
        if not tenant_id:
            return True
        return ticket.tenant_id == tenant_id

    async def _fetch_ticket(
        self, session: AsyncSession, ticket_id: int, tenant_id: int = 0
    ) -> Optional[TicketModel]:
        """SELECT the TicketModel row, honoring tenant isolation."""
        stmt = select(TicketModel).where(TicketModel.id == ticket_id)
        if tenant_id:
            stmt = stmt.where(
                or_(TicketModel.tenant_id == tenant_id, TicketModel.tenant_id == 0)
            )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_ticket(
        self,
        subject: str,
        description: str,
        customer_id: int,
        channel: TicketChannel,
        priority: TicketPriority = TicketPriority.MEDIUM,
        sla_level: SLALevel = SLALevel.STANDARD,
        assigned_to: Optional[int] = None,
        tenant_id: int = 0,
    ) -> ApiResponse[Ticket]:
        """创建工单"""
        now = datetime.utcnow()
        sla_config = SLA_CONFIGS[sla_level]
        response_deadline = now + timedelta(hours=sla_config.first_response_hours)

        async with get_db_session() as session:
            row = TicketModel(
                tenant_id=tenant_id,
                subject=subject,
                description=description,
                status=TicketStatus.OPEN.value,
                priority=priority.value,
                channel=channel.value,
                customer_id=customer_id,
                assigned_to=assigned_to,
                sla_level=sla_level.value,
                resolved_at=None,
                first_response_at=None,
                response_deadline=response_deadline,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()  # populate row.id before commit

            ticket = _row_to_ticket(row)

        # auto_assign is called outside the create transaction so it can open
        # its own session (mirrors the original logic).
        if assigned_to is None and ticket.id is not None:
            await self.auto_assign(ticket.id, tenant_id=tenant_id)
            # Re-fetch to get the assigned_to value set by auto_assign.
            async with get_db_session() as session:
                updated_row = await self._fetch_ticket(session, ticket.id, tenant_id)
                if updated_row is not None:
                    ticket = _row_to_ticket(updated_row)

        return ApiResponse.success(data=ticket, message='工单创建成功')

    async def get_ticket(self, ticket_id: int, tenant_id: int = 0) -> ApiResponse[Ticket]:
        """获取工单"""
        async with get_db_session() as session:
            row = await self._fetch_ticket(session, ticket_id, tenant_id)
        if row is None:
            return ApiResponse.error(message='工单不存在', code=1404)
        return ApiResponse.success(data=_row_to_ticket(row))

    async def update_ticket(
        self, ticket_id: int, tenant_id: int = 0, **kwargs
    ) -> ApiResponse[Ticket]:
        """更新工单"""
        # tenant_id must never be mutated
        kwargs.pop('tenant_id', None)

        async with get_db_session() as session:
            row = await self._fetch_ticket(session, ticket_id, tenant_id)
            if row is None:
                return ApiResponse.error(message='工单不存在', code=1404)

            for key, value in kwargs.items():
                if hasattr(row, key):
                    # Store enum values as strings in the DB
                    if hasattr(value, 'value'):
                        setattr(row, key, value.value)
                    else:
                        setattr(row, key, value)
            row.updated_at = datetime.utcnow()
            ticket = _row_to_ticket(row)

        return ApiResponse.success(data=ticket, message='工单更新成功')

    async def assign_ticket(
        self, ticket_id: int, assigned_to: int, tenant_id: int = 0
    ) -> ApiResponse[Ticket]:
        """分配客服"""
        result = await self.update_ticket(ticket_id, tenant_id=tenant_id, assigned_to=assigned_to)
        if result:
            result.message = '客服分配成功'
        return result

    async def add_reply(
        self,
        ticket_id: int,
        content: str,
        created_by: int,
        is_internal: bool = False,
        tenant_id: int = 0,
    ) -> ApiResponse[TicketReply]:
        """添加回复"""
        async with get_db_session() as session:
            ticket_row = await self._fetch_ticket(session, ticket_id, tenant_id)
            if ticket_row is None:
                return ApiResponse.error(message='工单不存在', code=1404)

            now = datetime.utcnow()
            reply_row = TicketReplyModel(
                ticket_id=ticket_id,
                tenant_id=ticket_row.tenant_id,
                content=content,
                is_internal=is_internal,
                created_by=created_by,
                created_at=now,
            )
            session.add(reply_row)

            # 更新 first_response_at（首次回复时间）
            if not ticket_row.first_response_at and not is_internal:
                ticket_row.first_response_at = now
                ticket_row.updated_at = now

            await session.flush()
            reply = _row_to_reply(reply_row)

        return ApiResponse.success(data=reply, message='回复添加成功')

    async def change_status(
        self, ticket_id: int, new_status: TicketStatus, tenant_id: int = 0
    ) -> ApiResponse[Ticket]:
        """改变状态"""
        async with get_db_session() as session:
            row = await self._fetch_ticket(session, ticket_id, tenant_id)
            if row is None:
                return ApiResponse.error(message='工单不存在', code=1404)

            now = datetime.utcnow()
            row.status = new_status.value
            row.updated_at = now

            # RESOLVED 时记录 resolved_at
            if new_status == TicketStatus.RESOLVED:
                row.resolved_at = now

            ticket = _row_to_ticket(row)

        return ApiResponse.success(data=ticket, message=f'工单状态已更新为{new_status}')

    async def get_customer_tickets(
        self, customer_id: int, tenant_id: int = 0
    ) -> List[Ticket]:
        """获取客户的所有工单"""
        async with get_db_session() as session:
            stmt = select(TicketModel).where(TicketModel.customer_id == customer_id)
            if tenant_id:
                stmt = stmt.where(
                    or_(TicketModel.tenant_id == tenant_id, TicketModel.tenant_id == 0)
                )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [_row_to_ticket(r) for r in rows]

    async def list_tickets(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assigned_to: Optional[int] = None,
        tenant_id: int = 0,
    ) -> ApiResponse[PaginatedData[Ticket]]:
        """工单列表"""
        async with get_db_session() as session:
            stmt = select(TicketModel)
            if tenant_id:
                stmt = stmt.where(
                    or_(TicketModel.tenant_id == tenant_id, TicketModel.tenant_id == 0)
                )
            if status is not None:
                stmt = stmt.where(TicketModel.status == status.value)
            if priority is not None:
                stmt = stmt.where(TicketModel.priority == priority.value)
            if assigned_to is not None:
                stmt = stmt.where(TicketModel.assigned_to == assigned_to)

            # Total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total: int = (await session.execute(count_stmt)).scalar_one()

            # Paginated results, ordered by created_at DESC
            stmt = (
                stmt.order_by(TicketModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        items = [_row_to_ticket(r) for r in rows]
        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message='查询成功',
        )

    async def get_sla_breaches(self, tenant_id: int = 0) -> List[Ticket]:
        """获取SLA超时的工单"""
        now = datetime.utcnow()
        async with get_db_session() as session:
            stmt = select(TicketModel).where(
                and_(
                    TicketModel.response_deadline < now,
                    TicketModel.resolved_at.is_(None),
                )
            )
            if tenant_id:
                stmt = stmt.where(
                    or_(TicketModel.tenant_id == tenant_id, TicketModel.tenant_id == 0)
                )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [_row_to_ticket(r) for r in rows]

    async def auto_assign(self, ticket_id: int, tenant_id: int = 0) -> ApiResponse[Dict]:
        """自动分配客服"""
        async with get_db_session() as session:
            row = await self._fetch_ticket(session, ticket_id, tenant_id)
            if row is None:
                return ApiResponse.error(message='工单不存在', code=1404)
            if row.assigned_to is not None:
                return ApiResponse.success(
                    data={'agent_id': row.assigned_to}, message='工单已分配客服'
                )

            agent_id = self._agent_pool[self._agent_index % len(self._agent_pool)]
            self._agent_index += 1
            row.assigned_to = agent_id
            row.updated_at = datetime.utcnow()

        return ApiResponse.success(data={'agent_id': agent_id}, message='自动分配客服成功')
