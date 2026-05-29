"""Unit tests for ScoreRequest and ScoreResponse schemas."""
import pytest
from pydantic import ValidationError

from src.models.score import ScoreRequest, ScoreResponse


class TestScoreResponse:
    """Tests for ScoreResponse schema."""

    def test_all_fields_set(self):
        """ScoreResponse round-trip with all fields populated."""
        resp = ScoreResponse(
            score=85,
            tier="hot_lead",
            score_factors={"source": 25, "company_size": 22},
            top_factors=["source", "company_size"],
            recommendations=["Schedule demo call", "Send pricing sheet"],
        )
        d = resp.to_dict()
        assert d["score"] == 85
        assert d["tier"] == "hot_lead"
        assert d["score_factors"] == {"source": 25, "company_size": 22}
        assert d["top_factors"] == ["source", "company_size"]
        assert d["recommendations"] == ["Schedule demo call", "Send pricing sheet"]

    def test_all_fields_none(self):
        """ScoreResponse to_dict returns None for all fields when unset."""
        resp = ScoreResponse()
        d = resp.to_dict()
        assert d["score"] is None
        assert d["tier"] is None
        assert d["score_factors"] is None
        assert d["top_factors"] is None
        assert d["recommendations"] is None

    def test_score_factors_dict_serialization(self):
        """score_factors dict is serialized correctly."""
        resp = ScoreResponse(score_factors={"title": 22, "engagement": 18})
        d = resp.to_dict()
        assert d["score_factors"] == {"title": 22, "engagement": 18}

    def test_top_factors_list_serialization(self):
        """top_factors list is serialized correctly."""
        resp = ScoreResponse(top_factors=["source", "company_size", "title"])
        d = resp.to_dict()
        assert d["top_factors"] == ["source", "company_size", "title"]

    def test_recommendations_list_serialization(self):
        """recommendations list is serialized correctly."""
        resp = ScoreResponse(recommendations=["Send email", "Follow up in 3 days"])
        d = resp.to_dict()
        assert d["recommendations"] == ["Send email", "Follow up in 3 days"]


class TestScoreRequest:
    """Tests for ScoreRequest schema."""

    def test_valid_input(self):
        """Valid input is accepted."""
        req = ScoreRequest(
            customer_id=1,
            tenant_id=1,
            source="referral",
            company_size=100,
            title="CEO",
            engaged_actions=["downloaded_trial", "booked_demo"],
        )
        assert req.customer_id == 1
        assert req.source == "referral"

    def test_customer_id_required(self):
        """customer_id must be provided."""
        with pytest.raises(ValidationError):
            ScoreRequest(
                tenant_id=1,
                source="referral",
                company_size=100,
                title="CEO",
                engaged_actions=[],
            )

    def test_customer_id_must_be_positive(self):
        """customer_id must be > 0."""
        with pytest.raises(ValidationError):
            ScoreRequest(customer_id=0, tenant_id=1, source="x", company_size=0, title="y")

    def test_tenant_id_required(self):
        """tenant_id must be provided."""
        with pytest.raises(ValidationError):
            ScoreRequest(
                customer_id=1,
                source="referral",
                company_size=100,
                title="CEO",
                engaged_actions=[],
            )

    def test_source_required(self):
        """source must be provided."""
        with pytest.raises(ValidationError):
            ScoreRequest(
                customer_id=1,
                tenant_id=1,
                company_size=100,
                title="CEO",
                engaged_actions=[],
            )

    def test_engaged_actions_default_empty(self):
        """engaged_actions defaults to empty list."""
        req = ScoreRequest(
            customer_id=1,
            tenant_id=1,
            source="website",
            company_size=50,
            title="Manager",
        )
        assert req.engaged_actions == []

    def test_to_dict(self):
        """to_dict renders all fields correctly."""
        req = ScoreRequest(
            customer_id=5,
            tenant_id=2,
            source="linkedin",
            company_size=200,
            title="VP Sales",
            engaged_actions=["attended_webinar"],
        )
        d = req.to_dict()
        assert d["customer_id"] == 5
        assert d["tenant_id"] == 2
        assert d["source"] == "linkedin"
        assert d["company_size"] == 200
        assert d["title"] == "VP Sales"
        assert d["engaged_actions"] == ["attended_webinar"]