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