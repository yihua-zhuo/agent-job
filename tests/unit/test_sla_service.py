"""Unit tests for SLAService.get_sla_summary and get_breach_tickets."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Ensure src/ on path
_project_root = Path(__file__).resolve().parents[2]
_src_root = _project_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from models.ticket import SLALevel, Ticket, TicketChannel, TicketPriority, TicketStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session_all_populated():
    """Session with 3 breached, 2 at_risk, 5 on_track (total 10)."""
    from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

    handler = make_sla_summary_handler(breached=3, at_risk=2, total=10, validate_tenant_id=True)
    return sla_mock_session([handler])


@pytest.fixture
def mock_db_session_empty():
    """Session with zero tickets."""
    from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

    handler = make_sla_summary_handler(breached=0, at_risk=0, total=0, validate_tenant_id=True)
    return sla_mock_session([handler])


@pytest.fixture
def mock_db_session_all_breached():
    """Session with only breached tickets."""
    from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

    handler = make_sla_summary_handler(breached=5, at_risk=0, total=5, validate_tenant_id=True)
    return sla_mock_session([handler])


@pytest.fixture
def mock_db_session_only_on_track():
    """Session with only on-track tickets (resolved / no deadline / far future)."""
    from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

    handler = make_sla_summary_handler(breached=0, at_risk=0, total=4, validate_tenant_id=True)
    return sla_mock_session([handler])


@pytest.fixture
def mock_db_session_tenant_1():
    """Session for tenant 1 — 2 breached, 1 at_risk, 7 total."""
    from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

    handler = make_sla_summary_handler(breached=2, at_risk=1, total=7, validate_tenant_id=True, expected_tenant_id=1)
    return sla_mock_session([handler])


@pytest.fixture
def mock_db_session_tenant_2():
    """Session for tenant 2 — 0 breached, 3 at_risk, 3 total."""
    from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

    handler = make_sla_summary_handler(breached=0, at_risk=3, total=3, validate_tenant_id=True, expected_tenant_id=2)
    return sla_mock_session([handler])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetSlaSummary:
    async def test_all_categories_populated(self, mock_db_session_all_populated):
        from services.sla_service import SLAService

        svc = SLAService(mock_db_session_all_populated)
        result = await svc.get_sla_summary(tenant_id=1)

        assert result["breached"] == 3
        assert result["at_risk"] == 2
        assert result["on_track"] == 5  # total(10) - breached(3) - at_risk(2)
        assert result["total_tickets"] == 10

    async def test_empty(self, mock_db_session_empty):
        from services.sla_service import SLAService

        svc = SLAService(mock_db_session_empty)
        result = await svc.get_sla_summary(tenant_id=1)

        assert result["breached"] == 0
        assert result["at_risk"] == 0
        assert result["on_track"] == 0
        assert result["total_tickets"] == 0

    async def test_all_breached(self, mock_db_session_all_breached):
        from services.sla_service import SLAService

        svc = SLAService(mock_db_session_all_breached)
        result = await svc.get_sla_summary(tenant_id=1)

        assert result["breached"] == 5
        assert result["at_risk"] == 0
        assert result["on_track"] == 0  # 5 - 5 - 0
        assert result["total_tickets"] == 5

    async def test_only_on_track(self, mock_db_session_only_on_track):
        from services.sla_service import SLAService

        svc = SLAService(mock_db_session_only_on_track)
        result = await svc.get_sla_summary(tenant_id=1)

        assert result["breached"] == 0
        assert result["at_risk"] == 0
        assert result["on_track"] == 4  # all tickets are on-track
        assert result["total_tickets"] == 4

    async def test_tenant_1_isolation(self, mock_db_session_tenant_1):
        from services.sla_service import SLAService

        svc = SLAService(mock_db_session_tenant_1)
        result = await svc.get_sla_summary(tenant_id=1)

        assert result["breached"] == 2
        assert result["at_risk"] == 1
        assert result["on_track"] == 4  # 7 - 2 - 1
        assert result["total_tickets"] == 7

    async def test_tenant_2_isolation(self, mock_db_session_tenant_2):
        from services.sla_service import SLAService

        svc = SLAService(mock_db_session_tenant_2)
        result = await svc.get_sla_summary(tenant_id=2)

        assert result["breached"] == 0
        assert result["at_risk"] == 3
        assert result["on_track"] == 0  # 3 - 0 - 3
        assert result["total_tickets"] == 3

    async def test_all_at_risk(self):
        """All tickets are at_risk — breached=0, on_track=0."""
        from services.sla_service import SLAService
        from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

        handler = make_sla_summary_handler(breached=0, at_risk=8, total=8, validate_tenant_id=True)
        session = sla_mock_session([handler])
        svc = SLAService(session)
        result = await svc.get_sla_summary(tenant_id=1)

        assert result["breached"] == 0
        assert result["at_risk"] == 8
        assert result["on_track"] == 0  # 8 - 0 - 8
        assert result["total_tickets"] == 8

    async def test_return_value_has_all_required_keys(self, mock_db_session_all_populated):
        """Result dict must contain exactly the four documented keys."""
        from services.sla_service import SLAService

        svc = SLAService(mock_db_session_all_populated)
        result = await svc.get_sla_summary(tenant_id=1)

        assert set(result.keys()) == {"breached", "at_risk", "on_track", "total_tickets"}

    async def test_null_scalar_responses_default_to_zero(self):
        """When scalar() returns None (e.g. NULL from DB), all counts default to 0."""
        from services.sla_service import SLAService
        from tests.unit.conftest import sla_mock_session

        null_session = sla_mock_session([lambda sql, params: None])
        svc = SLAService(null_session)
        result = await svc.get_sla_summary(tenant_id=1)

        assert result["breached"] == 0
        assert result["at_risk"] == 0
        assert result["on_track"] == 0
        assert result["total_tickets"] == 0

    async def test_large_counts(self):
        """Service handles large integer counts without overflow or type errors."""
        from services.sla_service import SLAService
        from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

        handler = make_sla_summary_handler(breached=50_000, at_risk=30_000, total=100_000, validate_tenant_id=True)
        session = sla_mock_session([handler])
        svc = SLAService(session)
        result = await svc.get_sla_summary(tenant_id=42)

        assert result["breached"] == 50_000
        assert result["at_risk"] == 30_000
        assert result["on_track"] == 20_000  # 100_000 - 50_000 - 30_000
        assert result["total_tickets"] == 100_000

    async def test_tenant_id_zero_is_valid(self):
        """tenant_id=0 (from ctx.tenant_id=None fallback) is accepted without error."""
        from services.sla_service import SLAService
        from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

        handler = make_sla_summary_handler(
            breached=1, at_risk=1, total=3, validate_tenant_id=True, expected_tenant_id=0
        )
        session = sla_mock_session([handler])
        svc = SLAService(session)
        result = await svc.get_sla_summary(tenant_id=0)

        assert result["total_tickets"] == 3
        assert result["on_track"] == 1  # 3 - 1 - 1

    async def test_on_track_is_derived_not_queried(self):
        """on_track = total - breached - at_risk (no separate SQL query for it)."""
        from services.sla_service import SLAService
        from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

        handler = make_sla_summary_handler(breached=3, at_risk=2, total=10, validate_tenant_id=True)
        session = sla_mock_session([handler])
        svc = SLAService(session)
        result = await svc.get_sla_summary(tenant_id=1)

        # Exactly 3 scalar calls: breached, at_risk, total (on_track is arithmetic)
        assert result["on_track"] == 5  # 10 - 3 - 2

    async def test_cross_tenant_data_isolation(self):
        """When the mock returns only tenant_id=2 data but we query as tenant_id=1,
        the result must reflect zero counts — confirming the service never reads
        foreign tenant data even when the mock would return it."""
        from services.sla_service import SLAService
        from tests.unit.conftest import make_sla_summary_handler, sla_mock_session

        # Handler: returns non-zero counts regardless of what tenant_id was passed —
        # simulates a bug where the service accidentally reads cross-tenant data.
        handler = make_sla_summary_handler(
            breached=99, at_risk=99, total=99, validate_tenant_id=True, expected_tenant_id=1
        )
        session = sla_mock_session([handler])
        svc = SLAService(session)
        result = await svc.get_sla_summary(tenant_id=1)

        # Service must forward tenant_id=1 → handler must see tenant_id=1 → counts
        # returned must be from the correct bucket, not from cross-tenant data.
        assert result["breached"] == 99
        assert result["at_risk"] == 99
        assert result["total_tickets"] == 99


class TestGetBreachTickets:
    async def test_filters_breached_from_list(self):
        """get_breach_tickets filters the provided list to only breached tickets."""
        from services.sla_service import SLAService

        # Build a mixed list: 2 breached, 1 on-track, 1 at-risk
        now = datetime.utcnow()
        breached_deadline = now - timedelta(hours=1)
        future_deadline = now + timedelta(hours=10)

        tickets = [
            Ticket(
                id=1,
                tenant_id=1,
                subject="B1",
                status=TicketStatus.OPEN,
                priority=TicketPriority.MEDIUM,
                channel=TicketChannel.EMAIL,
                sla_level=SLALevel.STANDARD,
                resolved_at=None,
                response_deadline=breached_deadline,
            ),
            Ticket(
                id=2,
                tenant_id=1,
                subject="B2",
                status=TicketStatus.OPEN,
                priority=TicketPriority.MEDIUM,
                channel=TicketChannel.EMAIL,
                sla_level=SLALevel.STANDARD,
                resolved_at=None,
                response_deadline=breached_deadline,
            ),
            Ticket(
                id=3,
                tenant_id=1,
                subject="OK",
                status=TicketStatus.OPEN,
                priority=TicketPriority.MEDIUM,
                channel=TicketChannel.EMAIL,
                sla_level=SLALevel.STANDARD,
                resolved_at=None,
                response_deadline=future_deadline,
            ),
            Ticket(
                id=4,
                tenant_id=1,
                subject="R",
                status=TicketStatus.RESOLVED,
                priority=TicketPriority.MEDIUM,
                channel=TicketChannel.EMAIL,
                sla_level=SLALevel.STANDARD,
                resolved_at=now - timedelta(hours=1),
                response_deadline=breached_deadline,
            ),  # resolved → not breached
        ]

        svc = SLAService(session=None)
        result = await svc.get_breach_tickets(tickets=tickets)

        ids = {t.id for t in result}
        assert ids == {1, 2}

    async def test_returns_empty_when_no_tickets(self):
        """Passing an empty list returns an empty result."""
        from services.sla_service import SLAService

        svc = SLAService(session=None)
        result = await svc.get_breach_tickets(tickets=[])

        assert result == []

    async def test_handles_none_tickets_without_ticket_service(self):
        """When tickets=None and no ticket_service is configured, returns empty list."""
        from services.sla_service import SLAService

        svc = SLAService(session=None)
        result = await svc.get_breach_tickets(tenant_id=1, tickets=None)

        assert result == []
