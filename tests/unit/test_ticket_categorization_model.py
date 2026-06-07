"""Unit tests for TicketCategorizationModel."""

from datetime import UTC, datetime
from decimal import Decimal

from db.models.ticket_categorization import TicketCategorizationModel


class TestTicketCategorizationInit:
    def test_id_defaults_to_none(self):
        """id starts as None before DB persistence."""
        tc = TicketCategorizationModel(
            tenant_id=1,
            ticket_id=1,
            category_type="billing",
        )
        assert tc.id is None

    def test_required_fields(self):
        """tenant_id, ticket_id, category_type are required."""
        tc = TicketCategorizationModel(tenant_id=1, ticket_id=1, category_type="support")
        assert tc.tenant_id == 1
        assert tc.ticket_id == 1
        assert tc.category_type == "support"

    def test_optional_fields_default_to_none(self):
        """Optional fields start as None."""
        tc = TicketCategorizationModel(tenant_id=1, ticket_id=1, category_type="billing")
        assert tc.priority is None
        assert tc.confidence is None
        assert tc.reasons is None
        assert tc.suggested_assignee_id is None
        assert tc.suggested_team is None
        assert tc.categorized_at is None

    def test_human_override_optional_with_to_dict_fallback(self):
        """human_override is not passed to constructor; to_dict() returns False as default."""
        tc = TicketCategorizationModel(tenant_id=1, ticket_id=1, category_type="billing")
        # human_override has server_default so it may be None before DB insert;
        # to_dict() normalises it to False for consistency.
        assert tc.human_override is None or tc.human_override is False
        assert tc.to_dict()["human_override"] is False

    def test_all_fields_set(self):
        """All fields can be set without error."""
        now = datetime.now(UTC)
        tc = TicketCategorizationModel(
            tenant_id=1,
            ticket_id=42,
            category_type="technical",
            priority="high",
            confidence=Decimal("0.9523"),
            reasons={"keywords": ["error", "crash"]},
            suggested_assignee_id=7,
            suggested_team="Tier-2",
            human_override=True,
            categorized_at=now,
        )
        assert tc.tenant_id == 1
        assert tc.ticket_id == 42
        assert tc.category_type == "technical"
        assert tc.priority == "high"
        assert tc.confidence == Decimal("0.9523")
        assert tc.reasons == {"keywords": ["error", "crash"]}
        assert tc.suggested_assignee_id == 7
        assert tc.suggested_team == "Tier-2"
        assert tc.human_override is True
        assert tc.categorized_at == now


class TestTicketCategorizationToDict:
    def test_to_dict_returns_all_fields(self):
        """to_dict() returns every model field."""
        now = datetime.now(UTC)
        tc = TicketCategorizationModel(
            tenant_id=1,
            ticket_id=2,
            category_type="billing",
            priority="low",
            confidence=Decimal("0.1234"),
            reasons={"source": "keywords"},
            suggested_assignee_id=5,
            suggested_team="Billing",
            human_override=True,
            categorized_at=now,
        )
        d = tc.to_dict()
        assert d["id"] is None
        assert d["tenant_id"] == 1
        assert d["ticket_id"] == 2
        assert d["category_type"] == "billing"
        assert d["priority"] == "low"
        assert d["confidence"] == Decimal("0.1234")
        assert d["reasons"] == {"source": "keywords"}
        assert d["suggested_assignee_id"] == 5
        assert d["suggested_team"] == "Billing"
        assert d["human_override"] is True
        assert d["categorized_at"] == now.isoformat()

    def test_to_dict_reasons_null_guard(self):
        """reasons=None in model becomes {} in to_dict()."""
        tc = TicketCategorizationModel(tenant_id=1, ticket_id=1, category_type="billing")
        d = tc.to_dict()
        assert d["reasons"] == {}

    def test_to_dict_categorized_at_none(self):
        """categorized_at=None in model becomes None string in to_dict()."""
        tc = TicketCategorizationModel(tenant_id=1, ticket_id=1, category_type="billing")
        d = tc.to_dict()
        assert d["categorized_at"] is None

    def test_to_dict_human_override_false(self):
        """human_override=False is preserved in to_dict()."""
        tc = TicketCategorizationModel(tenant_id=1, ticket_id=1, category_type="billing")
        d = tc.to_dict()
        assert d["human_override"] is False

    def test_to_dict_confidence_decimal(self):
        """confidence remains a Decimal after to_dict()."""
        tc = TicketCategorizationModel(
            tenant_id=1,
            ticket_id=1,
            category_type="billing",
            confidence=Decimal("0.9999"),
        )
        d = tc.to_dict()
        assert isinstance(d["confidence"], Decimal)
        assert d["confidence"] == Decimal("0.9999")
