"""Unit tests for Activity model."""
import pytest
from datetime import datetime, UTC
from src.models.activity import Activity, ActivityType


class TestActivityInit:
    """Tests for Activity __post_init__ method."""

    def test_post_init_clears_none_id(self):
        """Lines 30-31: id None stays None."""
        activity = Activity(
            customer_id=1, type=ActivityType.CALL,
            content="Call about order", created_by=1
        )
        assert activity.id is None

    def test_post_init_clears_none_opportunity_id(self):
        """Lines 32-33: opportunity_id None stays None."""
        activity = Activity(
            customer_id=1, type=ActivityType.CALL,
            content="Call about order", created_by=1
        )
        assert activity.opportunity_id is None

    def test_post_init_sets_default_created_at(self):
        """Lines 34-35: created_at defaults to now when None."""
        activity = Activity(
            customer_id=1, type=ActivityType.CALL,
            content="Call about order", created_by=1
        )
        assert activity.created_at is not None


class TestActivityToDict:
    """Tests for Activity.to_dict() method."""

    def test_to_dict_includes_all_fields(self):
        """Line 39: to_dict returns all fields."""
        now = datetime.now(UTC)
        activity = Activity(
            id=1, tenant_id=10, customer_id=100, type=ActivityType.EMAIL,
            content="Sent quote", created_by=5, created_at=now,
            opportunity_id=50
        )
        d = activity.to_dict()
        assert d['id'] == 1
        assert d['tenant_id'] == 10
        assert d['customer_id'] == 100
        assert d['type'] == 'email'
        assert d['content'] == 'Sent quote'
        assert d['created_by'] == 5
        assert d['opportunity_id'] == 50

    def test_to_dict_converts_enum_type_to_value(self):
        """Line 44: ActivityType enum converted to string value."""
        activity = Activity(
            customer_id=1, type=ActivityType.MEETING,
            content="Reviewed proposal", created_by=1
        )
        assert activity.to_dict()['type'] == 'meeting'

    def test_to_dict_converts_datetime_to_iso(self):
        """Line 47: datetime converted to ISO string."""
        now = datetime.now(UTC)
        activity = Activity(
            customer_id=1, type=ActivityType.NOTE,
            content="Note", created_by=1, created_at=now
        )
        iso_str = activity.to_dict()['created_at']
        # Should be parseable as ISO format
        assert datetime.fromisoformat(iso_str.replace('Z', '+00:00')) is not None


class TestActivityFromDict:
    """Tests for Activity.from_dict() class method."""

    def test_from_dict_parses_string_type(self):
        """Lines 54-55: string type is converted to ActivityType enum."""
        data = {
            'customer_id': 1, 'type': 'call',
            'content': 'Test call', 'created_by': 1
        }
        activity = Activity.from_dict(data)
        assert activity.type == ActivityType.CALL

    def test_from_dict_keeps_activity_type_enum(self):
        """Lines 56-57: ActivityType enum is kept as-is."""
        data = {
            'customer_id': 1, 'type': ActivityType.EMAIL,
            'content': 'Test email', 'created_by': 1
        }
        activity = Activity.from_dict(data)
        assert activity.type == ActivityType.EMAIL

    def test_from_dict_parses_iso_datetime_string(self):
        """Lines 60-61: ISO datetime string is parsed to datetime."""
        iso = "2024-01-15T10:30:00+00:00"
        data = {
            'customer_id': 1, 'type': 'note',
            'content': 'Test', 'created_by': 1, 'created_at': iso
        }
        activity = Activity.from_dict(data)
        assert activity.created_at == datetime.fromisoformat(iso)

    def test_from_dict_defaults_created_at_to_now_when_none(self):
        """Lines 62-63: None created_at defaults to current time."""
        data = {
            'customer_id': 1, 'type': 'note',
            'content': 'Test', 'created_by': 1, 'created_at': None
        }
        activity = Activity.from_dict(data)
        assert activity.created_at is not None

    def test_from_dict_extracts_all_optional_fields(self):
        """Lines 65-73: all optional fields extracted from dict."""
        data = {
            'id': 99, 'tenant_id': 5, 'customer_id': 10,
            'opportunity_id': 20, 'type': 'meeting',
            'content': 'Discussed pricing', 'created_by': 3
        }
        activity = Activity.from_dict(data)
        assert activity.id == 99
        assert activity.tenant_id == 5
        assert activity.customer_id == 10
        assert activity.opportunity_id == 20
        assert activity.type == ActivityType.MEETING
        assert activity.content == 'Discussed pricing'
        assert activity.created_by == 3