"""Unit tests for TicketCategorizationService.get_metrics()."""

import pytest
from unittest.mock import AsyncMock

from services.ticket_categorization_service import TicketCategorizationService


class MockResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class MockScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class TestGetMetrics:
    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        return TicketCategorizationService(mock_session)

    async def test_get_metrics_returns_structure(self, service, mock_session):
        """Happy path: verify all required keys are present and types are correct."""
        overall_row = type("Row", (), {"total": 100, "avg_confidence": 0.85, "override_count": 12})()
        type_rows = [
            type("R", (), {"category_type": "technical", "count": 60, "avg_confidence": 0.9, "overrides": 5})(),
            type("R", (), {"category_type": "billing", "count": 40, "avg_confidence": 0.8, "overrides": 7})(),
        ]
        priority_rows = [
            type("R", (), {"priority": "high", "count": 30, "avg_confidence": 0.85, "overrides": 4})(),
        ]

        service.session.execute = AsyncMock(side_effect=[
            MockResult(overall_row),
            MockScalarResult(type_rows),
            MockScalarResult(priority_rows),
        ])

        result = await service.get_metrics(tenant_id=1)

        assert "total_categorized" in result
        assert "override_count" in result
        assert "override_rate" in result
        assert "average_confidence" in result
        assert "by_type" in result
        assert "by_priority" in result
        assert isinstance(result["override_rate"], float)
        assert isinstance(result["by_type"], dict)
        assert isinstance(result["by_priority"], dict)
        assert result["total_categorized"] == 100
        assert result["override_count"] == 12
        assert result["override_rate"] == 0.12
        assert result["average_confidence"] == 0.85

    async def test_get_metrics_empty_result(self, service, mock_session):
        """Boundary: total=0 → override_rate must be 0.0, no division error."""
        overall_row = type("Row", (), {"total": 0, "avg_confidence": None, "override_count": 0})()

        service.session.execute = AsyncMock(side_effect=[
            MockResult(overall_row),
            MockScalarResult([]),
            MockScalarResult([]),
        ])

        result = await service.get_metrics(tenant_id=1)

        assert result["override_rate"] == 0.0
        assert result["total_categorized"] == 0
        assert result["override_count"] == 0
        assert result["average_confidence"] == 0.0
        assert result["by_type"] == {}
        assert result["by_priority"] == {}

    async def test_get_metrics_null_confidence_defaults_to_zero(self, service, mock_session):
        """Boundary: all NULL confidence → average_confidence returns 0.0."""
        overall_row = type("Row", (), {"total": 5, "avg_confidence": None, "override_count": 0})()

        service.session.execute = AsyncMock(side_effect=[
            MockResult(overall_row),
            MockScalarResult([]),
            MockScalarResult([]),
        ])

        result = await service.get_metrics(tenant_id=1)

        assert result["average_confidence"] == 0.0
        assert result["total_categorized"] == 5
