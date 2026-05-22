"""Integration tests for TicketCategorizationModel persistence.

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_ticket_categorization_integration.py -v
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from db.models.ticket_categorization import TicketCategorizationModel


@pytest.mark.integration
class TestTicketCategorizationIntegration:
    async def test_create_and_fetch_categorization(self, db_schema, tenant_id, async_session):
        """Full field round-trip: create a categorization and fetch it back."""
        from models.ticket import TicketChannel, TicketPriority
        from services.ticket_service import TicketService

        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="Billing issue",
            description="I was charged twice",
            customer_id=1,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
            tenant_id=tenant_id,
        )

        cat = TicketCategorizationModel(
            tenant_id=tenant_id,
            ticket_id=ticket.id,
            category_type="billing",
            priority="high",
            confidence=Decimal("0.9500"),
            reasons={"keywords": ["invoice", "charge", "double"]},
            suggested_assignee_id=5,
            suggested_team="Billing-Team",
            human_override=True,
        )
        async_session.add(cat)
        await async_session.flush()
        await async_session.commit()

        from sqlalchemy import select
        result = await async_session.execute(
            select(TicketCategorizationModel).where(
                TicketCategorizationModel.ticket_id == ticket.id
            )
        )
        fetched = result.scalar_one_or_none()

        assert fetched is not None
        assert fetched.tenant_id == tenant_id
        assert fetched.ticket_id == ticket.id
        assert fetched.category_type == "billing"
        assert fetched.priority == "high"
        assert fetched.confidence == Decimal("0.9500")
        assert fetched.reasons == {"keywords": ["invoice", "charge", "double"]}
        assert fetched.suggested_assignee_id == 5
        assert fetched.suggested_team == "Billing-Team"
        assert fetched.human_override is True
        assert fetched.created_at is not None
        assert fetched.updated_at is not None

    async def test_human_override_false_round_trip(self, db_schema, tenant_id, async_session):
        """human_override=False is stored and retrieved correctly."""
        from models.ticket import TicketChannel, TicketPriority
        from services.ticket_service import TicketService

        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="General question",
            description="How do I reset my password?",
            customer_id=1,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.LOW,
            tenant_id=tenant_id,
        )

        cat = TicketCategorizationModel(
            tenant_id=tenant_id,
            ticket_id=ticket.id,
            category_type="faq",
            human_override=False,
        )
        async_session.add(cat)
        await async_session.flush()
        await async_session.commit()

        from sqlalchemy import select
        result = await async_session.execute(
            select(TicketCategorizationModel).where(
                TicketCategorizationModel.ticket_id == ticket.id
            )
        )
        fetched = result.scalar_one_or_none()

        assert fetched is not None
        assert fetched.human_override is False
        assert fetched.category_type == "faq"
        assert fetched.priority is None
        assert fetched.confidence is None
        assert fetched.reasons is None

    async def test_to_dict_on_db_fetched_record(self, db_schema, tenant_id, async_session):
        """to_dict() produces correct output on a record that came from the DB."""
        from models.ticket import TicketChannel, TicketPriority
        from services.ticket_service import TicketService

        svc = TicketService(async_session)
        ticket = await svc.create_ticket(
            subject="Order not received",
            description="My order hasn't arrived",
            customer_id=1,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.HIGH,
            tenant_id=tenant_id,
        )

        cat = TicketCategorizationModel(
            tenant_id=tenant_id,
            ticket_id=ticket.id,
            category_type="shipping",
            priority="urgent",
            confidence=Decimal("0.8723"),
            reasons={"source": "LLM", "signals": ["tracking", "missing"]},
            suggested_team="Logistics",
            human_override=False,
        )
        async_session.add(cat)
        await async_session.flush()
        await async_session.commit()

        from sqlalchemy import select
        result = await async_session.execute(
            select(TicketCategorizationModel).where(
                TicketCategorizationModel.ticket_id == ticket.id
            )
        )
        fetched = result.scalar_one()
        d = fetched.to_dict()

        assert d["category_type"] == "shipping"
        assert d["priority"] == "urgent"
        assert d["confidence"] == Decimal("0.8723")
        assert d["reasons"] == {"source": "LLM", "signals": ["tracking", "missing"]}
        assert d["suggested_team"] == "Logistics"
        assert d["human_override"] is False
        assert isinstance(d["created_at"], str)
        assert isinstance(d["updated_at"], str)
