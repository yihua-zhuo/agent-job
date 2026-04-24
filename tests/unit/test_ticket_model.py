"""Unit tests for Ticket and TicketReply models."""
import pytest
from datetime import datetime, timedelta, UTC
from src.models.ticket import (
    Ticket, TicketReply, TicketStatus, TicketPriority,
    TicketChannel, SLALevel, SLAConfig, SLA_CONFIGS
)


class TestTicketInit:
    """Tests for Ticket __post_init__ method."""

    def test_post_init_clears_none_id(self):
        """Lines 55-56: id None stays None."""
        t = Ticket(
            subject="Help", description="Issue", status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM, channel=TicketChannel.EMAIL,
            customer_id=1, sla_level=SLALevel.BASIC
        )
        assert t.id is None

    def test_post_init_clears_none_assigned_to(self):
        """Lines 57-58: assigned_to None stays None."""
        t = Ticket(
            subject="Help", description="Issue", status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM, channel=TicketChannel.EMAIL,
            customer_id=1, sla_level=SLALevel.BASIC
        )
        assert t.assigned_to is None

    def test_post_init_sets_default_created_at(self):
        """Lines 59-60: created_at defaults to now."""
        t = Ticket(
            subject="Help", description="Issue", status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM, channel=TicketChannel.EMAIL,
            customer_id=1, sla_level=SLALevel.BASIC
        )
        assert t.created_at is not None
        assert isinstance(t.created_at, datetime)

    def test_post_init_sets_default_updated_at(self):
        """Lines 61-62: updated_at defaults to now."""
        t = Ticket(
            subject="Help", description="Issue", status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM, channel=TicketChannel.EMAIL,
            customer_id=1, sla_level=SLALevel.BASIC
        )
        assert t.updated_at is not None


class TestTicketSlaBreach:
    """Tests for Ticket.check_sla_breach() method."""

    def test_breach_false_when_resolved(self):
        """Lines 66-67: resolved ticket cannot breach."""
        t = Ticket(
            subject="Help", description="Issue", status=TicketStatus.RESOLVED,
            priority=TicketPriority.MEDIUM, channel=TicketChannel.EMAIL,
            customer_id=1, sla_level=SLALevel.BASIC,
            resolved_at=datetime.now(UTC)
        )
        assert t.check_sla_breach() is False

    def test_breach_false_when_no_deadline(self):
        """Lines 68-69: no deadline means no breach."""
        t = Ticket(
            subject="Help", description="Issue", status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM, channel=TicketChannel.EMAIL,
            customer_id=1, sla_level=SLALevel.BASIC,
            response_deadline=None
        )
        assert t.check_sla_breach() is False

    def test_breach_true_when_past_deadline(self):
        """Line 70: past deadline means breach."""
        past = datetime.now(UTC) - timedelta(hours=2)
        t = Ticket(
            subject="Help", description="Issue", status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM, channel=TicketChannel.EMAIL,
            customer_id=1, sla_level=SLALevel.BASIC,
            response_deadline=past
        )
        assert t.check_sla_breach() is True

    def test_breach_false_when_before_deadline(self):
        """Line 70: within deadline means no breach."""
        future = datetime.now(UTC) + timedelta(hours=2)
        t = Ticket(
            subject="Help", description="Issue", status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM, channel=TicketChannel.EMAIL,
            customer_id=1, sla_level=SLALevel.BASIC,
            response_deadline=future
        )
        assert t.check_sla_breach() is False


class TestTicketReplyInit:
    """Tests for TicketReply __post_init__ method."""

    def test_post_init_clears_none_id(self):
        """Lines 84-85: id None stays None."""
        reply = TicketReply(
            ticket_id=1, content="Info", is_internal=False, created_by=1
        )
        assert reply.id is None

    def test_post_init_sets_default_created_at(self):
        """Lines 86-87: created_at defaults to now."""
        reply = TicketReply(
            ticket_id=1, content="Info", is_internal=False, created_by=1
        )
        assert reply.created_at is not None
        assert isinstance(reply.created_at, datetime)


class TestSlaConfigs:
    """Tests for SLA_CONFIGS dictionary."""

    def test_all_sla_levels_have_config(self):
        """All SLA levels have corresponding configs."""
        for level in SLALevel:
            assert level in SLA_CONFIGS
            config = SLA_CONFIGS[level]
            assert isinstance(config, SLAConfig)
            assert config.first_response_hours > 0
            assert config.resolution_hours > 0