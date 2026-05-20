"""Unit tests for SLAService.get_sla_summary."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src/ on path
_project_root = Path(__file__).resolve().parents[2]
_src_root = _project_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from tests.unit.conftest import MockResult


# ---------------------------------------------------------------------------
# Minimal mock AsyncSession that supports session.scalar() for get_sla_summary
# ---------------------------------------------------------------------------


class _SlaMockSession:
    """Minimal mock AsyncSession that routes session.scalar() to SQL handlers.

    get_sla_summary calls session.scalar(select(func.count(...))) directly,
    not session.execute(), so we need to support that path.
    """

    def __init__(self, handlers):
        self._handlers = handlers

    async def scalar(self, sql, params=None):
        sql_text = str(sql).lower().strip()
        params = params or {}
        for h in self._handlers:
            result = h(sql_text, params)
            if result is not None:
                return result
        return None

    # Required for compatibility with SLAService __init__ signature
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# SQL handler for SLA summary COUNT queries
# ---------------------------------------------------------------------------


def make_sla_summary_handler(breached: int, at_risk: int, total: int):
    """Return a handler that responds to select count(...) from tickets queries.

    The handler detects which filter is active based on the SQL text and returns
    the appropriate count.
    """

    def handler(sql_text: str, params: dict):
        if not ("select" in sql_text and "count" in sql_text and "from tickets" in sql_text):
            return None

        # Check for ">" first — at_risk SQL has both "> now" and "<= now+4h" but no plain "<"
        # Breached SQL has only "< now" with no ">" comparison
        if ">" in sql_text:
            return at_risk

        # breached: resolved_at IS NULL AND response_deadline IS NOT NULL AND response_deadline < now
        if "<" in sql_text:
            return breached

        # total (no specific SLA filter — plain tenant_id filter)
        return total

    return handler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session_all_populated():
    """Session with 3 breached, 2 at_risk, 5 on_track (total 10)."""
    handler = make_sla_summary_handler(breached=3, at_risk=2, total=10)
    return _SlaMockSession([handler])


@pytest.fixture
def mock_db_session_empty():
    """Session with zero tickets."""
    handler = make_sla_summary_handler(breached=0, at_risk=0, total=0)
    return _SlaMockSession([handler])


@pytest.fixture
def mock_db_session_all_breached():
    """Session with only breached tickets."""
    handler = make_sla_summary_handler(breached=5, at_risk=0, total=5)
    return _SlaMockSession([handler])


@pytest.fixture
def mock_db_session_only_on_track():
    """Session with only on-track tickets (resolved / no deadline / far future)."""
    handler = make_sla_summary_handler(breached=0, at_risk=0, total=4)
    return _SlaMockSession([handler])


@pytest.fixture
def mock_db_session_tenant_1():
    """Session for tenant 1 — 2 breached, 1 at_risk, 7 total."""
    handler = make_sla_summary_handler(breached=2, at_risk=1, total=7)
    return _SlaMockSession([handler])


@pytest.fixture
def mock_db_session_tenant_2():
    """Session for tenant 2 — 0 breached, 3 at_risk, 3 total."""
    handler = make_sla_summary_handler(breached=0, at_risk=3, total=3)
    return _SlaMockSession([handler])


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

        handler = make_sla_summary_handler(breached=0, at_risk=8, total=8)
        session = _SlaMockSession([handler])
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

        # Handler always returns None — simulates unexpected NULL from DB
        null_session = _SlaMockSession([lambda sql, params: None])
        svc = SLAService(null_session)
        result = await svc.get_sla_summary(tenant_id=1)

        assert result["breached"] == 0
        assert result["at_risk"] == 0
        assert result["on_track"] == 0
        assert result["total_tickets"] == 0

    async def test_large_counts(self):
        """Service handles large integer counts without overflow or type errors."""
        from services.sla_service import SLAService

        handler = make_sla_summary_handler(breached=50_000, at_risk=30_000, total=100_000)
        session = _SlaMockSession([handler])
        svc = SLAService(session)
        result = await svc.get_sla_summary(tenant_id=42)

        assert result["breached"] == 50_000
        assert result["at_risk"] == 30_000
        assert result["on_track"] == 20_000  # 100_000 - 50_000 - 30_000
        assert result["total_tickets"] == 100_000

    async def test_tenant_id_zero_is_valid(self):
        """tenant_id=0 (from ctx.tenant_id=None fallback) is accepted without error."""
        from services.sla_service import SLAService

        handler = make_sla_summary_handler(breached=1, at_risk=1, total=3)
        session = _SlaMockSession([handler])
        svc = SLAService(session)
        result = await svc.get_sla_summary(tenant_id=0)

        assert result["total_tickets"] == 3
        assert result["on_track"] == 1  # 3 - 1 - 1

    async def test_on_track_is_derived_not_queried(self):
        """on_track = total - breached - at_risk (no separate SQL query for it)."""
        from services.sla_service import SLAService

        # Provide a session that counts each scalar() call
        call_count = []

        async def counting_scalar(sql, params=None):
            call_count.append(str(sql).lower())
            sql_text = str(sql).lower()
            if ">" in sql_text:
                return 2  # at_risk
            if "<" in sql_text:
                return 3  # breached
            return 10  # total

        class CountingSession:
            async def scalar(self, sql, params=None):
                return await counting_scalar(sql, params)

        svc = SLAService(CountingSession())
        result = await svc.get_sla_summary(tenant_id=1)

        # Exactly 3 scalar calls: breached, at_risk, total
        assert len(call_count) == 3
        assert result["on_track"] == 5  # 10 - 3 - 2