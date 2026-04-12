"""
Unit tests for Opportunity model.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from src.models.opportunity import Opportunity, Stage


class TestOpportunityModel:
    """Tests for Opportunity model."""

    def test_create_opportunity_defaults(self):
        """Test opportunity creation with default values."""
        opp = Opportunity(
            customer_id=1,
            name="Test Opportunity",
            stage=Stage.LEAD,
            amount=Decimal("10000"),
            probability=10,
            expected_close_date=datetime(2024, 12, 31),
            owner_id=1
        )
        
        assert opp.customer_id == 1
        assert opp.name == "Test Opportunity"
        assert opp.stage == Stage.LEAD
        assert opp.amount == Decimal("10000")
        assert opp.probability == 10
        assert isinstance(opp.created_at, datetime)
        assert isinstance(opp.updated_at, datetime)

    def test_stage_enum(self):
        """Test Stage enum values."""
        assert Stage.LEAD.value == "lead"
        assert Stage.QUALIFIED.value == "qualified"
        assert Stage.PROPOSAL.value == "proposal"
        assert Stage.NEGOTIATION.value == "negotiation"
        assert Stage.CLOSED_WON.value == "closed_won"
        assert Stage.CLOSED_LOST.value == "closed_lost"

    def test_probability_validation(self):
        """Test probability is clamped to 0-100 range."""
        # Test negative probability clamped to 0
        opp_neg = Opportunity(
            customer_id=1,
            name="Test",
            stage=Stage.LEAD,
            amount=Decimal("100"),
            probability=-10,
            expected_close_date=datetime.now(),
            owner_id=1
        )
        assert opp_neg.probability == 0
        
        # Test probability over 100 clamped to 100
        opp_over = Opportunity(
            customer_id=1,
            name="Test",
            stage=Stage.LEAD,
            amount=Decimal("100"),
            probability=150,
            expected_close_date=datetime.now(),
            owner_id=1
        )
        assert opp_over.probability == 100
        
        # Test valid probability stays same
        opp_valid = Opportunity(
            customer_id=1,
            name="Test",
            stage=Stage.LEAD,
            amount=Decimal("100"),
            probability=50,
            expected_close_date=datetime.now(),
            owner_id=1
        )
        assert opp_valid.probability == 50

    def test_to_dict(self):
        """Test opportunity to_dict conversion."""
        opp = Opportunity(
            id=1,
            customer_id=1,
            name="Test Opportunity",
            stage=Stage.PROPOSAL,
            amount=Decimal("50000"),
            probability=50,
            expected_close_date=datetime(2024, 12, 31),
            owner_id=1
        )
        
        result = opp.to_dict()
        
        assert result["id"] == 1
        assert result["customer_id"] == 1
        assert result["name"] == "Test Opportunity"
        assert result["stage"] == "proposal"
        assert result["amount"] == "50000"
        assert result["probability"] == 50
        assert result["owner_id"] == 1
        assert "expected_close_date" in result
        assert "created_at" in result
        assert "updated_at" in result
