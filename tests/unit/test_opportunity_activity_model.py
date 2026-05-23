"""Unit tests for OpportunityActivityModel ORM model."""

from datetime import UTC, datetime

from db.models.opportunity_activity import OpportunityActivityModel


class TestOpportunityActivityModel:
    """Tests for OpportunityActivityModel."""

    def test_model_fields_present(self):
        """Model has all expected columns."""
        assert hasattr(OpportunityActivityModel, "id")
        assert hasattr(OpportunityActivityModel, "tenant_id")
        assert hasattr(OpportunityActivityModel, "opportunity_id")
        assert hasattr(OpportunityActivityModel, "event_type")
        assert hasattr(OpportunityActivityModel, "event_timestamp")
        assert hasattr(OpportunityActivityModel, "event_metadata")

    def test_to_dict_returns_all_fields(self):
        """to_dict returns all model fields."""
        now = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        activity = OpportunityActivityModel(
            id=1,
            tenant_id=42,
            opportunity_id=7,
            event_type="stage_changed",
            event_timestamp=now,
            event_metadata={"old_stage": "lead", "new_stage": "qualified"},
        )
        d = activity.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 42
        assert d["opportunity_id"] == 7
        assert d["event_type"] == "stage_changed"
        assert d["event_timestamp"] == now.isoformat()
        assert d["metadata"] == {"old_stage": "lead", "new_stage": "qualified"}

    def test_to_dict_metadata_default_empty_dict(self):
        """metadata defaults to {} when not provided."""
        now = datetime(2026, 2, 1, tzinfo=UTC)
        activity = OpportunityActivityModel(
            id=2,
            tenant_id=10,
            opportunity_id=3,
            event_type="note_added",
            event_timestamp=now,
        )
        d = activity.to_dict()
        assert d["metadata"] == {}

    def test_to_dict_event_timestamp_none(self):
        """to_dict handles None event_timestamp gracefully."""
        activity = OpportunityActivityModel(
            id=3,
            tenant_id=5,
            opportunity_id=1,
            event_type="test",
            event_timestamp=None,
        )
        d = activity.to_dict()
        assert d["event_timestamp"] is None

    def test_tablename(self):
        """Model maps to the correct table name."""
        assert OpportunityActivityModel.__tablename__ == "opportunity_activities"
