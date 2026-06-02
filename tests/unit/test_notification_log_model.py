"""Unit tests for NotificationLogModel ORM class."""

from __future__ import annotations

from datetime import datetime

from db.models.notification_log import NotificationLogModel


class TestNotificationLogModel:
    def test_table_name(self):
        assert NotificationLogModel.__tablename__ == "notification_logs"

    def test_to_dict_returns_all_fields(self):
        now = datetime(2026, 6, 1, 12, 0, 0)
        log = NotificationLogModel(
            id=1,
            tenant_id=10,
            notification_id=100,
            channel="email",
            status="sent",
            attempts=2,
            error=None,
            created_at=now,
        )
        d = log.to_dict()
        assert "created_at" in d
        assert d["id"] == 1
        assert d["tenant_id"] == 10
        assert d["notification_id"] == 100
        assert d["channel"] == "email"
        assert d["status"] == "sent"
        assert d["attempts"] == 2
        assert d["error"] is None
        assert d["created_at"] == now.isoformat()

    def test_to_dict_with_error_field(self):
        now = datetime(2026, 6, 1, 12, 0, 0)
        log = NotificationLogModel(
            id=2,
            tenant_id=20,
            notification_id=200,
            channel="sms",
            status="failed",
            attempts=3,
            error="Connection timeout after 30s",
            created_at=now,
        )
        d = log.to_dict()
        assert "created_at" in d
        assert d["error"] == "Connection timeout after 30s"
        assert d["id"] == 2
        assert d["channel"] == "sms"
        assert d["status"] == "failed"
        assert d["created_at"] == now.isoformat()
