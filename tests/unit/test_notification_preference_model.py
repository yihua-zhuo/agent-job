"""Unit tests for NotificationPreferenceModel ORM class."""

from __future__ import annotations

from datetime import datetime

from db.models import NotificationPreferenceModel


class TestNotificationPreferenceModel:
    def test_tablename(self):
        assert NotificationPreferenceModel.__tablename__ == "notification_preferences"

    def test_columns_exist(self):
        column_names = {c.name for c in NotificationPreferenceModel.__table__.columns}
        assert column_names == {"id", "user_id", "tenant_id", "channel", "enabled", "created_at", "updated_at"}

    def test_to_dict_returns_all_fields(self):
        now = datetime(2026, 6, 1, 12, 0, 0)
        updated = datetime(2026, 6, 1, 13, 0, 0)
        pref = NotificationPreferenceModel(
            id=1,
            user_id=10,
            tenant_id=5,
            channel="email",
            enabled=True,
            created_at=now,
            updated_at=updated,
        )
        result = pref.to_dict()
        assert result["id"] == 1
        assert result["user_id"] == 10
        assert result["tenant_id"] == 5
        assert result["channel"] == "email"
        assert result["enabled"] is True
        assert result["created_at"] == now.isoformat()
        assert result["updated_at"] == updated.isoformat()

    def test_to_dict_disabled_preference(self):
        pref = NotificationPreferenceModel(
            id=2,
            user_id=20,
            tenant_id=8,
            channel="sms",
            enabled=False,
            created_at=None,
        )
        result = pref.to_dict()
        assert result["enabled"] is False
        assert result["created_at"] is None
