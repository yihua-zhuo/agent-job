"""Integration tests for SLA summary endpoint and service."""

from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.integration


async def test_sla_summary_all_categories(db_schema, tenant_id, async_session, _seed_customer):
    """Seed 3 breached, 2 at_risk, 5 on_track tickets; assert counts match."""
    from db.models.ticket import TicketModel
    from services.sla_service import SLAService

    now = datetime.now(UTC)
    cid = _seed_customer

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
                customer_id=cid,
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
                customer_id=0,
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
                customer_id=0,
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
                customer_id=0,
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
                customer_id=0,
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
                customer_id=0,
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
                customer_id=0,
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
            customer_id=0,
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


async def test_sla_summary_no_deadline_tickets_counted_as_on_track(db_schema, tenant_id, async_session):
    """Tickets with no response_deadline should be counted as on_track, not breached."""
    from db.models.ticket import TicketModel
    from services.sla_service import SLAService

    now = datetime.now(UTC)

    # 3 tickets with no deadline (response_deadline=None)
    for _ in range(3):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id,
                subject="NoDeadline",
                description="desc",
                status="open",
                priority="medium",
                channel="email",
                customer_id=0,
                resolved_at=None,
                response_deadline=None,
            )
        )

    # 1 breached ticket to ensure non-deadline tickets aren't misclassified
    async_session.add(
        TicketModel(
            tenant_id=tenant_id,
            subject="Breached",
            description="desc",
            status="open",
            priority="medium",
            channel="email",
            customer_id=0,
            resolved_at=None,
            response_deadline=now - timedelta(hours=2),
        )
    )

    await async_session.flush()

    svc = SLAService(async_session)
    result = await svc.get_sla_summary(tenant_id=tenant_id)

    assert result["breached"] == 1, f"expected 1 breached, got {result['breached']}"
    assert result["at_risk"] == 0, f"expected 0 at_risk, got {result['at_risk']}"
    assert result["on_track"] == 3, f"expected 3 on_track, got {result['on_track']}"
    assert result["total_tickets"] == 4, f"expected 4 total, got {result['total_tickets']}"


async def test_sla_summary_resolved_tickets_not_counted_as_breached(db_schema, tenant_id, async_session):
    """Resolved tickets with past deadlines must NOT be counted as breached."""
    from db.models.ticket import TicketModel
    from services.sla_service import SLAService

    now = datetime.now(UTC)

    # 4 resolved tickets whose deadline has already passed — NOT breached
    for _ in range(4):
        async_session.add(
            TicketModel(
                tenant_id=tenant_id,
                subject="Resolved",
                description="desc",
                status="resolved",
                priority="medium",
                channel="email",
                customer_id=0,
                resolved_at=now - timedelta(hours=1),
                response_deadline=now - timedelta(hours=10),
            )
        )

    await async_session.flush()

    svc = SLAService(async_session)
    result = await svc.get_sla_summary(tenant_id=tenant_id)

    assert result["breached"] == 0, f"expected 0 breached, got {result['breached']}"
    assert result["at_risk"] == 0, f"expected 0 at_risk, got {result['at_risk']}"
    assert result["on_track"] == 4, f"expected 4 on_track, got {result['on_track']}"
    assert result["total_tickets"] == 4


async def test_sla_summary_result_has_all_keys(db_schema, tenant_id, async_session):
    """Result dict must always contain all four documented keys, even when empty."""
    from services.sla_service import SLAService

    svc = SLAService(async_session)
    result = await svc.get_sla_summary(tenant_id=tenant_id)

    assert "breached" in result
    assert "at_risk" in result
    assert "on_track" in result
    assert "total_tickets" in result
    # All values are non-negative integers
    for key in ("breached", "at_risk", "on_track", "total_tickets"):
        assert isinstance(result[key], int), f"{key} should be int, got {type(result[key])}"
        assert result[key] >= 0, f"{key} should be >= 0, got {result[key]}"


async def test_sla_summary_at_risk_boundary_just_inside(db_schema, tenant_id, async_session):
    """Deadline exactly 3h 59m from now is within the at_risk window (< 4h)."""
    from db.models.ticket import TicketModel
    from services.sla_service import SLAService

    now = datetime.now(UTC)

    # 1 ticket: deadline in 3h59m — should be at_risk
    async_session.add(
        TicketModel(
            tenant_id=tenant_id,
            subject="AtRiskBoundary",
            description="desc",
            status="open",
            priority="medium",
            channel="email",
            customer_id=0,
            resolved_at=None,
            response_deadline=now + timedelta(hours=3, minutes=59),
        )
    )

    await async_session.flush()

    svc = SLAService(async_session)
    result = await svc.get_sla_summary(tenant_id=tenant_id)

    assert result["at_risk"] == 1, f"expected 1 at_risk, got {result['at_risk']}"
    assert result["breached"] == 0
    assert result["total_tickets"] == 1


async def test_sla_summary_at_risk_boundary_just_outside(db_schema, tenant_id, async_session):
    """Deadline 4h 1m from now is outside the at_risk window → on_track."""
    from db.models.ticket import TicketModel
    from services.sla_service import SLAService

    now = datetime.now(UTC)

    # 1 ticket: deadline in 4h1m — should be on_track (> 4h threshold)
    async_session.add(
        TicketModel(
            tenant_id=tenant_id,
            subject="OnTrackBoundary",
            description="desc",
            status="open",
            priority="medium",
            channel="email",
            customer_id=0,
            resolved_at=None,
            response_deadline=now + timedelta(hours=4, minutes=1),
        )
    )

    await async_session.flush()

    svc = SLAService(async_session)
    result = await svc.get_sla_summary(tenant_id=tenant_id)

    assert result["at_risk"] == 0, f"expected 0 at_risk, got {result['at_risk']}"
    assert result["breached"] == 0
    assert result["on_track"] == 1, f"expected 1 on_track, got {result['on_track']}"
    assert result["total_tickets"] == 1
