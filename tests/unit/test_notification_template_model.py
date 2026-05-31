"""Unit tests for src/db/models/notification_template.py — NotificationTemplateModel ORM class."""

from datetime import datetime

import pytest

from db.models.notification_template import NotificationTemplateModel


class TestNotificationTemplateModel:
    """Model-only tests; cross-tenant isolation is enforced at the service layer, not here."""

    def test_table_name(self):
        """__tablename__ is notification_templates."""
        assert NotificationTemplateModel.__tablename__ == "notification_templates"

    def test_to_dict_returns_all_fields(self):
        """to_dict() serializes all required and optional fields correctly."""
        now = datetime(2026, 1, 15, 10, 30, 0)
        updated = datetime(2026, 1, 16, 11, 0, 0)
        model = NotificationTemplateModel(
            id=1,
            tenant_id=42,
            name="Welcome Email",
            channel="email",
            subject="Welcome!",
            body_html="<p>Hello</p>",
            body_text="Hello",
            created_at=now,
            updated_at=updated,
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
        assert d["updated_at"] == updated.isoformat()

    def test_to_dict_with_null_optional_fields(self):
        """to_dict() handles subject, body_html, body_text, updated_at as None gracefully."""
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
            updated_at=None,
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
        assert d["updated_at"] is None

    @pytest.mark.parametrize("channel", ["email", "sms", "push", "in_app"])
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

    @pytest.mark.parametrize(
        "channel",
        [
            "webhook",
            "fax",
            "",
            "EMAIL",
            "sms_upper",
            "x" * 21,
        ],
    )
    def test_channel_non_standard_values_accepted(self, channel):
        """Channel does not enforce a value set at the ORM layer; any CHECK constraint or business-rule validation is delegated to the service or DB layer. This test documents the current acceptance boundary."""
        now = datetime(2026, 5, 1, 12, 0, 0)
        model = NotificationTemplateModel(
            id=15,
            tenant_id=1,
            name="Rejection Test",
            channel=channel,
            created_at=now,
        )
        d = model.to_dict()
        assert d["channel"] == channel  # ORM accepts; enforcement delegated to service/DB layer

    def test_name_accepts_100_chars(self):
        """Name field accepts a 100-character string without error."""
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

    def test_subject_accepts_255_chars(self):
        """Subject field accepts a 255-character string without error."""
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

    def test_updated_at_serialization(self):
        """updated_at is serialized as an ISO-format string when set, None when absent."""
        now = datetime(2026, 6, 1, 14, 30, 0)
        updated = datetime(2026, 6, 2, 9, 0, 0)
        # With value
        model_with = NotificationTemplateModel(
            id=21,
            tenant_id=99,
            name="Has Updated",
            channel="email",
            created_at=now,
            updated_at=updated,
        )
        assert model_with.to_dict()["updated_at"] == "2026-06-02T09:00:00"
        # With None
        model_without = NotificationTemplateModel(
            id=22,
            tenant_id=99,
            name="No Updated",
            channel="email",
            created_at=now,
            updated_at=None,
        )
        assert model_without.to_dict()["updated_at"] is None

    def test_empty_name_is_accepted_by_orm(self):
        """The ORM layer does not validate that name is non-empty; DB-level NOT NULL enforcement is exercised by integration tests."""
        now = datetime(2026, 6, 1, 14, 30, 0)
        model = NotificationTemplateModel(
            id=25,
            tenant_id=1,
            name="",
            channel="email",
            created_at=now,
        )
        assert model.to_dict()["name"] == ""

    def test_unknown_channel_accepted_by_orm(self):
        """The ORM layer does not validate channel values; invalid values are accepted and silently stored. DB-level enforcement (CHECK constraint) is exercised by integration tests."""
        now = datetime(2026, 6, 1, 14, 30, 0)
        model = NotificationTemplateModel(
            id=26,
            tenant_id=1,
            name="Unknown Channel",
            channel="telegram",
            created_at=now,
        )
        assert model.to_dict()["channel"] == "telegram"
