"""Integration tests for SLA summary endpoint and service."""
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.integration


async def test_sla_summary_all_categories(db_schema, tenant_id, async_session):
    """Seed 3 breached, 2 at_risk, 5 on_track tickets; assert counts match."""
    from db.models.ticket import TicketModel
    from services.sla_service import SLAService

    now = datetime.now(UTC)
    four_hours = timedelta(hours=4)

    # 3 breached: resolved_at=None, deadline in past
    for _ in range(3):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id,
                subject="Breached",
                description="desc",
                status="open",
                priority="medium",
                channel="email",
                customer_id=1,
                resolved_at=None,
                response_deadline=now - timedelta(hours=5),
            )
        )

    # 2 at_risk: resolved_at=None, deadline within 4h window
    for _ in range(2):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id,
                subject="AtRisk",
                description="desc",
                status="open",
                priority="medium",
                channel="email",
                customer_id=1,
                resolved_at=None,
                response_deadline=now + timedelta(hours=2),
            )
        )

    # 5 on_track: 3 resolved + 2 with deadline > 4h
    for _ in range(3):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id,
                subject="Resolved",
                description="desc",
                status="open",
                priority="medium",
                channel="email",
                customer_id=1,
                resolved_at=now - timedelta(hours=1),
                response_deadline=now - timedelta(hours=5),  # also past but resolved overrides
            )
        )
    for _ in range(2):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id,
                subject="OnTrack",
                description="desc",
                status="open",
                priority="medium",
                channel="email",
                customer_id=1,
                resolved_at=None,
                response_deadline=now + timedelta(hours=6),
            )
        )

    await async_session.flush()

    svc = SLAService(async_session)
    result = await svc.get_sla_summary(tenant_id=tenant_id)

    assert result["breached"] == 3, f"expected 3 breached, got {result['breached']}"
    assert result["at_risk"] == 2, f"expected 2 at_risk, got {result['at_risk']}"
    assert result["on_track"] == 5, f"expected 5 on_track, got {result['on_track']}"
    assert result["total_tickets"] == 10, f"expected 10 total, got {result['total_tickets']}"


async def test_sla_summary_empty(db_schema, tenant_id, async_session):
    """No tickets → all counts zero, total_tickets = 0."""
    from services.sla_service import SLAService

    svc = SLAService(async_session)
    result = await svc.get_sla_summary(tenant_id=tenant_id)

    assert result["breached"] == 0
    assert result["at_risk"] == 0
    assert result["on_track"] == 0
    assert result["total_tickets"] == 0


async def test_sla_summary_tenant_isolation(db_schema, tenant_id, tenant_id_2, async_session):
    """Seed tickets for two different tenant_ids; each query only sees its own."""
    from datetime import UTC

    from db.models.ticket import TicketModel
    from services.sla_service import SLAService

    now = datetime.now(UTC)

    # Tenant 1: 2 breached, 3 at_risk
    for _ in range(2):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id,
                subject="Breached",
                description="desc",
                status="open",
                priority="medium",
                channel="email",
                customer_id=1,
                resolved_at=None,
                response_deadline=now - timedelta(hours=3),
            )
        )
    for _ in range(3):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id,
                subject="AtRisk",
                description="desc",
                status="open",
                priority="medium",
                channel="email",
                customer_id=1,
                resolved_at=None,
                response_deadline=now + timedelta(hours=2),
            )
        )

    # Tenant 2: 5 breached, 1 at_risk
    for _ in range(5):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id_2,
                subject="Breached",
                description="desc",
                status="open",
                priority="medium",
                channel="email",
                customer_id=1,
                resolved_at=None,
                response_deadline=now - timedelta(hours=3),
            )
        )
    async_session.add(
        TicketModel(
            tenant_id=tenant_id_2,
            subject="AtRisk",
            description="desc",
            status="open",
            priority="medium",
            channel="email",
            customer_id=1,
            resolved_at=None,
            response_deadline=now + timedelta(hours=2),
        )
    )

    await async_session.flush()

    svc = SLAService(async_session)

    r1 = await svc.get_sla_summary(tenant_id=tenant_id)
    assert r1["breached"] == 2
    assert r1["at_risk"] == 3
    assert r1["total_tickets"] == 5

    r2 = await svc.get_sla_summary(tenant_id=tenant_id_2)
    assert r2["breached"] == 5
    assert r2["at_risk"] == 1
    assert r2["total_tickets"] == 6