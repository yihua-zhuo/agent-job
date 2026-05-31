"""Unit tests for src/db/models/notification_template.py — NotificationTemplateModel ORM class."""

from datetime import datetime, UTC

from db.models.notification_template import NotificationTemplateModel


class TestNotificationTemplateModel:
    def test_table_name(self):
        assert NotificationTemplateModel.__tablename__ == "notification_templates"

    def test_to_dict_returns_all_fields(self):
        now = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
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
        now = datetime(2026, 3, 1, 8, 0, 0, tzinfo=UTC)
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
