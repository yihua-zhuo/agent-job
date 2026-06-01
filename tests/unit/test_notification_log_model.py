"""Unit tests for NotificationLogModel ORM class."""

from __future__ import annotations

from datetime import datetime

from db.models.notification_log import NotificationLogModel


class TestNotificationLogModel:
    def test_tablename(self):
        assert NotificationLogModel.__tablename__ == "notification_logs"

    def test_to_dict_returns_all_fields(self):
        log = NotificationLogModel(
            id=1,
            tenant_id=10,
            notification_id=100,
            channel="email",
            status="sent",
            attempts=2,
            error=None,
        )
        d = log.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 10
        assert d["notification_id"] == 100
        assert d["channel"] == "email"
        assert d["status"] == "sent"
        assert d["attempts"] == 2
        assert d["error"] is None
        assert "created_at" in d

    def test_to_dict_with_error_field(self):
        log = NotificationLogModel(
            id=2,
            tenant_id=20,
            notification_id=200,
            channel="sms",
            status="failed",
            attempts=3,
            error="Connection timeout after 30s",
        )
        d = log.to_dict()
        assert d["error"] == "Connection timeout after 30s"
        assert d["id"] == 2
        assert d["channel"] == "sms"
        assert d["status"] == "failed"
        assert "created_at" in d