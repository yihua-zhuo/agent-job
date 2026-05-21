"""Unit tests for Webhook ORM models."""
from datetime import datetime

from db.models.webhook import WebhookDeliveryModel, WebhookModel


class TestWebhookModel:
    def test_columns_present(self):
        """All expected columns are defined on WebhookModel."""
        fields = {"id", "tenant_id", "url", "events", "secret", "is_active", "created_at"}
        assert fields.issubset(WebhookModel.__annotations__.keys())

    def test_to_dict_all_fields(self):
        """to_dict returns every column, including datetime as ISO string."""
        now = datetime(2024, 6, 15, 12, 0, 0)
        wh = WebhookModel(
            id=1,
            tenant_id=10,
            url="https://example.com/hook",
            events=["customer.created", "customer.updated"],
            secret="test-signing-secret",  # noqa: S105  # test fixture, not a real credential
            is_active=True,
            created_at=now,
        )
        d = wh.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 10
        assert d["url"] == "https://example.com/hook"
        assert d["events"] == ["customer.created", "customer.updated"]
        assert d["secret"] == "test-signing-secret"  # noqa: S105
        assert d["is_active"] is True
        assert d["created_at"] == "2024-06-15T12:00:00"

    def test_to_dict_secret_null(self):
        """secret may be None and to_dict preserves it."""
        wh = WebhookModel(id=2, tenant_id=1, url="http://x.com", events=[], secret=None)
        assert wh.to_dict()["secret"] is None

    def test_to_dict_events_empty_list(self):
        """events is an empty list when not set."""
        wh = WebhookModel(id=3, tenant_id=2, url="http://x.com")
        assert wh.to_dict()["events"] == []

    def test_to_dict_events_none_defaults_to_empty(self):
        """events=None is normalised to [] in to_dict."""
        wh = WebhookModel(id=4, tenant_id=3, url="http://x.com")
        wh.events = None  # simulate DB NULL edge case
        assert wh.to_dict()["events"] == []

    def test_to_dict_created_at_none(self):
        """created_at None yields None in to_dict."""
        wh = WebhookModel(id=5, tenant_id=4, url="http://x.com")
        wh.created_at = None
        assert wh.to_dict()["created_at"] is None

    def test_to_dict_with_explicit_is_active(self):
        """is_active True is serialised correctly."""
        wh = WebhookModel(id=6, tenant_id=5, url="http://x.com", is_active=True)
        assert wh.to_dict()["is_active"] is True

    def test_composite_index_defined(self):
        """__table_args__ includes the ix_webhooks_tenant_active index."""
        names = {arg.name for arg in WebhookModel.__table_args__}
        assert "ix_webhooks_tenant_active" in names


class TestWebhookDeliveryModel:
    def test_columns_present(self):
        """All expected columns are defined on WebhookDeliveryModel."""
        fields = {
            "id", "webhook_id", "tenant_id", "event_type",
            "payload", "status", "response", "attempts", "delivered_at",
        }
        assert fields.issubset(WebhookDeliveryModel.__annotations__.keys())

    def test_fk_on_webhook_id(self):
        """webhook_id is a ForeignKey column with CASCADE delete."""
        col = WebhookDeliveryModel.__table__.c["webhook_id"]
        fk = list(col.foreign_keys)[0]
        assert str(fk.column) == "webhooks.id"
        assert fk.ondelete is not None

    def test_to_dict_all_fields(self):
        """to_dict returns every column, including datetime as ISO string."""
        now = datetime(2024, 7, 1, 8, 30, 0)
        delivery = WebhookDeliveryModel(
            id=1,
            webhook_id=5,
            tenant_id=10,
            event_type="customer.created",
            payload={"customer": {"id": 42}},
            status="delivered",
            response={"code": 200, "body": "ok"},
            attempts=3,
            delivered_at=now,
        )
        d = delivery.to_dict()
        assert d["id"] == 1
        assert d["webhook_id"] == 5
        assert d["tenant_id"] == 10
        assert d["event_type"] == "customer.created"
        assert d["payload"] == {"customer": {"id": 42}}
        assert d["status"] == "delivered"
        assert d["response"] == {"code": 200, "body": "ok"}
        assert d["attempts"] == 3
        assert d["delivered_at"] == "2024-07-01T08:30:00"

    def test_to_dict_response_null(self):
        """response may be None (not yet received) and to_dict preserves it."""
        delivery = WebhookDeliveryModel(
            id=2, webhook_id=1, tenant_id=1,
            event_type="ticket.created", payload={}, status="pending",
            response=None,
        )
        assert delivery.to_dict()["response"] is None

    def test_to_dict_payload_empty_dict(self):
        """payload={} is returned as-is (empty dict)."""
        delivery = WebhookDeliveryModel(
            id=3, webhook_id=1, tenant_id=1,
            event_type="ticket.created", payload={}, status="pending",
        )
        assert delivery.to_dict()["payload"] == {}

    def test_to_dict_payload_none_becomes_empty(self):
        """payload=None is normalised to {} in to_dict."""
        delivery = WebhookDeliveryModel(
            id=4, webhook_id=1, tenant_id=1,
            event_type="ticket.created", status="pending",
        )
        delivery.payload = None
        assert delivery.to_dict()["payload"] == {}

    def test_to_dict_delivered_at_null(self):
        """delivered_at None yields None in to_dict."""
        delivery = WebhookDeliveryModel(
            id=5, webhook_id=1, tenant_id=1,
            event_type="ticket.created", payload={}, status="pending",
        )
        assert delivery.to_dict()["delivered_at"] is None

    def test_to_dict_with_explicit_status_pending(self):
        """status 'pending' is serialised correctly."""
        delivery = WebhookDeliveryModel(
            id=6, webhook_id=1, tenant_id=1,
            event_type="ticket.created", payload={}, status="pending",
        )
        assert delivery.to_dict()["status"] == "pending"

    def test_to_dict_with_explicit_attempts_one(self):
        """attempts=1 is serialised correctly."""
        delivery = WebhookDeliveryModel(
            id=7, webhook_id=1, tenant_id=1,
            event_type="ticket.created", payload={}, attempts=1,
        )
        assert delivery.to_dict()["attempts"] == 1

    def test_index_on_webhook_id(self):
        """__table_args__ includes the ix_webhook_deliveries_webhook_id index."""
        names = {arg.name for arg in WebhookDeliveryModel.__table_args__}
        assert "ix_webhook_deliveries_webhook_id" in names
