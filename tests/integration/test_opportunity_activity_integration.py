"""
Integration tests for OpportunityActivityModel.

Run against a real PostgreSQL database (via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_opportunity_activity_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from db.models.opportunity import OpportunityModel
from db.models.opportunity_activity import OpportunityActivityModel


@pytest.mark.integration
class TestOpportunityActivityIntegration:
    """Full lifecycle tests for OpportunityActivityModel via the real DB."""

    async def test_insert_and_select(self, db_schema, tenant_id, async_session):
        """Round-trip: insert an opportunity and its activity, then fetch."""
        # Seed an opportunity (FK dependency)
        opp = OpportunityModel(
            tenant_id=tenant_id,
            customer_id=1,
            name="Test Deal",
            stage="lead",
        )
        async_session.add(opp)
        await async_session.flush()

        # Insert activity
        now = datetime(2026, 3, 10, 14, 0, 0, tzinfo=UTC)
        activity = OpportunityActivityModel(
            tenant_id=tenant_id,
            opportunity_id=opp.id,
            event_type="created",
            event_timestamp=now,
            event_metadata={"source": "web", "campaign": "spring_sale"},
        )
        async_session.add(activity)
        await async_session.flush()
        await async_session.commit()

        # Fetch by id
        result = await async_session.execute(
            select(OpportunityActivityModel).where(OpportunityActivityModel.id == activity.id)
        )
        fetched = result.scalar_one_or_none()

        assert fetched is not None
        assert fetched.tenant_id == tenant_id
        assert fetched.opportunity_id == opp.id
        assert fetched.event_type == "created"
        assert fetched.event_timestamp == now
        assert fetched.event_metadata == {"source": "web", "campaign": "spring_sale"}

    async def test_metadata_json_arbitrary_values(self, db_schema, tenant_id, async_session):
        """metadata column stores arbitrary JSON without type errors."""
        opp = OpportunityModel(
            tenant_id=tenant_id,
            customer_id=1,
            name="Metadata Test",
            stage="qualified",
        )
        async_session.add(opp)
        await async_session.flush()

        complex_metadata = {
            "user_id": 99,
            "changes": {"amount": {"old": 1000, "new": 1500}, "stage": {"old": "lead", "new": "qualified"}},
            "tags": ["important", "q1"],
            "nested": [{"key": "value", "count": 3}],
        }
        activity = OpportunityActivityModel(
            tenant_id=tenant_id,
            opportunity_id=opp.id,
            event_type="updated",
            event_timestamp=datetime(2026, 4, 1, tzinfo=UTC),
            event_metadata=complex_metadata,
        )
        async_session.add(activity)
        await async_session.flush()
        await async_session.commit()

        result = await async_session.execute(
            select(OpportunityActivityModel).where(OpportunityActivityModel.id == activity.id)
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.event_metadata == complex_metadata

    async def test_fk_cascade_deletes_activity(self, db_schema, tenant_id, async_session):
        """Deleting the parent opportunity removes the activity row (FK cascade)."""
        opp = OpportunityModel(
            tenant_id=tenant_id,
            customer_id=1,
            name="Cascade Test",
            stage="lead",
        )
        async_session.add(opp)
        await async_session.flush()

        activity = OpportunityActivityModel(
            tenant_id=tenant_id,
            opportunity_id=opp.id,
            event_type="created",
            event_timestamp=datetime(2026, 5, 1, tzinfo=UTC),
            event_metadata={},
        )
        async_session.add(activity)
        await async_session.flush()
        await async_session.commit()

        # Verify activity exists
        result = await async_session.execute(
            select(OpportunityActivityModel).where(OpportunityActivityModel.id == activity.id)
        )
        assert result.scalar_one_or_none() is not None

        # Delete the parent opportunity — cascade should remove the activity
        await async_session.delete(opp)
        await async_session.commit()

        result = await async_session.execute(
            select(OpportunityActivityModel).where(OpportunityActivityModel.id == activity.id)
        )
        assert result.scalar_one_or_none() is None

    async def test_indexes_present_on_tenant_id_and_opportunity_id(self, db_schema, tenant_id, async_session):
        """Both tenant_id and opportunity_id columns have indexes in the DB."""
        opp = OpportunityModel(
            tenant_id=tenant_id,
            customer_id=1,
            name="Index Test",
            stage="lead",
        )
        async_session.add(opp)
        await async_session.flush()

        activity = OpportunityActivityModel(
            tenant_id=tenant_id,
            opportunity_id=opp.id,
            event_type="index_check",
            event_timestamp=datetime(2026, 5, 1, tzinfo=UTC),
            event_metadata={},
        )
        async_session.add(activity)
        await async_session.flush()
        await async_session.commit()

        # Check indexes via pg_indexes
        result = await async_session.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'opportunity_activities'")
        )
        indexes = {row[0] for row in result.fetchall()}
        assert any("tenant_id" in idx for idx in indexes), f"No tenant_id index found: {indexes}"
        assert any("opportunity_id" in idx for idx in indexes), f"No opportunity_id index found: {indexes}"
