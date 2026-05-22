"""Unit tests for SmartNotificationModel."""

from datetime import UTC, datetime

from db.models.smart_notification import (
    Channel,
    Priority,
    SmartNotificationModel,
    Timing,
)


class TestPriorityEnum:
    def test_priority_values(self):
        assert Priority.urgent.value == 0
        assert Priority.normal.value == 1
        assert Priority.low.value == 2


class TestChannelEnum:
    def test_channel_values(self):
        assert Channel.email.value == 0
        assert Channel.sms.value == 1
        assert Channel.push.value == 2
        assert Channel.in_app.value == 3


class TestTimingEnum:
    def test_timing_values(self):
        assert Timing.immediate.value == 0
        assert Timing.batch.value == 1


class TestSmartNotificationModel:
    def test_tablename(self):
        assert SmartNotificationModel.__tablename__ == "smart_notifications"

    def test_instantiation_with_required_fields(self):
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        record = SmartNotificationModel(
            id=1,
            tenant_id=42,
            summarized_content="You have 3 new tasks",
            priority=Priority.urgent,
            channel=Channel.push,
            timing=Timing.immediate,
            recipient_filter={"role": "admin"},
            created_at=now,
        )
        assert record.id == 1
        assert record.tenant_id == 42
        assert record.summarized_content == "You have 3 new tasks"
        assert record.priority == Priority.urgent
        assert record.channel == Channel.push
        assert record.timing == Timing.immediate
        assert record.recipient_filter == {"role": "admin"}
        assert record.created_at == now

    def test_instantiation_with_defaults(self):
        record = SmartNotificationModel(
            tenant_id=10,
            summarized_content="Summary here",
        )
        assert record.tenant_id == 10
        assert record.summarized_content == "Summary here"
        # mapped_column defaults are applied by the DB on insert; Python-level
        # construction leaves them as None unless explicitly passed.
        assert record.recipient_filter is None

    def test_to_dict(self):
        now = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)
        record = SmartNotificationModel(
            id=5,
            tenant_id=7,
            summarized_content="Weekly digest",
            priority=Priority.low,
            channel=Channel.sms,
            timing=Timing.batch,
            recipient_filter={"segment": "vip"},
            created_at=now,
        )
        result = record.to_dict()
        assert result["id"] == 5
        assert result["tenant_id"] == 7
        assert result["summarized_content"] == "Weekly digest"
        assert result["priority"] == Priority.low
        assert result["channel"] == Channel.sms
        assert result["timing"] == Timing.batch
        assert result["recipient_filter"] == {"segment": "vip"}
        assert result["created_at"] == "2026-03-15T10:30:00+00:00"

    def test_to_dict_with_none_recipient_filter(self):
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        record = SmartNotificationModel(
            id=2,
            tenant_id=3,
            summarized_content="Test content",
            created_at=now,
        )
        result = record.to_dict()
        assert result["recipient_filter"] is None
        assert "created_at" in result

    def test_to_dict_isoformat(self):
        now = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)
        record = SmartNotificationModel(
            id=99,
            tenant_id=1,
            summarized_content="End of year summary",
            created_at=now,
        )
        result = record.to_dict()
        assert result["created_at"] == "2026-12-31T23:59:59+00:00"
