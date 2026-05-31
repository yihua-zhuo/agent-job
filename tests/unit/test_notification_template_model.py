"""Unit tests for src/db/models/notification_template.py — NotificationTemplateModel ORM class."""

from datetime import datetime

import pytest

from db.models.notification_template import NotificationTemplateModel


class TestNotificationTemplateModel:
    def test_table_name(self):
        """__tablename__ is notification_templates."""
        assert NotificationTemplateModel.__tablename__ == "notification_templates"

    def test_to_dict_returns_all_fields(self):
        """to_dict() serializes all required and optional fields correctly."""
        now = datetime(2026, 1, 15, 10, 30, 0)
        model = NotificationTemplateModel(
            id=1,
            tenant_id=42,
            name="Welcome Email",
            channel="email",
            subject="Welcome!",
            body_html="<p>Hello</p>",
            body_text="Hello",
            created_at=now,
        )
        d = model.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 42
        assert d["name"] == "Welcome Email"
        assert d["channel"] == "email"
        assert d["subject"] == "Welcome!"
        assert d["body_html"] == "<p>Hello</p>"
        assert d["body_text"] == "Hello"
        assert d["created_at"] == now.isoformat()

    def test_to_dict_with_null_optional_fields(self):
        """to_dict() handles subject, body_html, body_text as None gracefully."""
        now = datetime(2026, 3, 1, 8, 0, 0)
        model = NotificationTemplateModel(
            id=5,
            tenant_id=7,
            name="SMS Reminder",
            channel="sms",
            subject=None,
            body_html=None,
            body_text=None,
            created_at=now,
        )
        d = model.to_dict()
        assert d["id"] == 5
        assert d["tenant_id"] == 7
        assert d["name"] == "SMS Reminder"
        assert d["channel"] == "sms"
        assert d["subject"] is None
        assert d["body_html"] is None
        assert d["body_text"] is None
        assert d["created_at"] == now.isoformat()

    @pytest.mark.parametrize(
        "channel",
        [
            "email",
            "sms",
            "push",
            "in_app",
        ],
    )
    def test_channel_accepts_standard_values(self, channel):
        """Channel field accepts email/sms/push/in_app."""
        now = datetime(2026, 5, 1, 12, 0, 0)
        model = NotificationTemplateModel(
            id=10,
            tenant_id=1,
            name="Test",
            channel=channel,
            created_at=now,
        )
        d = model.to_dict()
        assert d["channel"] == channel

    def test_name_max_length(self):
        """Name field accepts strings up to and including 100 characters."""
        now = datetime(2026, 5, 1, 12, 0, 0)
        model = NotificationTemplateModel(
            id=11,
            tenant_id=1,
            name="x" * 100,
            channel="email",
            created_at=now,
        )
        d = model.to_dict()
        assert len(d["name"]) == 100

    def test_subject_max_length(self):
        """Subject field accepts strings up to and including 255 characters."""
        now = datetime(2026, 5, 1, 12, 0, 0)
        model = NotificationTemplateModel(
            id=12,
            tenant_id=1,
            name="Test Subject",
            channel="email",
            subject="y" * 255,
            created_at=now,
        )
        d = model.to_dict()
        assert len(d["subject"]) == 255

    def test_to_dict_created_at_isoformat(self):
        """created_at is serialized as an ISO-format string."""
        now = datetime(2026, 6, 1, 14, 30, 0)
        model = NotificationTemplateModel(
            id=20,
            tenant_id=99,
            name="Date Test",
            channel="email",
            created_at=now,
        )
        d = model.to_dict()
        assert d["created_at"] == "2026-06-01T14:30:00"